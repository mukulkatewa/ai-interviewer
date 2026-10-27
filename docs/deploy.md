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
3. Authentication → Providers → **Google** (optional): create an OAuth client in Google Cloud Console (type *Web application*). Its authorized redirect URI is the one Supabase shows on that page.

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
