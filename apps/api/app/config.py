from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm import ReasoningEffort


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env (never hard-coded)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""

    # Model names change; check console.groq.com/docs/models.
    # Extraction: turn text into JSON. Simple task, so think little (projectprep.md, D13).
    groq_extraction_model: str = "openai/gpt-oss-20b"
    groq_extraction_effort: ReasoningEffort = "low"
    # Analysis: write advice for the user. Not live, so spend more thinking on quality.
    groq_analysis_model: str = "openai/gpt-oss-120b"
    groq_analysis_effort: ReasoningEffort = "medium"

    # e.g. https://<project-ref>.supabase.co. Only public values derive from it (D16).
    supabase_url: str = ""
    # Supabase "Session pooler" connection string (projectprep.md, D15).
    database_url: str = ""
    db_pool_max_size: int = 5  # free-tier pooler allows few connections; keep headroom

    max_upload_bytes: int = 5 * 1024 * 1024

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
