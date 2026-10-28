"""Speech-to-text behind a tiny interface (D9). Production uses Groq Whisper."""

import time
from typing import Any, Protocol

import groq
from pydantic import BaseModel


class STTError(RuntimeError):
    """Transcription failed. The candidate is asked to answer again."""


class STTBusyError(STTError):
    """Groq's free-tier limit (20 req/min, audio-seconds/hour) is hit; retry later."""


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    text: str
    # Timestamps let phase 9 compute speaking pace and long pauses without another model.
    segments: list[Segment]
    stt_ms: int


class STTProvider(Protocol):
    async def transcribe(self, wav: bytes, prompt: str | None = None) -> Transcript: ...


class GroqWhisper:
    # Any SDK with the same `audio.transcriptions.create` shape works (see app/fallback.py).
    _rate_limit: type[Exception] = groq.RateLimitError
    _api_error: type[Exception] = groq.APIError

    def __init__(self, client: Any, model: str):
        self._client = client  # the app's shared AsyncGroq: one connection pool
        self._model = model

    async def transcribe(self, wav: bytes, prompt: str | None = None) -> Transcript:
        extra = {"prompt": prompt} if prompt else {}
        started = time.perf_counter()
        try:
            result = await self._client.audio.transcriptions.create(
                file=("answer.wav", wav),
                model=self._model,
                language="en",  # skips language detection: faster, and no mis-detected accents
                temperature=0,
                response_format="verbose_json",
                **extra,
            )
        except self._rate_limit as e:
            raise STTBusyError(str(e)) from e
        except self._api_error as e:
            raise STTError(str(e)) from e

        # verbose_json segments come back as dicts on Groq; be lenient about the shape.
        raw_segments = getattr(result, "segments", None) or []
        segments = [
            Segment(start=s["start"], end=s["end"], text=s["text"].strip())
            for s in (seg if isinstance(seg, dict) else seg.model_dump() for seg in raw_segments)
        ]
        return Transcript(
            text=result.text.strip(),
            segments=segments,
            stt_ms=round((time.perf_counter() - started) * 1000),
        )
