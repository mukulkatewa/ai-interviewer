# Launch checklist (phase 11)

From "deployed" to "real users", in order. Deployment itself: [`deploy.md`](deploy.md).

## 1. Before inviting anyone

- [ ] **Rotate every key that was ever pasted in a chat or terminal log**: Groq API key, Supabase secret key, database password. Update `apps/api/.env` on the VM and run `docker compose … up -d`.
- [ ] `curl https://<API_DOMAIN>/health` returns `{"status":"ok"}`, and the browser shows a valid HTTPS padlock on both the web app and the API.
- [ ] Smoke test passes against production (`deploy.md` §4), including the `@slow` interview once.
- [ ] Sign in on a phone (Chrome Android, Safari iOS): mic permission prompt, interviewer voice, answer captured.
- [ ] Supabase → Authentication → Rate limits: the built-in email sender allows only a few emails per hour. For more than a handful of magic-link users, enable Google sign-in (doesn't use email) or add a free SMTP provider (Resend's free tier works).
- [ ] Limits match your free tiers (`LIMIT_*_PER_DAY`, D32). Groq allows 1,000 requests/day **per model**. A full interview uses ~10 live-model calls and 1 plan + 1 report call on the 120B model. So roughly **80–100 interviews a day** fit, before Whisper's 28,800 audio-seconds/day limit (≈ 8 hours of answers).
- [ ] PostHog key set on Vercel if you want usage numbers (optional, anonymous).
- [ ] Privacy: the landing page or footer says what is stored (resume text, transcripts, reports), that audio is not stored, and that "Delete all my data" is on the dashboard.

## 2. First users (week 1)

Small and close first: you want feedback before scale.

- [ ] 5–10 friends or classmates preparing for placements. Watch one of them use it (screen share) without helping. Note every place they hesitate.
- [ ] Ask each one: *What was the most useful part? What felt wrong or slow?* Write the answers down.
- [ ] Check the API logs for errors: `docker compose -f infra/docker-compose.prod.yml logs api | grep -E "ERROR|Traceback"`.
- [ ] Check reports for odd scores: read 5 transcripts next to their reports. Are the quotes and scores fair?

## 3. Wider launch (week 2–3)

- [ ] Fix the top 3 problems from week 1 first.
- [ ] Post where students prepare for interviews: your college's placement groups, LinkedIn (a short demo video of a real interview works best), r/developersIndia, r/cscareerquestions.
- [ ] Product Hunt or Peerlist launch: post on a Tuesday–Thursday morning (US time) with the demo video and 3 screenshots (report, live interview, match report).
- [ ] Reply to every comment and feedback message within a day.

## 4. Watch these numbers

| Number | Where | Healthy |
|---|---|---|
| Interviews completed / started | PostHog `interview_completed` ÷ `interview_started` | > 60% |
| Report failures | `select status, count(*) from interviews group by status` | `failed` < 2% |
| Turn latency p50 / p95 | `uv run python -m bench.latency` | p95 first sentence < 2 s |
| Groq 429s | API logs: "at capacity" | Rare. If frequent, lower the limits |

## 5. Put it on your resume (with real numbers)

After the first ~50 interviews, run `uv run python -m bench.latency` and count users and interviews in Supabase. Then fill in:

> Built a voice-based AI mock-interview platform (Next.js, FastAPI, Postgres, WebSockets) used by **N** students for **M** interviews.
> Streamed Whisper STT → LLM → Kokoro TTS sentence by sentence for a **p50 X s / p95 Y s** response time on free-tier infrastructure.
> Designed a code-enforced interview state machine and a Postgres job queue (transactional outbox, `SKIP LOCKED`), with evidence-verified LLM scoring.

Link the repo and `projectprep.md`: the design decisions (D1–D32) are the strongest interview talking points.
