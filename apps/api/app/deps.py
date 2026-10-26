"""Shared FastAPI dependencies.

Each provider is cached so the process holds one client (one connection pool)
per role. Tests swap them out via `app.dependency_overrides`.
"""

from functools import lru_cache

from app.config import get_settings
from app.llm import GroqClient, LLMClient


@lru_cache
def get_extraction_llm() -> LLMClient:
    s = get_settings()
    return GroqClient(s.groq_api_key, s.groq_extraction_model, s.groq_extraction_effort)


@lru_cache
def get_analysis_llm() -> LLMClient:
    s = get_settings()
    return GroqClient(s.groq_api_key, s.groq_analysis_model, s.groq_analysis_effort)
