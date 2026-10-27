# AI Interviewer

Free, voice-based mock interviews personalized to your resume and a job description, with an evidence-based feedback report.

1. **Upload a resume**: parsed into structured data.
2. **Paste a job description**: match score, missing skills, stronger resume bullets.
3. **Practice the interview by voice**: an AI interviewer asks about *your* projects and *this* job's gaps, and follows up when an answer is vague.
4. **Get a report**: competency scores with quotes from your own answers, question-by-question feedback, and speaking metrics.

Everything runs on free tiers: Groq (LLM + Whisper), self-hosted Kokoro TTS, Supabase, Vercel, an Oracle Cloud free VM.

**Design decisions and architecture: [`projectprep.md`](projectprep.md)** (D1–D32, each with what was chosen, why, and what was given up).
Measured speech latency: [`docs/benchmarks/`](docs/benchmarks/). Deploying: [`docs/deploy.md`](docs/deploy.md). Launching: [`docs/launch.md`](docs/launch.md).

## Architecture

```
Browser (Next.js 16) ── HTTPS ──► FastAPI ──► Groq: gpt-oss-120b (plans, reports), gpt-oss-20b (live turns), Whisper
   mic → Silero VAD    ── WSS ───►  ├─ interview state machine (code owns structure, model writes words)
   gapless audio queue              ├─ Kokoro TTS, sentence by sentence while the model streams
                                    ├─ Postgres job queue (outbox + SKIP LOCKED) for reports
                                    └─► Supabase Postgres (RLS-locked) + Auth (JWT verified locally)
```

## Repository

```
apps/api        FastAPI service (Python 3.12, uv): app/, tests/, bench/
apps/web        Next.js app (TypeScript, Tailwind, shadcn/ui): src/, e2e/
supabase/       SQL migrations, applied in order
infra/          docker-compose (local services, production stack), Caddyfile
docs/           benchmarks, deploy guide, launch checklist
```

## Run locally

Requires Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22+, Docker.

```bash
# Postgres (tests) + Kokoro TTS (the interviewer's voice; ~3 GB image)
docker compose -f infra/docker-compose.yml --profile speech up -d

# API: http://localhost:8000/docs
cd apps/api
cp .env.example .env          # GROQ_API_KEY, SUPABASE_URL, DATABASE_URL
uv sync && uv run uvicorn app.main:app --reload

# Web: http://localhost:3000
cd apps/web
cp .env.example .env.local    # Supabase URL + publishable key, API URL
npm install && npm run dev
```

Without Kokoro, interviews still work: the browser's built-in voice reads the questions (D26).
After changing API models, run `npm run gen:api` to regenerate the TypeScript types.

**Supabase login setup** (dashboard → Authentication): add `http://localhost:3000/auth/callback` to *Redirect URLs*; optionally enable *Google*.

**Migrations:** `npx supabase@2 db push --db-url "$DATABASE_URL"`

## Tests

| Suite | Command | Needs |
|---|---|---|
| API (unit + integration) | `cd apps/api && uv run pytest` | Local Postgres (`docker compose … up -d postgres`). Fakes for Groq, Whisper, Kokoro |
| API lint/format | `uv run ruff check && uv run ruff format --check` | none |
| Web types/lint/build | `cd apps/web && npx tsc --noEmit && npm run lint && npm run build` | none |
| End-to-end (real browser, fake mic) | `cd apps/web && npm run e2e` | The running stack + Supabase keys, see `e2e/support.ts` |

CI runs everything except end-to-end on every push and pull request.
