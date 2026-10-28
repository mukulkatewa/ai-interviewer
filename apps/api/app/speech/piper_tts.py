"""Text-to-speech that runs inside the API process: Piper (D47).

Why: Kokoro needs about 4 CPUs (docs/benchmarks/tts-concurrency-2026-10-29.md). The free Oracle VM has 1.
Piper's `lessac-medium` voice measured on that VM: a 17-word sentence in 0.94 s (5x faster than real time),
65 MB of memory, no separate service. The voice is a little less rich than Kokoro's and far better than
silence. Installed with the `piper` extra: `uv sync --extra piper`.

Returns WAV (the browser decodes any format; WAV needs no encoder). One sentence at a time on one worker
thread: on a single core, parallel synthesis would just make every sentence slower.
"""

import asyncio
import contextlib
import io
import logging
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.speech.tts import TTSError

logger = logging.getLogger(__name__)


def _load_piper(model_path: str) -> Any:
    from piper import PiperVoice  # imported here: the `piper` extra is optional

    return PiperVoice.load(model_path)


class PiperTTS:
    def __init__(self, model_path: str, loader: Callable[[str], Any] = _load_piper):
        self._model_path = model_path
        self._loader = loader
        self._voice: Any = None
        self._lock = asyncio.Lock()  # one synthesis at a time

    def _ensure_loaded(self) -> Any:
        if self._voice is None:
            if not Path(self._model_path).is_file():
                raise TTSError(f"Piper voice not found: {self._model_path} (run scripts/get-piper-voice.sh)")
            self._voice = self._loader(self._model_path)
        return self._voice

    def _synthesize_blocking(self, text: str) -> bytes:
        voice = self._ensure_loaded()
        buffer = io.BytesIO()
        wav = wave.open(buffer, "wb")  # noqa: SIM115 - closed explicitly below, see the comment
        try:
            voice.synthesize_wav(text, wav)
        except BaseException:
            # Closing a WAV that never got its format raises its own error and would hide the real one.
            with contextlib.suppress(wave.Error):
                wav.close()
            raise
        wav.close()
        return buffer.getvalue()

    async def synthesize(self, text: str) -> bytes:
        async with self._lock:
            try:
                audio = await asyncio.to_thread(self._synthesize_blocking, text)
            except TTSError:
                raise
            except Exception as e:  # noqa: BLE001 - any engine failure becomes "use the browser voice" (D26)
                raise TTSError(f"Piper failed: {e}") from e
        if len(audio) <= 44:  # a WAV header alone: nothing was spoken
            raise TTSError("Piper returned no audio")
        return audio

    async def healthy(self) -> bool:
        """Can we speak? Loads the voice once, which also warms it up before the first interview."""
        try:
            await asyncio.to_thread(self._ensure_loaded)
        except Exception as e:  # noqa: BLE001
            logger.warning("Piper not ready: %s", e)
            return False
        return True
