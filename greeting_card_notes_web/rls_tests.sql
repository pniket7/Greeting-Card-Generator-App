-- Cross-account access checks for the Rooting For You tables.
-- Run in Supabase → SQL Editor after supabase_schema.sql.
-- The script rolls back, so the test users and notes are not kept.

begin;

insert into auth.users (
  instance_id,
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  confirmation_token,
  email_change,
  email_change_token_new,
  recovery_token
) values
  (
    '00000000-0000-0000-0000-000000000000',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'authenticated',
    'authenticated',
    'rls-a@example.com',
    '',
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{}'::jsonb,
    now(),
    now(),
    '',
    '',
    '',
    ''
  ),
  (
    '00000000-0000-0000-0000-000000000000',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'authenticated',
    'authenticated',
    'rls-b@example.com',
    '',
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{}'::jsonb,
    now(),
    now(),
    '',
    '',
    '',
    ''
  );

insert into public.note_input (
  id, owner_id, occasion_category, specific_moment, relationship,
  relationship_closeness, recipient_name, known_context, status
) values
  (
    '11111111-1111-1111-1111-111111111111',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'celebrate', 'birthday', 'friend', 'warm', 'A Recipient', 'private fact A', 'ready'
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'thank', 'thank_you', 'colleague', 'formal', 'B Recipient', 'private fact B', 'ready'
  );

insert into public.note_output (
  id, note_input_id, owner_id, version_number, source, content, is_final
) values
  (
    '33333333-3333-3333-3333-333333333333',
    '22222222-2222-2222-2222-222222222222',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    1,
    'generated',
    'private note B',
    true
  ),
  (
    '44444444-4444-4444-4444-444444444444',
    '11111111-1111-1111-1111-111111111111',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    1,
    'generated',
    'private note A',
    true
  );

insert into public.note_trace (note_input_id, note_output_id, event_type, prompt, response)
values (
  '22222222-2222-2222-2222-222222222222',
  '33333333-3333-3333-3333-333333333333',
  'writer',
  'secret prompt',
  'secret response'
);

insert into public.note_eval (note_output_id, owner_id)
values
  (
    '33333333-3333-3333-3333-333333333333',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
  ),
  (
    '44444444-4444-4444-4444-444444444444',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
  );

set local role authenticated;
select set_config('request.jwt.claim.sub', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', true);
select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa","role":"authenticated"}',
  true
);

do $$
declare
  seen_inputs integer;
  seen_notes integer;
  seen_traces integer;
begin
  select count(*) into seen_inputs from public.note_input;
  if seen_inputs <> 1 then
    raise exception 'user A saw % questionnaires, expected 1', seen_inputs;
  end if;

  if exists (
    select 1 from public.note_input where known_context = 'private fact B'
  ) then
    raise exception 'user A read user B questionnaire text';
  end if;

  select count(*) into seen_notes from public.note_output;
  if seen_notes <> 1 then
    raise exception 'user A saw % note versions, expected 1', seen_notes;
  end if;

  if exists (
    select 1 from public.note_output where content = 'private note B'
  ) then
    raise exception 'user A read user B note text';
  end if;
end $$;

do $$
declare
  seen_traces integer;
begin
  begin
    select count(*) into seen_traces from public.note_trace;
    if seen_traces <> 0 then
      raise exception 'user A read a model trace';
    end if;
  exception
    when insufficient_privilege then
      null;
  end;
end $$;

do $$
begin
  begin
    perform 1 from public.prompt_version;
    raise exception 'authenticated user could read prompt_version';
  exception
    when insufficient_privilege then
      null;
  end;

  begin
    insert into public.note_output (
      note_input_id, owner_id, version_number, source, content, is_final
    ) values (
      '11111111-1111-1111-1111-111111111111',
      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      2,
      'generated',
      'forged note',
      false
    );
    raise exception 'authenticated user inserted a generated note';
  exception
    when insufficient_privilege then
      null;
  end;

  begin
    update public.note_eval
    set qa_notes = 'staff note from the browser'
    where note_output_id = '44444444-4444-4444-4444-444444444444';
    if found then
      raise exception 'authenticated user wrote a staff score';
    end if;
  exception
    when insufficient_privilege then
      null;
  end;
end $$;

rollback;
