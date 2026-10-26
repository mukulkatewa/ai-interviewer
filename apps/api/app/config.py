from functools import lru_cache

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
    # A sentence takes ~0.6-4 s on 4 CPUs (benchmark); past this, fall back to browser speech (D26).
    tts_timeout_s: float = 15.0
    # How long a new interview WebSocket may stay open without sending `auth`.
    ws_auth_timeout_s: float = 10.0

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
