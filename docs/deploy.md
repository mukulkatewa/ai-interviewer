# Deploying AI Interviewer (free tier)

Architecture and reasons: [`projectprep.md` §5.13](../projectprep.md). About 45 minutes the first time.

```
Vercel (web)  ──►  Oracle Cloud VM: Caddy ─► API (+ job worker) ─► Kokoro TTS
                                  └─► Supabase (DB + login), Groq (LLM + Whisper)
```

## 1. Supabase (database + login)

1. Apply all migrations from your machine:
   ```bash
   bash scripts/db-push.sh --dry-run   # lists what would be applied, changes nothing
   bash scripts/db-push.sh             # applies it (asks for confirmation)
   ```
2. Authentication → URL Configuration:
   - **Site URL**: your Vercel URL, e.g. `https://ai-interviewer.vercel.app`
   - **Redirect URLs**: add `https://ai-interviewer.vercel.app/auth/callback`, and keep the localhost one for development
3. Authentication → Providers → **Google** (recommended: it is the main sign-in button, magic link is the fallback): create an OAuth client in Google Cloud Console (type *Web application*). Its authorized redirect URI is the one Supabase shows on that page.

## 2. Oracle Cloud VM (API + TTS)

1. Create an **Always Free** instance: shape `VM.Standard.A1.Flex`, **4 OCPUs, 24 GB**, image *Canonical Ubuntu 24.04*. Save the SSH key.
2. Open ports **80 and 443**, in **two** places:
   - Console: the instance's subnet → Security List → ingress rules for TCP 80 and 443 from `0.0.0.0/0`.
   - **On the VM itself.** Oracle's Ubuntu images ship iptables rules that block everything except SSH:
     ```bash
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
     sudo netfilter-persistent save
     ```
3. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER && newgrp docker
   ```
4. Code and secrets:
   ```bash
   git clone https://github.com/mukulkatewa/ai-interviewer.git && cd ai-interviewer
   nano apps/api/.env   # same keys as your local .env (template: apps/api/.env.example)
   ```
   In that `.env`, allow the web origin: `CORS_ORIGINS=["https://ai-interviewer.vercel.app"]`
5. Start. `API_DOMAIN` can be a free [sslip.io](https://sslip.io) name built from the VM's public IP:
   ```bash
   export API_DOMAIN=api.<VM-PUBLIC-IP>.sslip.io
   docker compose -f infra/docker-compose.prod.yml up -d --build
   docker compose -f infra/docker-compose.prod.yml logs -f api
   ```
6. Check: `curl https://$API_DOMAIN/health` → `{"status":"ok"}`. The first start downloads the ~3 GB Kokoro image.

**Update later:** `git pull && docker compose -f infra/docker-compose.prod.yml up -d --build`

**Latency numbers for your resume** (p50/p95 from real interviews): from your own machine, with the production `DATABASE_URL` in `apps/api/.env`, run `cd apps/api && uv run python -m bench.latency`. Benchmarks aren't shipped in the image.

## 3. Vercel (web app)

1. vercel.com → **Add New Project** → import the GitHub repo → **Root Directory: `apps/web`**.
2. Environment variables (Production):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://<project-ref>.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_…` |
   | `NEXT_PUBLIC_API_URL` | `https://api.<VM-PUBLIC-IP>.sslip.io` |
   | `NEXT_PUBLIC_POSTHOG_KEY` (optional) | your PostHog project key |

3. Deploy. If the final URL differs from what you used in 1.2 and 2.4, update the Supabase URLs and `CORS_ORIGINS`, then rerun `docker compose … up -d` on the VM.

## 4. Smoke test against production

```bash
cd apps/web
set -a; source ../api/.env; set +a
E2E_WEB_URL=https://ai-interviewer.vercel.app E2E_API_URL=https://$API_DOMAIN \
  npm run e2e -- --grep-invert @slow
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser console: CORS error | `CORS_ORIGINS` doesn't exactly match the Vercel URL (scheme included, no trailing slash) |
| Caddy log: certificate errors | Ports 80/443 not open in *both* the security list and iptables |
| Login loops back to `/login?error=callback` | The Vercel `/auth/callback` URL isn't in Supabase Redirect URLs |
| Interviewer has a robotic voice | Kokoro is down or still starting: `docker compose … logs kokoro`. The browser voice is the fallback (D26) |
| "Our AI is at capacity" | Groq free-tier rate limit; it recovers within a minute |
| "You've reached today's limit" | Per-user daily limits (D32); tune `LIMIT_*_PER_DAY` in `apps/api/.env` |


## Keep the free database awake

Free Supabase projects are paused after about a week without database activity. The repo includes a scheduled GitHub Action that prevents it (D39).

1. Apply the migration: `./scripts/db-push.sh`.
2. In GitHub: repo → **Settings → Secrets and variables → Actions → Variables** → add two *variables* (not secrets; both values are public):
   - `SUPABASE_URL` = `https://<project-ref>.supabase.co`
   - `SUPABASE_PUBLISHABLE_KEY` = your publishable key (`sb_publishable_...`)
   Or from a terminal: `gh variable set SUPABASE_URL --body "https://<project-ref>.supabase.co"` and the same for the key.
3. Test it once: **Actions → Keep Supabase awake → Run workflow**. Green means it worked. Or from your machine:
   ```
   curl -X POST "$SUPABASE_URL/rest/v1/rpc/keepalive" -H "apikey: $SUPABASE_PUBLISHABLE_KEY" -H "Content-Type: application/json" -d '{}'
   ```
   It returns a timestamp.
4. Optional second layer, inside Supabase itself: **Database → Extensions → enable `pg_cron`**, then in the SQL editor:
   ```sql
   select cron.schedule('keepalive', '0 4 * * *', $$ select public.keepalive() $$);
   ```
5. If a project is ever paused anyway, Supabase keeps the data for a while and you restore it with one click in the dashboard.

Check the Actions tab once a month: GitHub turns off scheduled workflows in a public repo after 60 days without any push.


## Backups (D45)

On the VM, as the user that runs Docker:

```
crontab -e
# every night at 03:00
0 3 * * * cd ~/ai-interviewer && ./scripts/backup.sh >> ~/backup.log 2>&1
```

Files land in `~/db-backups` (14 days kept). **Copy them off the VM** now and then (or `rclone` them to free cloud storage): a backup on the same disk is not a backup against losing the VM.

Practice the restore once on a scratch database, before you need it:
```
./scripts/restore.sh "postgresql://postgres:postgres@localhost:54329/scratch" ~/db-backups/<stamp>-users.sql.gz ~/db-backups/<stamp>-app.sql.gz
```

## Monitoring

- **Uptime:** point a free monitor (UptimeRobot, Better Stack) at `https://<API_DOMAIN>/ready`. It returns 503 when the database is unreachable and stays 200 when only text-to-speech is down (interviews fall back to the browser's voice).
- **Errors:** create a free Sentry project, put its DSN in `apps/api/.env` as `SENTRY_DSN`, and `docker compose ... up -d`.
- **Capacity:** run `uv run python -m bench.tts_concurrency` on the VM, then set `MAX_LIVE_INTERVIEWS` to the largest number of simultaneous interviews whose p50 stays under about 5 s.
- **Second providers (optional):** fill `FALLBACK_LLM_*` / `FALLBACK_STT_*` in `.env`. Try one interview with Groq's key removed to see the fallback working before you rely on it.
