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

    max_upload_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    # Parse .env once per process instead of on every request.
    return Settings()
