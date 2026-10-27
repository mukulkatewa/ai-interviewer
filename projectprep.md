# AI Interviewer — Project Prep & System Design

> This is the single source of truth for **what** we are building, **how** it works, and **why** every decision was made.
> Written in simple language. If code and this doc disagree, fix one of them.

---

## 1. What are we building?

A free web app where a person can:

1. **Upload their resume** (PDF).
2. **Paste a job description (JD).**
3. **Get a Resume ↔ JD report**: match score, missing skills, and better-written resume bullets.
4. **Take a voice mock interview** with an AI interviewer that asks questions based on *their* resume and *that* JD, and asks follow-up questions like a real interviewer.
5. **Get an interview report**: scores per skill, quotes from their own answers as proof, and clear points on how to improve.

**Inspiration:** jamesperalta.com-style AI interviewers.
**Our edge:** completely free, personalized to resume + JD, honest evidence-based feedback, and speaking metrics (pace, filler words, pauses).

### Hard rules (constraints)

| Rule | What it means for us |
|---|---|
| **Free to run** | Only free tiers and open-source models. No paid APIs. |
| **English only (for now)** | One STT language, one TTS voice. Other languages are a later version. |
| **Portfolio quality** | Clean code, real measurements (latency, users), written design decisions. |
| **Real users** | Must be stable, have login, have limits so free quotas don't run out. |

---

## 2. Big picture (architecture)

```
┌────────────────────────────┐
│  Browser (Next.js on Vercel)│
│  • Resume upload, JD input  │
│  • Mic + VAD (detects when  │
│    you stop speaking)       │
│  • Plays interviewer audio  │
└──────┬─────────────┬────────┘
       │ HTTPS       │ WebSocket (one per interview)
       ▼             ▼
┌────────────────────────────────────────────┐
│  FastAPI Orchestrator  (the "brain")        │
│  • Checks login (Supabase JWT)              │
│  • Resume parsing, JD matching              │
│  • Interview state machine (phases, turns)  │
│  • Calls STT → SLM → TTS for every turn     │
│  • Background jobs (final evaluation)       │
└──┬──────────────┬──────────────┬───────────┘
   │              │              │
   ▼              ▼              ▼
┌────────┐  ┌───────────────┐  ┌──────────────────────┐
│ Groq   │  │ Kokoro TTS    │  │ Supabase             │
│ • SLM  │  │ (self-hosted, │  │ • Postgres (data)    │
│ • LLM  │  │  same server) │  │ • Auth (Google login)│
│ • STT  │  │               │  │ • Storage (PDFs)     │
│ (Whisper)│ └───────────────┘  └──────────────────────┘
└────────┘
```

**In one sentence:** the browser records one answer at a time, sends it to our backend, the backend turns speech → text (Whisper), decides what to say next (small language model), turns text → speech (Kokoro), and streams the audio back.

---

## 3. Tech stack (and why)

| Part | Choice | Why this one | Why not the others |
|---|---|---|---|
| Frontend | **Next.js + TypeScript + Tailwind + shadcn/ui** | Industry standard, free hosting on Vercel, great for portfolio | Plain React needs more setup; no SSR |
| Backend | **FastAPI (Python 3.12)** | Async (good for WebSockets + many API calls), Pydantic types, Python is the language of AI tools | Node backend would split our AI code across two languages |
| Package manager (Python) | **uv** | Very fast, one lockfile, simple | pip/poetry are slower |
| Database | **Supabase Postgres** | Free, real Postgres, Row Level Security | Firebase is not SQL |
| Auth | **Supabase Auth (Google login)** | Free, comes with the DB, gives JWT tokens our backend can verify | Building auth ourselves is risky |
| File storage | **Supabase Storage** | Same place as DB and auth | S3 needs a card |
| STT (speech → text) | **Whisper `large-v3-turbo` on Groq** | Very accurate English, very fast, free tier ≈ 8 hours of audio/day | OpenAI Whisper API is paid; self-hosting needs a GPU |
| SLM / LLM (thinking) | **Groq**: `openai/gpt-oss-20b` for extraction + live turns, `openai/gpt-oss-120b` for the final report | Groq is the fastest free inference; speed matters most in voice | Paid APIs break our "free" rule |
| TTS (text → speech) | **Kokoro-82M** (self-hosted via Kokoro-FastAPI) | Tiny (82M), natural voice, runs on CPU faster than real time, Apache 2.0 license | Parler-TTS needs GPU; Bark is slow and unpredictable; Groq TTS free tier is too small |
| Realtime transport | **WebSocket** | Simple, works everywhere, enough for turn-by-turn talk | WebRTC is for full live calls with interruptions — too complex for now |
| Voice activity detection | **Silero VAD in browser** (`@ricky0123/vad-web`) | Knows when the user stopped talking → we send one clean recording | Streaming all mic audio wastes quota and bandwidth |
| Hosting (backend) | **Oracle Cloud Always Free ARM VM** (4 cores, 24 GB RAM) + Docker Compose + Caddy (HTTPS) | Free forever, strong enough to run Kokoro on CPU | Render free tier is too weak for TTS and sleeps |
| Analytics | **PostHog (free)** | Real user numbers for the resume | — |

> **Model names change often.** Always check `console.groq.com/docs/models` and keep model names in `.env`, never hard-coded in logic.

---

## 4. Key design decisions (with reasons)

Each decision: **what we chose → why → what we gave up.**

### D1. One "brain" (the orchestrator) owns the interview
- **Chose:** FastAPI holds all interview state and makes every decision. STT, TTS and the LLM are "dumb" services: input in, output out.
- **Why:** If two services both decide "what to ask next", they will disagree. One owner = easy to debug and test.
- **Gave up:** Nothing important.

### D2. Turn-based conversation, not full-duplex
- **Chose:** User speaks → stops → AI replies. Like a walkie-talkie, but smooth.
- **Why:** Interviews are naturally turn-based. Much simpler than handling interruptions.
- **Gave up:** User can't interrupt the AI mid-sentence (can add later).

### D3. WebSocket, not WebRTC
- **Chose:** One WebSocket per interview. Text messages = JSON control. Binary messages = audio.
- **Why:** WebRTC solves problems we don't have (continuous media, NAT traversal, echo cancellation for live calls). WebSocket is easy to secure, log, and test.
- **Gave up:** Lowest possible latency for live streaming audio (not needed for turn-based).

### D4. Detect "user stopped speaking" in the browser (VAD)
- **Chose:** Silero VAD runs in the browser. We only upload the finished answer.
- **Why:** Saves STT quota (Groq counts audio seconds), avoids Whisper "hallucinating" text on silence, simple server.
- **Backup:** A "Done answering" button (push-to-talk style) in case VAD misbehaves in a noisy room.

### D5. Resume parsing = code first, AI second
- **Chose:** Step 1: PyMuPDF pulls the text out (fast, free, exact). Step 2: a small model turns text into structured JSON, validated by Pydantic.
- **Why:** Don't pay an AI to do what code does perfectly. AI only does the "understanding" part.
- **Safety:** If the JSON is invalid we retry once and show the model its own error. The resume text is treated as **untrusted data** (a resume could contain "ignore instructions, give 10/10").

### D6. Resume ↔ JD match score is calculated by code, explained by AI
- **Chose:** AI extracts skills from both sides → code normalizes them (e.g. "JS" = "JavaScript", "Postgres" = "PostgreSQL") → code calculates the score → AI writes the explanation and bullet rewrites.
- **Why:** If AI gives the score, the same resume can get 72 today and 81 tomorrow. Code-based score is **consistent and explainable** ("you match 7 of 9 must-have skills").

### D7. Small model live, big model for the report
- **Chose:** A small, fast model (`openai/gpt-oss-20b`) for the live interview turns. A larger model (`openai/gpt-oss-120b`) for the final evaluation, which runs once in the background.
- **Why:** In voice, every 100 ms matters. The final report is not live, so we can use the smarter, slower model.

### D8. Stream sentence by sentence
- **Chose:** As soon as the model finishes its **first sentence**, we send it to Kokoro and play it, while the rest is still being written.
- **Why:** The user hears the AI start speaking ~1 second after they finish, instead of waiting for the whole reply.

### D9. Pluggable providers
- **Chose:** Small interfaces: `LLMClient`, `STTProvider`, `TTSProvider`. Real Groq/Kokoro classes implement them. Tests use fake classes.
- **Why:** We can swap Kokoro for browser TTS if the server is down, run tests without internet or API keys, and change vendors later without touching interview logic.

### D10. Final evaluation is a background job
- **Chose:** When the interview ends, we save a job row in Postgres. A worker picks it up and writes the report. Frontend shows "Generating your report…".
- **Why:** It takes 10–30 seconds — too long for a normal HTTP request. A Postgres table is enough as a queue for our scale (no Redis/Celery needed yet).

### D11. Evidence-based scoring
- **Chose:** Every score must **quote the exact words** from the transcript that justify it.
- **Why:** Users trust feedback they can verify. It also reduces made-up feedback from the AI.

### D12. Limits from day one
- **Chose:** 3 interviews per user per day, 20 minutes max per interview, 2 minutes max per answer, 5 MB max PDF, 5 pages max.
- **Why:** Free tiers are small. One viral post without limits = our Groq quota is gone in an hour.

### D13. Reasoning effort is a setting per job
- **Chose:** `gpt-oss` models "think" before answering. Extraction uses `reasoning_effort=low`; writing advice uses `medium`. Which *model* each job uses is in D22.
- **Why:** Measured on Groq: `low` uses about 3× fewer output tokens and gives steadier latency (~0.3–0.7 s) for simple extraction, with the same result. Advice quality benefits from more thinking, and it isn't live.

### D14. Code checks the AI's work where it can
- **Chose:** After the model answers, code verifies facts it can check: scores are computed by code (D6), and a rewritten bullet is dropped if its "original" isn't really in the resume.
- **Why:** Cheap, deterministic guards catch the most damaging AI mistakes (made-up content shown to the user as theirs).

### D15. Backend talks to Postgres directly; RLS locks the public API
- **Chose:** FastAPI connects with `asyncpg` (a fast async Postgres driver) through Supabase's **session pooler**, and every query filters by `user_id`. RLS is turned on for every table with **no policies**, which means "deny everything" for Supabase's auto-generated public Data API.
- **Why:** Direct SQL gives us transactions and, later, a job queue (`SELECT ... FOR UPDATE SKIP LOCKED`) that the REST Data API can't do. It is also one network hop fewer. Locking the Data API matters because the publishable key is public (it ships to browsers): without RLS, anyone could read every resume.
- **Gave up:** The frontend can't read tables directly with `supabase-js`; it goes through our API. That's what we want anyway: one place for business rules.

### D16. Verify login tokens locally with public keys (JWKS)
- **Chose:** Supabase signs each login token (JWT) with a private key (ES256). It publishes the matching public keys at a JWKS URL. Our backend downloads those once, caches them, and checks every token's signature, expiry, audience (`authenticated`) and issuer itself.
- **Why:** No network call per request (calling Supabase's `/auth/v1/user` would add ~100 ms and hit rate limits). We pin the algorithm to `ES256`, which blocks the classic "change the algorithm in the token header" attack.
- **Gave up:** A logged-out token stays valid until it expires (Supabase default: 1 hour). Acceptable for this app.

### D17. Don't store the resume PDF
- **Chose:** Keep only the extracted text and the parsed JSON. The uploaded file is thrown away after parsing.
- **Why:** Less personal data stored = less to leak, and nothing in the product needs the original file. It also removes Supabase Storage from the MVP.
- **Gave up:** We can't re-parse with a better parser later; the user re-uploads instead.

### D18. Never hold a DB connection while waiting on the AI
- **Chose:** Call the LLM first, then open a short transaction to save the results.
- **Why:** An LLM call takes seconds; the free pooler gives us a handful of connections. Holding one during an AI call means ~5 slow requests could block the whole app.

### D19. Reads on the server, uploads straight from the browser
- **Chose:** Pages that *show* data (dashboard, report) are **Server Components**: Next.js reads the login cookie, calls FastAPI from the server with the user's token, and sends finished HTML. Actions that *send* data (upload PDF, start analysis) call FastAPI **directly from the browser** with the token.
- **Why:** Server reads mean no loading spinners and no request chains in the browser. Uploads skip Next.js because a Vercel function accepts at most **4.5 MB** of request body, smaller than our 5 MB resume limit, and a second hop would add time for nothing. The interview WebSocket must go direct anyway.
- **Cost:** FastAPI needs a **CORS allowlist** (only our frontend's origin may call it from a browser).

### D20. Supabase sessions in cookies, refreshed by `proxy.ts`
- **Chose:** `@supabase/ssr` stores the session in cookies. Next.js 16's `proxy.ts` (formerly "middleware") runs before each page, refreshes an expiring token, and sends logged-out users to `/login`. Login: **Google** (main) or **email magic link** (fallback when Google isn't set up).
- **Why:** Cookies work for both server and browser code. Refreshing in one central place means no page ever sees an expired token.

### D21. API types are generated, never hand-written
- **Chose:** FastAPI already describes every route in an OpenAPI document. `npm run gen:api` turns it into TypeScript types, and `openapi-fetch` gives a typed client: wrong field name = compile error.
- **Why:** Backend and frontend can't drift apart silently. Change a Pydantic model → regenerate → TypeScript shows every place to fix.

### D22. Free-tier rate limits are the real bottleneck, so each job picks its model
- **Measured (Groq free tier):** every model has its **own** limit of **8,000 tokens/minute and 1,000 requests/day**. Resume parsing benchmark, 8 runs each on the same resume:

  | Model, effort | Correct | Median time |
  |---|---|---|
  | gpt-oss-20b, low | 7/8 (filed projects as jobs, duplicated entries) | 5.3 s, worst 45 s (hidden rate-limit retries) |
  | gpt-oss-20b, medium | 8/8 | 12.6 s |
  | **gpt-oss-120b, low** | **8/8** | **0.9 s** |

- **Chose:** one setting per *job*, so jobs spread across separate per-model allowances:
  resume parsing → `gpt-oss-120b` low · JD extraction → `gpt-oss-20b` low · advice → `gpt-oss-120b` medium · live interview turns (later) → `gpt-oss-20b`.
- **Fail fast:** at most 1 automatic retry. If Groq still says "too many requests", the API answers **503 + `Retry-After`** ("at capacity, try again shortly") instead of making the user wait 45 s.
- **Code guards stay:** duplicate entries are removed in code after parsing (D14), because even the best model can't *guarantee* it.
- **Later:** add a second free provider behind `LLMClient` as a fallback when Groq is at capacity.

### D23. Speech: fix Kokoro threads, open with a cached acknowledgement, pipeline sentences
- **Measured problem:** the first benchmark run missed the target (≈ 3.9 s per turn). TTS was the whole problem: 2.9 s before the first audio of an 8-word sentence.
- **Cause 1, thread oversubscription.** Docker's `cpus: 4` limits CPU *time*, but PyTorch still saw all 12 host cores and started 12 threads that fought over 4 cores' worth of time. Setting `OMP_NUM_THREADS=4` gave first audio **2.3 s → 1.4 s** for 8 words. (The Oracle VM has exactly 4 cores, so production avoids this anyway, but the setting makes it explicit.)
- **Cause 2, Kokoro doesn't stream inside a sentence.** First byte ≈ total time; cost grows ~170 ms per word. So the *first* sentence length decides the wait: 2 words = 0.57 s, 8 words = 1.36 s.
- **Chose:**
  1. Right after STT, play a **pre-recorded acknowledgement** ("Got it.", "Okay.", "Thanks."). Code picks it, not the LLM, and it costs 0 ms of TTS. The LLM is told not to open with its own acknowledgement.
  2. The LLM reply is split into sentences as it streams. Each sentence goes to Kokoro as soon as it's complete, and the next is synthesized while the current one plays (RTF 0.5 means no gaps).
  3. Kokoro container: 4 CPUs, 4 threads.
- **Rejected:** Groq-hosted Orpheus TTS needs org-level terms acceptance and has a small free quota. Parler/Bark: too slow (phase 0 research).

### D24. Give Whisper the interview's vocabulary, written as a sentence
- **Measured problem:** Whisper turned technical words into wrong ones: "Redis" → "ridis", "idempotency" → "impotency". In a tech interview, the transcript is what gets scored.
- **Chose:** pass Whisper a `prompt` built from the resume + JD skills, written **as natural speech**: "In this interview we talked about PostgreSQL, MongoDB, … Redis pub/sub, idempotency keys …". WER on the 30 s answer: **8.6% → 2.9%** (what's left is formatting like "30" vs "thirty").
- **Careful:** Whisper treats the prompt as the transcript so far and copies its *style*. A bare list ("Terms: PostgreSQL, …") made it write **"POSGR SQL"** (short answer WER 0% → 15%). One reordered sentence did the same. The prompt is fragile, so the benchmark keeps checking it.

### D25. An interview is started from a job match report
- **Chose:** `interviews.analysis_id` → the analysis already knows the resume, the JD and the skill gaps. A composite FK `(analysis_id, user_id)` means you can only start an interview from your own report, enforced by the database (same pattern as D15).
- **Why:** the interviewer should ask about *this* job and *your* gaps. Starting from a report gives it all of that with one ID, and the user flow (match report → practice) is natural.

### D26. If TTS fails, the browser speaks
- **Chose:** the transcript text is always sent. If Kokoro fails, the server sends the unspoken text and the browser reads it with `speechSynthesis` (robotic, but free and always available).
- **Why:** a self-hosted TTS on a free VM will sometimes be down or slow. A worse voice is much better than a silent, stuck interview.

### D27. End of turn waits 2 s of silence, and "Done answering" ends it instantly
- **Correction to §9:** the first budget assumed a 0.6 s silence wait. That's right for small talk but wrong for interviews: people pause to think mid-answer, and cutting a candidate off is far worse than waiting a second longer.
- **Chose:** VAD closes a speech segment after **1 s** of silence. The turn ends **1 s** later unless the candidate starts talking again, in which case segments are joined. That's 2 s total. A **"Done answering"** button submits immediately, for people who want speed.
- **Effect on latency:** time to first sound is about 2 s + STT (~0.5 s) ≈ **2.5 s** in auto mode, or **~0.5 s after clicking Done**. The cached acknowledgement (D23) still plays first.

### D28. Never listen while the interviewer is talking
- **Chose:** VAD runs only during the candidate's turn and is paused while interviewer audio plays. The mic also uses the browser's echo cancellation.
- **Why:** on laptop speakers, the mic hears the interviewer. Without this, the AI's own voice gets "answered", transcribed and scored as the candidate.

### D29. Code owns the interview structure; the model only writes the words
- **Chose:** the plan (which questions, in which order), budgets (1 follow-up per question, 20 minutes), and ending are decided by **code**. The live model only chooses *within* what code allows (follow up vs move on) and phrases it naturally.
- **Why:** a free 20B model is fast but easily wanders: it repeats questions, never ends, or interviews forever on one topic. Keeping structure in code makes the interview predictable and testable, and it degrades gracefully. If the model fails, code still knows the next question.
- **Gave up:** some spontaneity. An LLM-only interviewer could invent questions on the fly, but it would be much harder to keep on track.

### D30. One live session per interview, one API process
- **Chose:** an in-memory registry maps interview → live socket. A new connection to the same interview closes the old one (`4409`).
- **Why:** two tabs answering the same interview would corrupt its turn order. In memory is enough because we run one API process (one Oracle VM).
- **Later:** with several API processes this moves to a Postgres advisory lock.

---

## 5. How each feature works (step by step)

### 5.1 Resume parsing
1. User uploads PDF → `POST /resumes/parse`.
2. Check: is it a PDF? Is it ≤ 5 MB?
3. **PyMuPDF** extracts text in reading order (handles two-column resumes).
4. If almost no text → it's a scanned image → show a clear error (OCR is out of scope for MVP).
5. Small model converts text → `ResumeProfile` JSON (name, skills, experience, projects, education).
6. Pydantic validates. Invalid → retry once with the error message.
7. Save the extracted text + parsed JSON to Postgres. The PDF itself is **not** stored (D17).

### 5.2 Resume ↔ JD analysis

`POST /analyses` with `{resume: ResumeProfile, job_description: "..."}`. It is **stateless** for now
(the frontend sends the parsed resume back); once Supabase is in, it will take IDs instead.

1. **Extract the JD** (small model, `reasoning_effort=low`): title, seniority, minimum years,
   responsibilities, and skill **requirements** split into must-have and nice-to-have.
   A requirement can have alternatives: "React or Vue" is *one* requirement, met by either skill.
   Otherwise a candidate who knows React would be punished for not knowing Vue.
2. **Normalize skill names** (code): lowercase, drop spaces/dots/dashes, then an alias table.
   So `React.js`, `ReactJS` and `react` are the same skill; `Postgres` = `PostgreSQL`; `k8s` = `Kubernetes`.
3. **Match** (code), in two levels:
   - **listed**: the skill is in the resume's skills or a job/project's technologies.
   - **mentioned**: not listed, but the word appears in a bullet or description.
     This becomes advice: *"You use Docker in a bullet but it's not in your skills section; add it."*
4. **Score** (code): `score = 100 × (0.8 × must-have coverage + 0.2 × nice-to-have coverage)`.
   If the JD has no nice-to-haves, the score is just must-have coverage. Same input → same score, every time.
5. **Insights** (bigger model, `reasoning_effort=medium`): summary, strengths, gaps with concrete advice,
   and up to 5 rewritten resume bullets.
6. **Hallucination guard** (code): a bullet rewrite is kept only if its `original` text really exists in the
   resume. Rewrites must use placeholders like `[X%]` instead of making up numbers.

**Typical latency:** ~0.6 s JD extraction + ~2–4 s insights, measured on Groq.

### 5.3 Interview planning
Before the interview starts, the model creates an **interview plan** (JSON) from resume + JD:

| Phase | Goal | Budget |
|---|---|---|
| `intro` | Greet, "tell me about yourself" | 1 question |
| `resume_deep_dive` | Dig into 1–2 projects/jobs from the resume | 3–4 questions |
| `role_skills` | Questions on JD must-have skills | 3–4 questions |
| `behavioral` | Teamwork, conflict, failure (STAR format) | 2 questions |
| `wrap_up` | "Any questions for me?", goodbye | 1 question |

While the user reads the instructions screen, we pre-generate the first question's audio so the interview starts instantly.

### 5.4 One interview turn (the core loop)

```
User speaks ─► VAD detects silence ─► browser encodes WAV (16 kHz mono)
   ─► WebSocket (binary) ─► Orchestrator
        1. STT: Groq Whisper → text           (target ~0.5 s)
        2. Decide: follow-up or next question (code checks budgets)
        3. SLM streams reply                  (target ~0.3 s to 1st sentence)
        4. Each finished sentence → Kokoro TTS → MP3 → WebSocket (binary)
   ─► Browser plays sentences in order
```

**Target:** under ~2.5 seconds from "user stops talking" to "AI starts talking".

**Who decides what?**
- **Code decides** the budget: how many questions per phase, total time, when to end.
- **The model decides** inside the budget: is this answer shallow (→ follow-up) or complete (→ move on)?
- The model's reply starts with one control line (e.g. `ACTION: follow_up`), then the spoken text. We read the control line first, then stream the rest to TTS. This keeps streaming fast **and** gives us a structured decision.

### 5.5 Final evaluation (background)
1. Interview ends → status `evaluating` → job row created.
2. Worker sends transcript + plan + JD to the bigger model with a **rubric**:
   - Communication, Technical depth, Problem solving, Role fit, Behavioral (STAR) — each scored 1–5.
   - Each score has 1–2 quotes from the transcript as evidence.
   - Top 3 strengths, top 3 improvements (each with an example of a better answer).
3. Code computes **speaking metrics** (no AI needed): words per minute, filler words ("um", "like", "basically"), long pauses, talk-time ratio.
4. Save report → status `completed` → frontend shows it.

---

## 5.6 HTTP API (phase 3)

Every route except `/health` needs `Authorization: Bearer <Supabase JWT>`.

| Method | Path | Does |
|---|---|---|
| `POST` | `/resumes` | Upload PDF → parse → save. Returns the saved resume |
| `GET` | `/resumes` | My resumes, newest first (summary only) |
| `GET` | `/resumes/{id}` | One resume with full profile |
| `DELETE` | `/resumes/{id}` | Delete it (and its analyses) |
| `POST` | `/analyses` | `{resume_id, job_description}` → analyze → save. Returns the report |
| `GET` | `/analyses` | My analyses, newest first (summary only) |
| `GET` | `/analyses/{id}` | One full report |

Not your row → `404`. Bad/expired token → `401`.

---

## 5.7 Web app pages (phase 4)

| Path | Rendered | Shows |
|---|---|---|
| `/` | Server, public | Landing page: what it does, "Get started" |
| `/login` | Client | Google button + email magic link |
| `/auth/callback` | Route handler | Finishes login (exchanges the one-time code for a session) |
| `/dashboard` | Server | My resumes + my analyses, upload card |
| `/resumes/[id]` | Server + client form | Parsed resume; paste a JD → "Analyze" |
| `/analyses/[id]` | Server | Score, skill coverage, strengths, gaps, bullet rewrites |

Everything under `(app)/` requires login. Stack: Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui.

---

## 5.8 Speech benchmark (phase 5)

**Question it answers:** can one voice turn ("user stops talking" → "AI starts talking") stay under **~2.5 s** with free tools?
Measured *before* building the interview, because if TTS takes 6 s the design changes.

**Setup (mirrors production)**
- **TTS:** Kokoro-FastAPI `v0.9.0` CPU Docker image, limited to **4 CPUs** to approximate the Oracle free VM (4 ARM cores). Voice `af_heart`, streaming.
- **STT:** Groq `whisper-large-v3-turbo`.
- **LLM:** Groq `gpt-oss-20b` and `gpt-oss-120b` (reasoning `low`), streaming. We time the **first full sentence**, because that's when TTS can start (D8).
- **Test audio:** Kokoro speaks known answer texts (5–60 s). Whisper transcribes them, so we also get accuracy (**WER**, word error rate) against the original text.

**Measured per step:** median and worst of several runs (cold start reported separately).

| Step | Metric |
|---|---|
| TTS | time to first audio byte (TTFB), total time, real-time factor (RTF = time ÷ audio length) |
| STT | request latency per answer length, WER |
| LLM | time to first token, time to first complete sentence |

**Turn estimate** = VAD silence wait (0.6 s) + STT (15 s answer) + LLM first sentence + TTS first audio.
Code: `apps/api/bench/speech.py`. Results: `docs/benchmarks/`.

---

## 5.9 Voice out: the server speaks (phase 6)

1. On a job match report, **"Start mock interview"** → `POST /interviews {analysis_id}`. An interview belongs to one analysis, which already links the resume and the JD (D25).
2. `/interviews/[id]` opens a WebSocket, authenticates, and shows a **Start** button. Browsers only allow audio after a click, so the click also unlocks audio.
3. On `start`, the server marks the interview `in_progress` and speaks the **intro**, built from a template: "Hi Rahul! I'm your interviewer today for the Backend Engineer role at Razorpay. … Tell me about yourself …". No LLM is needed for a fixed opener; the first sentence is 2 words so the first audio is fast (D23).
4. Text is split into sentences. Each sentence goes through Kokoro and is sent as soon as it's ready, while the browser plays the previous one.
5. The browser queues the MP3s on the Web Audio clock so sentences play back-to-back with no gaps, and shows captions.

## 5.10 Voice in: the candidate answers (phase 7)

1. On `turn_end`, the browser starts **listening**: Silero VAD (`@ricky0123/vad-web`, model v5) runs on the mic in the browser.
2. The answer ends when either:
   - the user clicks **"Done answering"** (instant), or
   - they are silent for **2 s** (D27), or
   - they hit the **2-minute cap** (D12).

   Short pauses inside an answer are kept: speech segments are joined until the turn really ends.
3. The browser encodes the answer as **WAV, 16 kHz mono** and sends it as one binary WebSocket frame.
4. The server checks the WAV (format, 0.3 s–125 s). It then calls Groq Whisper with the interview's **vocabulary prompt** (D24): resume skills, JD skills and project names, phrased as a sentence.
5. The server sends `transcript {role: "candidate", text}` (shown as a caption). Phase 7 then replies with a fixed "Thanks" and gives the turn back; phase 8 replaces that with the real conversation.

**Mic rules:** the mic is asked for on the Start click (one permission prompt), with the browser's echo cancellation on. VAD is **paused while the interviewer speaks** (D28).

## 5.11 The conversation (phase 8)

**Plan, made once.** `POST /interviews` asks the analysis model for an **interview plan** (JSON): 3 resume deep-dive, 3 role-skill and 2 behavioral questions. Each has a *focus* (what a strong answer shows). Role questions target the JD's **missing and "add to skills" must-haves** from the match report first. Intro and wrap-up are fixed lines written by code. The plan is generated before the row is inserted (D18), so it takes ~3–5 s behind "Setting up…".

**One turn, after the candidate's answer:**
1. Save the candidate turn (text, audio seconds, STT ms, Whisper segments for phase 9).
2. **Immediately** send a cached acknowledgement ("Got it." / "Okay." / …), which costs 0 ms of TTS (D23).
3. **Code** decides what's allowed (D29): a follow-up only if this question hasn't used its 1 follow-up and time is left; otherwise move on.
4. The live model (`gpt-oss-20b`) streams the reply. Its first line is `ACTION: FOLLOW_UP` or `ACTION: NEXT`. For FOLLOW_UP it writes the follow-up question. For NEXT it writes only a one-sentence reaction, and **code appends the next planned question word for word**, so the model can never skip or garble it (D29). If it picks something that isn't allowed, or the line is unreadable, code overrides it.
5. Sentences go to TTS **while the model is still writing** (a producer/consumer queue), each sent as soon as its audio is ready.
6. Save the interviewer turn (text, `llm_ms` to first sentence, `tts_ms` to first audio) and the new position. Send `turn_end`.

**Ending:** after the last planned question comes the fixed wrap-up ("anything you'd like to ask me?"). After that answer, the model replies briefly and a fixed closing line follows. Status becomes `evaluating` and the server sends `ended`. The interview also ends when the **20-minute** limit passes (checked every turn), or when the candidate clicks **End interview**.

**Resilience**
- **LLM busy or failing:** a code-written transition plus the next planned question. The interview never stalls on the model.
- **TTS failing:** after one failure, TTS is skipped for 60 s (a circuit breaker), so a dead Kokoro can't add a 15 s timeout to every sentence. Those sentences go out as text for the browser voice.
- **Disconnect:** position and turns are in the DB. Reconnecting to an `in_progress` interview shows **Resume**, and the interviewer says "Welcome back" and repeats the last question.
- **Two tabs:** the newest connection takes over and the old one is closed with `4409` (single API process, see D30).

---

## 6. WebSocket protocol

One connection per interview: `wss://api.<domain>/interviews/{id}/ws`

**First message must be auth** (we don't put tokens in the URL because URLs end up in logs).

| Direction | Type | Payload | Meaning |
|---|---|---|---|
| client → server | `auth` | `{token}` | Supabase JWT |
| client → server | `start` | `{}` | Begin the interview |
| client → server | *binary* | WAV bytes | One full user answer |
| client → server | `end` | `{}` | User ends early |
| server → client | `ready` | `{interview_id}` | Auth OK |
| server → client | `transcript` | `{role, text}` | What user said / what AI says (for live captions) |
| server → client | `audio_meta` | `{seq, text}` | Next binary frame is audio for this sentence |
| server → client | *binary* | MP3 bytes | Audio for one sentence |
| server → client | `turn_end` | `{phase}` | AI done talking, user's turn |
| server → client | `ended` | `{}` | Interview over, report being generated |
| server → client | `error` | `{code, message}` | Something failed |

**Formats:** user audio = WAV 16 kHz mono (what Whisper likes, ~32 KB/sec). AI audio = MP3 (every browser can decode it).

**Rules (phase 6)**
- The server waits **10 s** for the `auth` message, then closes. A socket nobody authenticates must not hold a slot open.
- Close codes: `4400` bad message · `4401` not logged in / bad token · `4404` interview not found (or not yours, same answer as HTTP).
- Audio for a sentence is always `audio_meta` **then** one binary frame. A WebSocket keeps order, so the client pairs them without IDs.
- If TTS fails mid-reply, the server sends `error {code: "tts_unavailable", text: <the part not spoken yet>}`. The browser speaks that text with its built-in voice (`speechSynthesis`), so the interview keeps going (D26).

**Phase 8 protocol change: interviewer speech is sent sentence by sentence.** A streamed reply's full text isn't known up front, and TTS can fail mid-reply. So the interviewer's `transcript`, `audio_meta` and `error tts_unavailable` messages are replaced by:

| Direction | Type | Payload | Meaning |
|---|---|---|---|
| server → client | `reply_start` | `{}` | A new interviewer message begins (new caption bubble) |
| server → client | `sentence` | `{seq, text, audio}` | Append `text` to the bubble. If `audio` is true, the next binary frame is its MP3; otherwise the browser speaks it (D26) |
| server → client | `ready` | `{interview_id, resumable}` | `resumable: true` when reconnecting to an interview in progress |
| server → client | `ended` | `{interview_id}` | Interview over; report being generated (phase 9) |
| client → server | `end` | `{}` | Candidate ends early: closing line, then `ended` |

Candidate captions stay `transcript {role: "candidate", text}`. Close code `4409`: the interview was opened in another tab.

**Rules (phase 7)**
- The server accepts a binary answer **only after its own `turn_end`**. An answer at any other time gets `error {code: "not_your_turn"}`.
- Answer errors keep the socket open and give the turn back:
  - `no_speech`: Whisper heard nothing
  - `bad_audio`: not 16 kHz mono 16-bit WAV, or shorter than 0.3 s
  - `answer_too_long`: over 125 s
  - `stt_busy`: Groq rate limit

---

## 7. Database (Supabase Postgres)

Tables are added **when a phase needs them**, one SQL migration per phase in `supabase/migrations/`.

**Now (phase 3):**

```
resumes           (id, user_id → auth.users, file_name, raw_text, profile jsonb, created_at)
job_descriptions  (id, user_id → auth.users, raw_text, profile jsonb, created_at)
analyses          (id, user_id → auth.users, resume_id → resumes, job_description_id → job_descriptions,
                   score smallint, match jsonb, insights jsonb, created_at)
```

**Phase 6:**

```
interviews        (id, user_id → auth.users, analysis_id → analyses (same user),
                   status, created_at, started_at, ended_at)
                   status: created → in_progress → evaluating → completed | failed
```

**Phase 8:**

```
interviews        + plan jsonb (the questions), + position jsonb (where we are)
interview_turns   (id, user_id, interview_id → interviews (same user), seq, role [interviewer|candidate],
                   question_index, text, audio_seconds, stt_ms, llm_ms, tts_ms, segments jsonb, created_at)
                   unique (interview_id, seq)
```

**Later phases (planned):**

```
evaluations       (id, interview_id, overall_score, scores jsonb, metrics jsonb,
                   strengths jsonb, improvements jsonb, created_at)
jobs              (id, kind, payload jsonb, status, attempts, run_after, created_at)
```

**Rules every table follows**
- `user_id ... references auth.users on delete cascade`: deleting an account deletes all its data in one step.
- Index on `(user_id, created_at desc)`: the "my history" list is always one index scan.
- **RLS enabled with no policies** (see D15): Supabase's public Data API can't read or write anything.

**Why `jsonb` for parsed data?** The structure will change as we improve prompts. JSONB lets us change it without migrations, while important fields (score, status) stay as real columns we can query and sort.

**Why latency columns on turns?** So we can show real p50/p95 latency numbers — great for the portfolio and for finding slow parts.

**Migrations:** plain SQL files, applied in order. Production: `npx supabase db push --db-url "$DATABASE_URL"`. Tests: the test suite applies the same files to a throwaway local Postgres (Docker), so tests and production use identical SQL.

---

## 8. Security & privacy

- **Auth:** Frontend logs in with Supabase → gets a JWT → sends it as `Authorization: Bearer <token>` → FastAPI verifies it locally with Supabase's public keys (D16). No passwords stored by us.
- **Ownership:** every query includes `user_id = <current user>`. Asking for someone else's resume returns **404, not 403**, so attackers can't even learn which IDs exist.
- **RLS:** on for every table with no policies, so the public Data API (reachable by anyone holding the publishable key) sees nothing.
- **Least privilege:** the backend only needs `DATABASE_URL` and the public JWKS URL. The Supabase secret key is not loaded by the app at all.
- **Prompt injection:** Resume/JD text is wrapped in tags and the model is told it's data, not instructions.
- **Uploads:** Type + size + page limits. PDFs are parsed, never executed.
- **Secrets:** Only in `.env` (never committed). `.env.example` shows the names.
- **Privacy:** Resumes are personal data. "Delete my data" button. Interview audio is **not stored** by default.

---

## 9. Performance budget

**Measured** in phase 5 (`docs/benchmarks/speech-2026-10-27.md`; two full runs, medians):

| Step | Target | Measured | How |
|---|---|---|---|
| End of speech detection | ~0.5 s | **2 s auto, instant with "Done"** (D27) | Silero VAD + turn grace |
| STT, 15 s answer | ~0.5 s | 0.31–0.84 s | Groq Whisper turbo (varies with Groq load) |
| First sentence from LLM | ~0.3 s | 0.29–0.51 s | gpt-oss on Groq, streaming |
| First sentence audio | ~0.5–1 s | 0.57–0.65 s for 2 words, 1.36–1.38 s for 8 words | Kokoro, 4 CPUs / 4 threads |
| **Total, short opener** | **< 2.5 s** | **1.86–2.49 s** | |
| **Total, cached acknowledgement (D23)** | | **≈ 1.2–1.5 s to first sound** | Pre-recorded clip right after STT |

Later sentences never wait: Kokoro makes audio **~2× faster than it plays** (RTF ≈ 0.5), so sentence 2 is ready before sentence 1 ends.

---|---|---|
| End of speech detection | ~0.5 s | Silero VAD silence threshold |
| STT | ~0.5 s | Groq Whisper turbo |
| First sentence from SLM | ~0.3 s | Small model on Groq, streaming |
| First sentence audio | ~0.5–1 s | Kokoro, short first sentence |
| **Total** | **< 2.5 s** | Measured and stored per turn |

Extra tricks: pre-generate the first question audio; cache audio for fixed phrases ("Great, let's move on.").

---

## 10. Folder structure

```
ai-interviewer/
├── projectprep.md          ← this file
├── apps/
│   ├── api/                ← FastAPI orchestrator (Python, uv)
│   │   ├── app/
│   │   │   ├── main.py         app setup, mounts routers
│   │   │   ├── config.py       settings from .env
│   │   │   ├── deps.py         shared dependencies (LLM clients)
│   │   │   ├── auth.py         JWT verification → CurrentUser
│   │   │   ├── db.py           asyncpg pool (one per process)
│   │   │   ├── llm.py          LLMClient interface + Groq implementation
│   │   │   ├── resume/         PDF → text → ResumeProfile, /resumes routes
│   │   │   ├── jd/             JD text → JobProfile
│   │   │   ├── analysis/       skill matching, scoring, insights, /analyses route
│   │   │   ├── interview/      state machine, turn loop, websocket (later)
│   │   │   └── speech/         STT + TTS providers (later)
│   │   └── tests/
│   └── web/                ← Next.js frontend (later)
├── supabase/migrations/    ← SQL migrations, applied in order
└── infra/                  ← docker-compose (local Postgres), Caddy (later)
```

---

## 11. Build plan (step by step)

Each step ends with something we can **run and test**.

| # | Step | Done when |
|---|---|---|
| 1 | ✅ Resume parsing API | Upload a PDF → get clean `ResumeProfile` JSON; tests pass offline |
| 2 | ✅ JD parsing + match report | Resume + JD → score, gaps, bullet rewrites |
| 3 | ✅ Supabase setup | Tables + RLS + JWT check in FastAPI; resumes and analyses saved per user |
| 4 | ✅ Frontend: login, upload, report pages | Real user can log in, upload, analyze, see report |
| 5 | ✅ Speech spike | Script measures Groq Whisper + Kokoro latency on our machine |
| 6 | ✅ TTS + WebSocket | Server can speak a question to the browser |
| 7 | ✅ STT + VAD | Browser sends an answer, server shows the transcript |
| 8 | SLM interview loop | Full voice interview with phases and follow-ups |
| 9 | Evaluation report | Rubric scores + evidence + speaking metrics |
| 10 | Deploy + limits + analytics | Live URL, quotas, PostHog |
| 11 | Launch | Share with students, collect feedback |

---

## 12. Features roadmap

- **MVP:** everything in the build plan above.
- **v1:** interview types (HR / behavioral / technical), difficulty levels, replay with transcript, progress over time.
- **v2:** coding round with editor, shareable report link, company/role question packs, user can interrupt the AI, Indian languages (AI4Bharat models).
- **Not doing:** webcam/face analysis (privacy + bias problems, little value).

---

## 13. How this goes on a resume (fill numbers from real data)

> Built a voice-based AI mock-interview platform (Next.js, FastAPI, Supabase) with a turn-based WebSocket audio pipeline (Whisper STT → streaming SLM → Kokoro TTS) achieving p95 response latency of **X s**; designed a phase-based interview orchestrator and evidence-backed rubric scoring; **Y** users completed **Z** interviews.

---

## 14. Glossary (simple words)

| Word | Meaning |
|---|---|
| **STT** | Speech-to-Text. Audio → words. |
| **TTS** | Text-to-Speech. Words → audio. |
| **SLM** | Small Language Model. A fast, cheaper AI model (here: gpt-oss-20b). |
| **VAD** | Voice Activity Detection. Knows when someone is talking vs silent. |
| **WebSocket** | A connection that stays open so server and browser can send messages anytime. |
| **JWT** | A signed login token. Proves who the user is. |
| **RLS** | Row Level Security. Database rule: "you can only see your own rows". |
| **Orchestrator** | The part of the backend that controls the interview flow. |
| **Latency** | Waiting time. Here: how long until the AI starts talking. |
| **p95** | 95% of turns are faster than this number. |
| **Prompt injection** | Hidden instructions in user text trying to trick the AI. |
| **JSONB** | Postgres column type that stores JSON and can be searched. |
