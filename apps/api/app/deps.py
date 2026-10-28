"""Shared FastAPI dependencies.

Providers are cached: the process holds one Groq connection pool, and one
lightweight client per job on top of it. Tests swap them via
`app.dependency_overrides`.
"""

from functools import lru_cache

import groq
from starlette.requests import HTTPConnection

from app.config import get_settings
from app.llm import GroqClient, LLMClient, PatientLLM, TextStreamer, create_groq
from app.speech.stt import GroqWhisper, STTProvider
from app.speech.tts import TTSProvider


@lru_cache
def get_groq() -> groq.AsyncGroq:
    return create_groq(get_settings().groq_api_key)


# One provider per job, each with its own model, so jobs draw on separate
# per-model rate limits (projectprep.md, D22).


@lru_cache
def get_resume_llm() -> LLMClient:
    s = get_settings()
    return PatientLLM(GroqClient(get_groq(), s.groq_resume_model, s.groq_resume_effort), s.llm_patience_s)


@lru_cache
def get_jd_llm() -> LLMClient:
    s = get_settings()
    return PatientLLM(GroqClient(get_groq(), s.groq_jd_model, s.groq_jd_effort), s.llm_patience_s)


@lru_cache
def get_live_llm() -> TextStreamer:
    s = get_settings()
    return GroqClient(get_groq(), s.groq_live_model, s.groq_live_effort)


@lru_cache
def get_report_llm() -> LLMClient:
    """For the background worker: no in-request patience, it re-queues and waits as long as the provider asks."""
    s = get_settings()
    return GroqClient(get_groq(), s.groq_analysis_model, s.groq_analysis_effort)


@lru_cache
def get_analysis_llm() -> LLMClient:
    """For requests that plan an interview or write a match report."""
    return PatientLLM(get_report_llm(), get_settings().llm_patience_s)


def get_tts(conn: HTTPConnection) -> TTSProvider:
    # Created in the app lifespan, which also closes its HTTP client on shutdown.
    return conn.app.state.tts


@lru_cache
def get_stt() -> STTProvider:
    return GroqWhisper(get_groq(), get_settings().groq_stt_model)
