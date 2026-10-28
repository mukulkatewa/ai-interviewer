"""Shared FastAPI dependencies.

Providers are cached: the process holds one Groq connection pool, and one
lightweight client per job on top of it. Tests swap them via
`app.dependency_overrides`.
"""

from functools import lru_cache

import groq
import openai
from starlette.requests import HTTPConnection

from app.config import get_settings
from app.fallback import FallbackLLM, FallbackSTT, OpenAICompatClient, OpenAICompatWhisper
from app.llm import GroqClient, LLMClient, PatientLLM, TextStreamer, create_groq
from app.speech.stt import GroqWhisper, STTProvider
from app.speech.tts import TTSProvider


@lru_cache
def get_groq() -> groq.AsyncGroq:
    return create_groq(get_settings().groq_api_key)


@lru_cache
def get_fallback_client() -> openai.AsyncOpenAI | None:
    s = get_settings()
    if not (s.fallback_llm_base_url and s.fallback_llm_api_key and s.fallback_llm_model):
        return None
    return openai.AsyncOpenAI(base_url=s.fallback_llm_base_url, api_key=s.fallback_llm_api_key, max_retries=1)


def with_fallback(primary):  # noqa: ANN001, ANN201 - one helper for LLMClient and TextStreamer providers
    """Wrap a Groq provider so the second provider answers when it is rate limited (no-op when not configured)."""
    client = get_fallback_client()
    if client is None:
        return primary
    s = get_settings()
    return FallbackLLM(primary, OpenAICompatClient(client, s.fallback_llm_model, s.fallback_llm_effort))


# One provider per job, each with its own model, so jobs draw on separate
# per-model rate limits (projectprep.md, D22).


@lru_cache
def get_resume_llm() -> LLMClient:
    s = get_settings()
    return PatientLLM(
        with_fallback(GroqClient(get_groq(), s.groq_resume_model, s.groq_resume_effort)), s.llm_patience_s
    )


@lru_cache
def get_jd_llm() -> LLMClient:
    s = get_settings()
    return PatientLLM(with_fallback(GroqClient(get_groq(), s.groq_jd_model, s.groq_jd_effort)), s.llm_patience_s)


@lru_cache
def get_live_llm() -> TextStreamer:
    s = get_settings()
    return with_fallback(GroqClient(get_groq(), s.groq_live_model, s.groq_live_effort))


@lru_cache
def get_report_llm() -> LLMClient:
    """For the background worker: no in-request patience, it re-queues and waits as long as the provider asks."""
    s = get_settings()
    return with_fallback(GroqClient(get_groq(), s.groq_analysis_model, s.groq_analysis_effort))


@lru_cache
def get_analysis_llm() -> LLMClient:
    """For requests that plan an interview or write a match report."""
    return PatientLLM(get_report_llm(), get_settings().llm_patience_s)


def get_tts(conn: HTTPConnection) -> TTSProvider:
    # Created in the app lifespan, which also closes its HTTP client on shutdown.
    return conn.app.state.tts


@lru_cache
def get_stt() -> STTProvider:
    s = get_settings()
    main = GroqWhisper(get_groq(), s.groq_stt_model)
    if not (s.fallback_stt_base_url and s.fallback_stt_api_key):
        return main
    client = openai.AsyncOpenAI(base_url=s.fallback_stt_base_url, api_key=s.fallback_stt_api_key, max_retries=1)
    return FallbackSTT(main, OpenAICompatWhisper(client, s.fallback_stt_model))
