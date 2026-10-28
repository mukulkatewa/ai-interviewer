"""LLM access behind a tiny interface (projectprep.md, D9).

Feature code depends on the `LLMClient` protocol, never on Groq directly, so
tests can pass a fake and we can swap providers without touching callers.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeVar

import groq
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
ReasoningEffort = Literal["low", "medium", "high"]

DEFAULT_RETRY_AFTER_S = 30


class LLMError(RuntimeError):
    """The model failed to produce usable output after all retries."""


class LLMBusyError(LLMError):
    """The provider is rate limiting us (free-tier quota). Retrying later will work."""

    def __init__(self, retry_after_s: int):
        super().__init__(f"Rate limited; retry after {retry_after_s}s")
        self.retry_after_s = retry_after_s


class LLMClient(Protocol):
    async def complete_json(self, system: str, user: str, schema: type[T]) -> T: ...


class TextStreamer(Protocol):
    def stream_text(self, system: str, user: str) -> AsyncIterator[str]:
        """Spoken-reply text as it's generated, chunk by chunk."""
        ...


class PatientLLM:
    """Waits out a short rate limit instead of failing the request (D41).

    The free tier allows ~8k tokens a minute per model, so a user who uploads a resume and starts an
    interview straight away can brush against it. The provider says how long to wait; if that fits in
    `max_wait_s` we wait and try again, otherwise the error goes up unchanged (a 503 with Retry-After).
    Only for request-path calls: the live conversation must never stall, and the job worker has its own
    patience (D22).
    """

    def __init__(self, inner: LLMClient, max_wait_s: float, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._inner, self._max_wait_s, self._sleep = inner, max_wait_s, sleep

    async def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        waited = 0.0
        while True:
            try:
                return await self._inner.complete_json(system, user, schema)
            except LLMBusyError as e:
                if waited + e.retry_after_s > self._max_wait_s:
                    raise
                waited += e.retry_after_s
                await self._sleep(e.retry_after_s)


def create_groq(api_key: str) -> groq.AsyncGroq:
    # One retry absorbs a brief blip. More would hide a quota wall behind a
    # long silent wait (we measured 45 s); failing fast lets us tell the user (D22).
    return groq.AsyncGroq(api_key=api_key, max_retries=1)


@lru_cache
def _schema_instructions(schema: type[BaseModel]) -> str:
    # Building the JSON Schema walks the whole model; do it once per type, not per request.
    return "Respond with a single JSON object that matches this JSON Schema:\n" + json.dumps(
        schema.model_json_schema(), separators=(",", ":")
    )


def retry_after_seconds(e: Any) -> int:
    try:
        return max(1, round(float(e.response.headers.get("retry-after", ""))))
    except ValueError:
        return DEFAULT_RETRY_AFTER_S


class GroqClient:
    """One model + settings for one job (resume parsing, JD extraction, ...).

    The AsyncGroq instance is shared by all jobs: it holds the HTTP connection
    pool, so every call reuses warm connections.

    Any SDK with the same `chat.completions.create` shape works: a subclass only names its own
    error types (see app/fallback.py).
    """

    _provider = "Groq"
    _rate_limit: type[Exception] = groq.RateLimitError
    _api_error: type[Exception] = groq.APIError

    def __init__(
        self,
        client: Any,
        model: str,
        reasoning_effort: ReasoningEffort | None = None,
        max_attempts: int = 2,
    ):
        self._client = client
        self._model = model
        # Only reasoning models (e.g. gpt-oss) accept this; None omits the parameter.
        self._extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        self._max_attempts = max_attempts

    async def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        """Return the model's answer parsed into `schema`.

        JSON mode guarantees syntactically valid JSON, but not the right shape.
        If Pydantic rejects it, we show the model its own validation error and
        ask again: models usually fix a missing or mistyped field on retry.
        """
        messages = [
            {"role": "system", "content": f"{system}\n\n{_schema_instructions(schema)}"},
            {"role": "user", "content": user},
        ]
        last_error: ValidationError | None = None

        for _ in range(self._max_attempts):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,  # structured output should be repeatable, not creative
                    **self._extra,
                )
            except self._rate_limit as e:
                raise LLMBusyError(retry_after_seconds(e)) from e
            except self._api_error as e:
                raise LLMError(f"{self._provider} request failed: {e}") from e

            raw = resp.choices[0].message.content or ""
            try:
                return schema.model_validate_json(raw)
            except ValidationError as e:
                last_error = e
                messages += [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"Invalid JSON for the schema: {e}. Return only the corrected JSON."},
                ]

        raise LLMError(f"Model did not return a valid {schema.__name__}") from last_error

    async def stream_text(self, system: str, user: str) -> AsyncIterator[str]:
        """Stream a free-text reply. Used live, where first-sentence latency matters (D8)."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                temperature=0.6,  # spoken replies should vary a little, unlike extraction
                **self._extra,
            )
        except self._rate_limit as e:
            raise LLMBusyError(retry_after_seconds(e)) from e
        except self._api_error as e:
            raise LLMError(f"{self._provider} request failed: {e}") from e

        try:
            async for chunk in stream:
                # gpt-oss streams its reasoning in a separate field; only `content` is spoken.
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except self._api_error as e:
            raise LLMError(f"{self._provider} stream failed: {e}") from e
