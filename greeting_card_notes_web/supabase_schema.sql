-- Rooting For You — Supabase schema for full debug logging
-- Run this once in: Supabase → SQL Editor → New query → Run

create extension if not exists "pgcrypto";

create table if not exists public.note_sessions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  email text not null default '',
  newsletter_consent boolean not null default false,
  occasion_category text not null default '',
  specific_moment text not null default '',
  recipient_name text not null default '',
  relationship text not null default '',
  relationship_closeness text not null default '',
  known_context text not null default '',
  user_override text not null default '',
  sender_name text not null default '',
  language text not null default 'English',
  final_note text not null default '',
  craft_notes text not null default '',
  verdict text not null default '',
  attempts integer not null default 0,
  refinements_used integer not null default 0
);

create table if not exists public.note_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  session_id uuid references public.note_sessions(id) on delete cascade,
  event_type text not null,
  -- writer | reviewer | reviser | refine
  prompt text not null default '',
  response text not null default '',
  parsed_note text not null default '',
  meta jsonb not null default '{}'::jsonb
);

create index if not exists note_sessions_created_at_idx on public.note_sessions (created_at desc);
create index if not exists note_events_session_id_idx on public.note_events (session_id);
create index if not exists note_events_event_type_idx on public.note_events (event_type);

-- Backend uses the service role key, so RLS can stay enabled with no public policies.
alter table public.note_sessions enable row level security;
alter table public.note_events enable row level security;
