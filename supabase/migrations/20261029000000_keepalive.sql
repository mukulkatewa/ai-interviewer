-- Keep the free Supabase project from being paused for inactivity (D39).
-- A scheduled GitHub Action calls public.keepalive() through the REST API; it is a real database write.

create table public.keepalive (
    id         int primary key default 1 check (id = 1),  -- exactly one row
    pinged_at  timestamptz not null default now()
);
insert into public.keepalive default values;
-- RLS on with no policies, like every table (D15): the only way in is the function below.
alter table public.keepalive enable row level security;

-- SECURITY DEFINER so the public key can run it, with an empty search_path so it can't be hijacked.
-- It touches nothing but this one timestamp, so letting anyone call it is harmless.
create function public.keepalive() returns timestamptz
    language sql security definer set search_path = ''
as $$ update public.keepalive set pinged_at = now() where id = 1 returning pinged_at $$;

revoke all on function public.keepalive() from public;
-- `anon` exists on Supabase but not on the plain Postgres the tests use.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        grant execute on function public.keepalive() to anon;
    end if;
end $$;
