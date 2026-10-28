-- An interview can start from a resume alone: the job description step is optional (D36).

alter table public.interviews
    add column resume_id   uuid,
    add column target_role text,                    -- optional role the candidate typed instead of a full job description
    alter column analysis_id drop not null;         -- null = no job description was given

-- Existing interviews all came from an analysis, which knows the resume.
update public.interviews i set resume_id = a.resume_id from public.analyses a where a.id = i.analysis_id;
alter table public.interviews alter column resume_id set not null;

-- Same ownership pattern as everywhere: a resume of someone else can't be referenced.
alter table public.interviews
    add constraint interviews_resume_fk
    foreign key (resume_id, user_id) references public.resumes (id, user_id) on delete cascade;
create index interviews_resume_idx on public.interviews (resume_id, user_id);  -- for cascading deletes
