from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm import ReasoningEffort


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env (never hard-coded)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""

    # One model per job; each model has its own free-tier rate limit (projectprep.md, D22).
    # Model names change; check console.groq.com/docs/models.
    # Resume parsing: errors here mislead every later interview, so use the most accurate model.
    groq_resume_model: str = "openai/gpt-oss-120b"
    groq_resume_effort: ReasoningEffort = "low"
    # JD extraction: simpler task; a different model spreads the load.
    groq_jd_model: str = "openai/gpt-oss-20b"
    groq_jd_effort: ReasoningEffort = "low"
    # Live interview turns: the fastest first sentence, on its own rate limit (D7, D22).
    groq_live_model: str = "openai/gpt-oss-20b"
    groq_live_effort: ReasoningEffort = "low"
    # Advice for the user: not live, so spend more thinking on quality (D13).
    groq_analysis_model: str = "openai/gpt-oss-120b"
    groq_analysis_effort: ReasoningEffort = "medium"

    # e.g. https://<project-ref>.supabase.co. Only public values derive from it (D16).
    supabase_url: str = ""
    # Supabase "Session pooler" connection string (projectprep.md, D15).
    database_url: str = ""
    db_pool_max_size: int = 5  # free-tier pooler allows few connections; keep headroom

    max_upload_bytes: int = 5 * 1024 * 1024

    # Kokoro-FastAPI (infra/docker-compose.yml, profile "speech"); D23.
    kokoro_url: str = "http://localhost:8880"
    kokoro_voice: str = "af_heart"
    # Which speech engine runs (D47): "kokoro" (a separate service, needs ~4 CPUs) or "piper" (in this
    # process, fine on 1 CPU). Piper also needs the voice file: scripts/get-piper-voice.sh.
    tts_engine: Literal["kokoro", "piper"] = "kokoro"
    piper_voice_path: str = "voices/en_US-lessac-medium.onnx"
    # A sentence takes ~0.6-4 s on 4 CPUs (benchmark); past this, fall back to browser speech (D26).
    tts_timeout_s: float = 15.0
    # Speech-to-text (benchmarked in docs/benchmarks/speech-2026-10-27.md).
    # large-v3 over the faster "turbo": noticeably better on accented English and proper nouns, and on Groq
    # both run far faster than real time (~190x vs ~215x), so the extra latency is tens of milliseconds (D48).
    groq_stt_model: str = "whisper-large-v3"
    # Interview length cap (D12): checked every turn; past it, the interview wraps up.
    interview_max_minutes: float = 20.0
    # Per-user limits per rolling 24 h (D12, D32). Checked before any LLM spend.
    limit_resumes_per_day: int = 10
    limit_analyses_per_day: int = 10
    limit_interviews_per_day: int = 3
    # Optional second providers (D46): used when the main one is rate limited or failing. Any service with an
    # OpenAI-style API works, e.g. Cerebras (https://api.cerebras.ai/v1) for the model, or an OpenAI-style
    # Whisper endpoint for speech. Leave blank to turn off.
    fallback_llm_base_url: str = ""
    fallback_llm_api_key: str = ""
    fallback_llm_model: str = ""
    fallback_llm_effort: ReasoningEffort | None = "low"  # set empty for models without reasoning_effort
    fallback_stt_base_url: str = ""
    fallback_stt_api_key: str = ""
    fallback_stt_model: str = "whisper-1"
    # Longest we wait on a rate limit inside one request before answering 503 (D41).
    llm_patience_s: float = 20.0
    # How the feedback report is produced (D38): "single" = one model call, "graph" = LangGraph pipeline.
    report_engine: Literal["single", "graph"] = "single"
    # Error tracking (D44): off unless a DSN is set. `environment` just labels events.
    sentry_dsn: str = ""
    environment: str = "development"
    log_level: str = "INFO"
    # Run the background job worker in this process (D31). Off in tests, which drive it directly.
    run_jobs: bool = True
    # How long a new interview WebSocket may stay open without sending `auth`.
    ws_auth_timeout_s: float = 10.0
    # Connection limits (D42). Per client address, and live interviews across the whole server.
    # Measured (docs/benchmarks/tts-concurrency-2026-10-29.md): Kokoro on 4 CPUs slows almost in
    # proportion to the number of interviews, so 2 is the honest default. Re-measure on the production VM.
    ws_max_per_ip: int = 20
    max_live_interviews: int = 2

    # Browser origins allowed to call the API (D19). JSON list in env, e.g.
    # CORS_ORIGINS='["https://app.example.com"]'. Never "*": we send credentials.
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return f"{self.jwt_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    # Parse .env once per process instead of on every request.
    return Settings()
