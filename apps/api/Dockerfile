# AI Interviewer API (projectprep.md 5.13). Multi-arch: builds on the Oracle ARM VM as-is.
#   docker build -t ai-interviewer-api apps/api

# --- build: exactly the locked dependencies, in a venv -----------------------------
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first: this layer stays cached until uv.lock changes, so code edits rebuild in seconds.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app

# --- runtime: Python, the venv and the code, as a non-root user --------------------
FROM python:3.12-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
# One process on purpose: live sessions (D30) and the job worker (D31) live in memory.
# --proxy-headers: client IP and https scheme come through Caddy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
