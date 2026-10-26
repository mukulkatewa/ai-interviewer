-- Phase 8: interview plan, position, and saved turns (projectprep.md, 5.11).

alter table public.interviews
    add column plan jsonb,                                   -- InterviewPlan, written once at creation
    add column position jsonb not null default '{}'::jsonb,  -- where the conversation is (question, follow-ups)
    add constraint interviews_id_user_id_key unique (id, user_id);  -- target for the composite FK below

create table public.interview_turns (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references auth.users (id) on delete cascade,
    interview_id    uuid not null,
    seq             int not null,              -- 0, 1, 2... in speaking order
    role            text not null check (role in ('interviewer', 'candidate')),
    question_index  int not null,              -- which planned question this turn belongs to
    text            text not null,
    -- Latency per turn (projectprep.md, 9): measured, stored, reported.
    audio_seconds   real,                      -- candidate: answer length
    stt_ms          int,                       -- candidate: transcription time
    llm_ms          int,                       -- interviewer: time to first sentence
    tts_ms          int,                       -- interviewer: time to first audio
    segments        jsonb,                     -- candidate: Whisper timestamps, for speaking metrics (phase 9)
    created_at      timestamptz not null default now(),
    foreign key (interview_id, user_id) references public.interviews (id, user_id) on delete cascade,
    unique (interview_id, seq)                 -- also serves "turns of an interview, in order"
);

-- RLS on with no policies: the public Data API can't touch it (D15).
alter table public.interview_turns enable row level security;
