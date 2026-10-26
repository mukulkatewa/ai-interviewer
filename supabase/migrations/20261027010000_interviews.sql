-- Phase 6: interviews, started from a job match report (projectprep.md, D25).

-- Target for the composite FK below (same ownership pattern as the first migration).
alter table public.analyses add constraint analyses_id_user_id_key unique (id, user_id);

create table public.interviews (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references auth.users (id) on delete cascade,
    analysis_id  uuid not null,
    status       text not null default 'created'
                 check (status in ('created', 'in_progress', 'evaluating', 'completed', 'failed')),
    created_at   timestamptz not null default now(),
    started_at   timestamptz,
    ended_at     timestamptz,
    -- Only from your own analysis, enforced by Postgres even if app code has a bug.
    foreign key (analysis_id, user_id) references public.analyses (id, user_id) on delete cascade
);
create index interviews_user_created_idx on public.interviews (user_id, created_at desc);
create index interviews_analysis_idx on public.interviews (analysis_id, user_id);  -- for cascading deletes

-- RLS on with no policies: the public Data API can't touch it (D15).
alter table public.interviews enable row level security;
