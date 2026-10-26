"""LLM access behind a tiny interface (projectprep.md, D9).

Feature code depends on the `LLMClient` protocol, never on Groq directly, so
tests can pass a fake and we can swap providers without touching callers.
"""

import json
from functools import lru_cache
from typing import Protocol, TypeVar

from groq import AsyncGroq
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model failed to produce usable output after all retries."""


class LLMClient(Protocol):
    async def complete_json(self, system: str, user: str, schema: type[T]) -> T: ...


@lru_cache
def _schema_instructions(schema: type[BaseModel]) -> str:
    # Building the JSON Schema walks the whole model; do it once per type, not per request.
    return (
        "Respond with a single JSON object that matches this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), separators=(",", ":"))
    )


class GroqClient:
    def __init__(self, api_key: str, model: str, max_attempts: int = 2):
        # One AsyncGroq instance holds one HTTP connection pool; create it once
        # per process and reuse it so each call skips the TCP/TLS handshake.
        self._client = AsyncGroq(api_key=api_key)
        self._model = model
        self._max_attempts = max_attempts

    async def complete_json(self, system: str, user: str, schema: type[T]) -> T:
        """Return the model's answer parsed into `schema`.

        JSON mode guarantees syntactically valid JSON, but not the right shape.
        If Pydantic rejects it, we show the model its own validation error and
        ask again: small models usually fix a missing or mistyped field on retry.
        """
        messages = [
            {"role": "system", "content": f"{system}\n\n{_schema_instructions(schema)}"},
            {"role": "user", "content": user},
        ]
        last_error: ValidationError | None = None

        for _ in range(self._max_attempts):
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,  # extraction should be repeatable, not creative
            )
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
