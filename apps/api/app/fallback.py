"""A second provider behind the same interfaces (D46), so one free tier running dry is not an outage.

Both pieces are optional: with no FALLBACK_* settings nothing here is used and behavior is unchanged.
- `OpenAICompatClient` / `OpenAICompatWhisper`: any service with an OpenAI-style API (Cerebras, OpenRouter,
  Gemini's compatible endpoint, Fireworks, ...). They reuse the Groq classes' logic; only the SDK's
  error types differ.
- `FallbackLLM` / `FallbackSTT`: try the main provider; if it is rate limited or fails, try the second.
"""

import logging
from collections.abc import AsyncIterator

import openai
from pydantic import BaseModel

from app.llm import GroqClient, LLMClient, LLMError, TextStreamer
from app.speech.stt import GroqWhisper, STTError, STTProvider, Transcript

logger = logging.getLogger(__name__)


class OpenAICompatClient(GroqClient):
    _provider = "Fallback LLM"
    _rate_limit = openai.RateLimitError
    _api_error = openai.APIError


class OpenAICompatWhisper(GroqWhisper):
    _rate_limit = openai.RateLimitError
    _api_error = openai.APIError


class FallbackLLM:
    """Main provider first. Rate limited or failed: the second one answers instead."""

    def __init__(self, primary: LLMClient, secondary: LLMClient):
        self._primary, self._secondary = primary, secondary

    async def complete_json[T: BaseModel](self, system: str, user: str, schema: type[T]) -> T:
        try:
            return await self._primary.complete_json(system, user, schema)
        except LLMError as e:  # includes LLMBusyError
            logger.warning("main LLM failed (%s); using the fallback", e)
            return await self._secondary.complete_json(system, user, schema)

    async def stream_text(self, system: str, user: str) -> AsyncIterator[str]:
        """Falls back only if the main provider failed before saying anything: half a sentence from one
        model followed by a whole answer from another would be spoken twice."""
        spoke = False
        try:
            async for chunk in self._primary.stream_text(system, user):  # type: ignore[attr-defined]
                spoke = True
                yield chunk
            return
        except LLMError as e:
            if spoke:
                raise
            logger.warning("main LLM failed before replying (%s); using the fallback", e)
        async for chunk in self._secondary.stream_text(system, user):  # type: ignore[attr-defined]
            yield chunk


class FallbackSTT:
    def __init__(self, primary: STTProvider, secondary: STTProvider):
        self._primary, self._secondary = primary, secondary

    async def transcribe(self, wav: bytes, prompt: str | None = None) -> Transcript:
        try:
            return await self._primary.transcribe(wav, prompt)
        except STTError as e:  # includes STTBusyError
            logger.warning("main speech-to-text failed (%s); using the fallback", e)
            return await self._secondary.transcribe(wav, prompt)


__all__ = ["FallbackLLM", "FallbackSTT", "OpenAICompatClient", "OpenAICompatWhisper", "TextStreamer"]
