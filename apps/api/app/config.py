from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env (never hard-coded)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    # Small, fast model for extraction. Names change; check console.groq.com/docs/models.
    groq_extraction_model: str = "openai/gpt-oss-20b"
    max_upload_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    # Parse .env once per process instead of on every request.
    return Settings()
