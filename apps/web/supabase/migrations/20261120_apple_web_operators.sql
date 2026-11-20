-- Dedicated Daedalus web database; do NOT run in an unrelated project.
-- Provision the first auth user through a trusted admin invitation; no self-registration.
create table if not exists public.web_operators (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('owner','operator','viewer')),
  disabled boolean not null default false,
  created_at timestamptz not null default now()
);
alter table public.web_operators enable row level security;
revoke all on public.web_operators from anon;
grant select on public.web_operators to authenticated;
drop policy if exists web_operator_self_read on public.web_operators;
create policy web_operator_self_read on public.web_operators for select to authenticated
  using ((select auth.uid()) = user_id);
create table if not exists public.web_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  appearance text not null default 'system' check (appearance in ('system','light','dark')),
  updated_at timestamptz not null default now()
);
alter table public.web_preferences enable row level security;
revoke all on public.web_preferences from anon;
grant select, insert, update, delete on public.web_preferences to authenticated;
drop policy if exists web_preferences_own on public.web_preferences;
create policy web_preferences_own on public.web_preferences for all to authenticated
  using ((select auth.uid()) = user_id and exists
    (select 1 from public.web_operators o where o.user_id=(select auth.uid()) and not o.disabled))
  with check ((select auth.uid()) = user_id and exists
    (select 1 from public.web_operators o where o.user_id=(select auth.uid()) and not o.disabled));
create table if not exists public.web_audit (
  id bigint generated always as identity primary key,
  operator_id uuid not null references auth.users(id) on delete cascade,
  action text not null check (char_length(action) between 1 and 96),
  outcome text not null check (outcome in ('accepted','rejected','uncertain','observed')),
  request_ref uuid,
  created_at timestamptz not null default now()
);
alter table public.web_audit enable row level security;
revoke all on public.web_audit from anon,authenticated;
-- Never store account snapshots or auth tokens in this table.
