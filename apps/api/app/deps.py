"""Shared FastAPI dependencies.

Providers are cached: the process holds one Groq connection pool, and one
lightweight client per job on top of it. Tests swap them via
`app.dependency_overrides`.
"""

from functools import lru_cache

import groq
from starlette.requests import HTTPConnection

from app.config import get_settings
from app.llm import GroqClient, LLMClient, create_groq
from app.speech.tts import TTSProvider


@lru_cache
def get_groq() -> groq.AsyncGroq:
    return create_groq(get_settings().groq_api_key)


# One provider per job, each with its own model, so jobs draw on separate
# per-model rate limits (projectprep.md, D22).


@lru_cache
def get_resume_llm() -> LLMClient:
    s = get_settings()
    return GroqClient(get_groq(), s.groq_resume_model, s.groq_resume_effort)


@lru_cache
def get_jd_llm() -> LLMClient:
    s = get_settings()
    return GroqClient(get_groq(), s.groq_jd_model, s.groq_jd_effort)


@lru_cache
def get_analysis_llm() -> LLMClient:
    s = get_settings()
    return GroqClient(get_groq(), s.groq_analysis_model, s.groq_analysis_effort)


def get_tts(conn: HTTPConnection) -> TTSProvider:
    # Created in the app lifespan, which also closes its HTTP client on shutdown.
    return conn.app.state.tts
