-- Phase 9: background jobs and interview reports (projectprep.md 5.12, D31).

-- Durable work queue. Internal infrastructure, not user data: no user_id; the
-- payload names what to work on, and handlers re-check ownership when they load it.
create table public.jobs (
    id          uuid primary key default gen_random_uuid(),
    kind        text not null,
    payload     jsonb not null,
    status      text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
    attempts    int not null default 0,
    run_after   timestamptz not null default now(),
    last_error  text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
-- The worker's two queries touch only queued / running rows; partial indexes stay tiny
-- however many finished jobs pile up.
create index jobs_queued_idx on public.jobs (run_after) where status = 'queued';
create index jobs_running_idx on public.jobs (updated_at) where status = 'running';

create table public.evaluations (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references auth.users (id) on delete cascade,
    interview_id   uuid not null unique,
    overall_score  smallint check (overall_score between 0 and 100),  -- null when too short to judge
    report         jsonb not null,                                      -- Report
    created_at     timestamptz not null default now(),
    foreign key (interview_id, user_id) references public.interviews (id, user_id) on delete cascade
);

-- RLS on with no policies: the public Data API can't touch either table (D15).
alter table public.jobs enable row level security;
alter table public.evaluations enable row level security;
