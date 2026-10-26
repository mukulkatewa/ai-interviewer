# AI Interviewer

Free, voice-based mock interviews personalized to your resume and a job description, with an evidence-based feedback report.

Design decisions and architecture: [`projectprep.md`](projectprep.md).

## Status

| Step | |
|---|---|
| Resume parsing | ✅ |
| Resume ↔ JD analysis | ✅ |
| Auth (Supabase JWT) + persistence | ✅ |
| Frontend, voice interview, evaluation | in progress |

## Run the API locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cd apps/api
cp .env.example .env        # fill in GROQ_API_KEY, SUPABASE_URL, DATABASE_URL
uv sync
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000/docs.

## Database migrations

SQL files live in `supabase/migrations/` and are applied in order:

```bash
npx supabase db push --db-url "$DATABASE_URL"
```

## Tests

Tests use a fake LLM (no API key or network) and a throwaway local Postgres built from the same migrations:

```bash
docker compose -f infra/docker-compose.yml up -d
cd apps/api && uv run pytest
```
