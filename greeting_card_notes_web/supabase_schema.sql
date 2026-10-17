-- Rooting For You — account, note, prompt, trace, and usefulness tables.
-- Run once in Supabase → SQL Editor.
--
-- Does not drop the old prototype tables note_sessions and note_events.
-- Stop writing those from the app. Drop them later, after this schema is receiving notes.
--
-- No payment tables. Notes are unlimited until payments exist.
-- Each note still allows only two AI rewrites. Hand edits do not count.
-- Prompt rows and model traces are server-only.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Prompt bundle. The Python files are the source. This table records the
-- writer, reviewer, and reviser text that actually ran. Rows are insert-only.
-- ---------------------------------------------------------------------------

create table if not exists public.prompt_version (
  id uuid primary key default gen_random_uuid(),
  label text not null,
  writer_prompt text not null,
  reviewer_prompt text not null,
  reviser_prompt text not null,
  content_hash text not null unique,
  model text not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Questionnaire. One row per note request.
-- ---------------------------------------------------------------------------

create table if not exists public.note_input (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users (id) on delete cascade,
  occasion_category text not null,
  specific_moment text not null,
  relationship text not null,
  relationship_closeness text not null,
  recipient_name text not null,
  sender_name text not null default '',
  known_context text not null default '',
  user_override text not null default '',
  language text not null default 'English',
  status text not null default 'draft'
    check (status in ('draft', 'generating', 'ready', 'failed', 'deleted')),
  deleted_at timestamptz,
  purge_after timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists note_input_owner_updated_idx
  on public.note_input (owner_id, updated_at desc);

-- ---------------------------------------------------------------------------
-- Every saved version of the words.
-- ---------------------------------------------------------------------------

create table if not exists public.note_output (
  id uuid primary key default gen_random_uuid(),
  note_input_id uuid not null references public.note_input (id) on delete cascade,
  owner_id uuid not null references auth.users (id) on delete cascade,
  version_number integer not null check (version_number > 0),
  source text not null check (source in ('generated', 'revision', 'user_edit')),
  content text not null,
  revision_instruction text,
  input_snapshot jsonb,
  model text,
  prompt_version_id uuid references public.prompt_version (id),
  is_final boolean not null default false,
  created_at timestamptz not null default now(),
  unique (note_input_id, version_number)
);

create unique index if not exists note_output_one_final_idx
  on public.note_output (note_input_id)
  where is_final;

create index if not exists note_output_input_version_idx
  on public.note_output (note_input_id, version_number);

-- ---------------------------------------------------------------------------
-- Full prompts and model replies. Not readable by the signed-in person.
-- ---------------------------------------------------------------------------

create table if not exists public.note_trace (
  id uuid primary key default gen_random_uuid(),
  note_output_id uuid references public.note_output (id) on delete cascade,
  note_input_id uuid not null references public.note_input (id) on delete cascade,
  event_type text not null
    check (event_type in ('writer', 'reviewer', 'reviser', 'refine')),
  prompt text not null default '',
  response text not null default '',
  parsed_note text not null default '',
  verdict text,
  failures jsonb,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists note_trace_input_idx
  on public.note_trace (note_input_id, created_at);

-- ---------------------------------------------------------------------------
-- One usefulness row per note version.
-- The person can set copied_at, rating, and reason_tag.
-- qa_* columns are for a later staff review. The API does not write them.
-- ---------------------------------------------------------------------------

create table if not exists public.note_eval (
  id uuid primary key default gen_random_uuid(),
  note_output_id uuid not null unique references public.note_output (id) on delete cascade,
  owner_id uuid not null references auth.users (id) on delete cascade,
  copied_at timestamptz,
  rating smallint check (rating is null or rating between 1 and 5),
  reason_tag text check (
    reason_tag is null or reason_tag in (
      'too_generic',
      'too_sentimental',
      'wrong_tone',
      'missed_point',
      'invented_detail',
      'strong'
    )
  ),
  qa_score smallint,
  qa_tags text[],
  qa_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists note_input_set_updated_at on public.note_input;
create trigger note_input_set_updated_at
  before update on public.note_input
  for each row execute function public.set_updated_at();

drop trigger if exists note_eval_set_updated_at on public.note_eval;
create trigger note_eval_set_updated_at
  before update on public.note_eval
  for each row execute function public.set_updated_at();

-- Block a third AI rewrite even if two requests overlap.
create or replace function public.limit_note_revisions()
returns trigger
language plpgsql
as $$
declare
  existing_revisions integer;
begin
  if new.source = 'revision' then
    select count(*) into existing_revisions
    from public.note_output
    where note_input_id = new.note_input_id
      and source = 'revision';
    if existing_revisions >= 2 then
      raise exception 'refinement limit reached';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists note_output_limit_revisions on public.note_output;
create trigger note_output_limit_revisions
  before insert on public.note_output
  for each row execute function public.limit_note_revisions();

-- ---------------------------------------------------------------------------
-- Access
-- The API uses the service role and bypasses these policies.
-- The policies block the browser from reading other people or forging a
-- generated note if the anon key is used with a user token.
-- ---------------------------------------------------------------------------

alter table public.prompt_version enable row level security;
alter table public.note_input enable row level security;
alter table public.note_output enable row level security;
alter table public.note_trace enable row level security;
alter table public.note_eval enable row level security;

revoke all on table public.prompt_version from public, anon, authenticated;
revoke all on table public.note_trace from public, anon, authenticated;
revoke all on table public.note_input from public, anon, authenticated;
revoke all on table public.note_output from public, anon, authenticated;
revoke all on table public.note_eval from public, anon, authenticated;

grant all on table public.prompt_version to service_role;
grant all on table public.note_trace to service_role;
grant all on table public.note_input to service_role;
grant all on table public.note_output to service_role;
grant all on table public.note_eval to service_role;

grant select on table public.note_input to authenticated;
grant update (
  occasion_category,
  specific_moment,
  relationship,
  relationship_closeness,
  recipient_name,
  sender_name,
  known_context,
  user_override,
  language,
  status,
  deleted_at,
  purge_after
) on table public.note_input to authenticated;

grant select on table public.note_output to authenticated;
grant insert (
  note_input_id,
  owner_id,
  version_number,
  source,
  content,
  is_final
) on table public.note_output to authenticated;

grant select (
  id,
  note_output_id,
  owner_id,
  copied_at,
  rating,
  reason_tag,
  created_at,
  updated_at
) on table public.note_eval to authenticated;

grant update (copied_at, rating, reason_tag)
on table public.note_eval to authenticated;

drop policy if exists note_input_select_own on public.note_input;
create policy note_input_select_own
  on public.note_input
  for select
  to authenticated
  using (owner_id = auth.uid());

drop policy if exists note_input_update_own_draft on public.note_input;
create policy note_input_update_own_draft
  on public.note_input
  for update
  to authenticated
  using (owner_id = auth.uid() and status = 'draft')
  with check (owner_id = auth.uid() and status in ('draft', 'deleted'));

drop policy if exists note_output_select_own on public.note_output;
create policy note_output_select_own
  on public.note_output
  for select
  to authenticated
  using (owner_id = auth.uid());

drop policy if exists note_output_insert_own_edit on public.note_output;
create policy note_output_insert_own_edit
  on public.note_output
  for insert
  to authenticated
  with check (
    owner_id = auth.uid()
    and source = 'user_edit'
    and model is null
    and prompt_version_id is null
    and exists (
      select 1
      from public.note_input as parent
      where parent.id = note_input_id
        and parent.owner_id = auth.uid()
    )
  );

drop policy if exists note_eval_select_own on public.note_eval;
create policy note_eval_select_own
  on public.note_eval
  for select
  to authenticated
  using (owner_id = auth.uid());

drop policy if exists note_eval_update_own_signals on public.note_eval;
create policy note_eval_update_own_signals
  on public.note_eval
  for update
  to authenticated
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());
