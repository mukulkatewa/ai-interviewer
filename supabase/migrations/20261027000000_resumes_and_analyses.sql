-- Phase 3: saved resumes, job descriptions and analyses (projectprep.md, section 7).

create table public.resumes (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    file_name   text not null,
    raw_text    text not null,          -- PDF itself is not stored (D17)
    profile     jsonb not null,         -- ResumeProfile
    created_at  timestamptz not null default now(),
    -- Target for the composite FKs below: lets the DB check that a row points
    -- at a resume owned by the *same* user.
    unique (id, user_id)
);
create index resumes_user_created_idx on public.resumes (user_id, created_at desc);

create table public.job_descriptions (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    raw_text    text not null,
    profile     jsonb not null,         -- JobProfile
    created_at  timestamptz not null default now(),
    unique (id, user_id)
);
create index job_descriptions_user_created_idx on public.job_descriptions (user_id, created_at desc);

create table public.analyses (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null references auth.users (id) on delete cascade,
    resume_id           uuid not null,
    job_description_id  uuid not null,
    score               smallint check (score between 0 and 100),  -- null when the JD lists no skills
    match               jsonb not null,  -- MatchResult
    insights            jsonb not null,  -- Insights
    created_at          timestamptz not null default now(),
    -- Composite FKs: an analysis can only reference this user's own resume/JD,
    -- enforced by Postgres even if application code has a bug.
    foreign key (resume_id, user_id) references public.resumes (id, user_id) on delete cascade,
    foreign key (job_description_id, user_id) references public.job_descriptions (id, user_id) on delete cascade
);
create index analyses_user_created_idx on public.analyses (user_id, created_at desc);
-- Postgres doesn't index FK columns automatically; without these, deleting a
-- resume scans the whole analyses table to find rows to cascade.
create index analyses_resume_idx on public.analyses (resume_id, user_id);
create index analyses_job_description_idx on public.analyses (job_description_id, user_id);

-- RLS on with no policies = the public Data API can't touch these tables (D15).
-- Our backend connects as the table owner, which RLS doesn't restrict.
alter table public.resumes enable row level security;
alter table public.job_descriptions enable row level security;
alter table public.analyses enable row level security;
