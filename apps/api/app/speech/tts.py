"""Text-to-speech behind a tiny interface (D9). Production uses Kokoro (D23)."""

from typing import Protocol

import httpx


class TTSError(RuntimeError):
    """TTS is down, slow, or returned nothing. Callers fall back to browser speech (D26)."""


class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> bytes:
        """One sentence of text -> MP3 bytes."""
        ...


class KokoroTTS:
    """Client for Kokoro-FastAPI's OpenAI-compatible /v1/audio/speech endpoint.

    We ask for a whole sentence at a time (not Kokoro's streaming mode):
    the benchmark showed Kokoro returns a sentence's audio all at once anyway,
    and a complete MP3 per sentence is what the browser decodes most easily.
    """

    def __init__(self, http: httpx.AsyncClient, base_url: str, voice: str):
        self._http = http
        self._url = f"{base_url.rstrip('/')}/v1/audio/speech"
        self._voice = voice

    async def synthesize(self, text: str) -> bytes:
        body = {"model": "kokoro", "input": text, "voice": self._voice, "response_format": "mp3"}
        try:
            resp = await self._http.post(self._url, json=body)
            resp.raise_for_status()
        except httpx.HTTPError as e:  # connection refused, timeout, 4xx/5xx
            raise TTSError(f"Kokoro request failed: {e}") from e
        if not resp.content:
            raise TTSError("Kokoro returned no audio")
        return resp.content
