"""Everything the interviewer says goes out through here (protocol: projectprep.md, 6).

A reply is `reply_start`, then one `sentence` per sentence, each followed by its
MP3 when TTS worked. When it didn't, the sentence is sent as text only and the
browser speaks it (D26).
"""

import logging
import re
import time
from collections.abc import AsyncIterable, Iterable

from fastapi import WebSocket

from app.speech.text import split_sentences
from app.speech.tts import TTSError, TTSProvider

logger = logging.getLogger(__name__)

TTS_COOLDOWN_S = 60.0  # after a TTS failure, skip TTS this long (circuit breaker)

# Played the instant an answer is transcribed: 0 ms of TTS once cached (D23).
ACKNOWLEDGEMENTS = ("Got it.", "Okay.", "Thanks.", "Makes sense.", "Alright.")
_ack_audio: dict[str, bytes] = {}  # process-wide: same phrases for every interview

# Models write typographic dashes ("trade‑offs") that TTS may read oddly.
_DASHES = re.compile(r"[‐-―]")


def for_speech(text: str) -> str:
    return _DASHES.sub("-", text)


class Speaker:
    def __init__(self, ws: WebSocket, tts: TTSProvider):
        self.ws = ws
        self.tts = tts
        self._tts_down_until = 0.0

    async def reply(
        self, sentences: AsyncIterable[str] | Iterable[str], acknowledgement: str | None = None
    ) -> tuple[str, int | None]:
        """Speak sentences as they arrive. Returns (full text, TTS ms for the first sentence).

        `sentences` can be a live LLM stream. Iterating it sequentially is still
        pipelined: while we synthesize sentence N, the LLM's next tokens keep
        arriving into the HTTP buffer, so sentence N+1 is usually ready at once.
        """
        first_tts_ms: int | None = None
        spoken: list[str] = []
        await self.ws.send_json({"type": "reply_start"})

        seq = 0
        if acknowledgement:
            await self._send_sentence(seq, acknowledgement, await self._ack_audio(acknowledgement))
            seq += 1
        async for sentence in _aiter(sentences):
            sentence = for_speech(sentence)
            synth_started = time.perf_counter()
            audio = await self._synthesize(sentence)
            if first_tts_ms is None and audio is not None:
                first_tts_ms = round((time.perf_counter() - synth_started) * 1000)
            await self._send_sentence(seq, sentence, audio)
            spoken.append(sentence)
            seq += 1
        return " ".join(spoken), first_tts_ms

    async def say(self, text: str) -> str:
        """Speak a fixed line (intro, closing). Returns the text spoken."""
        spoken, _ = await self.reply(split_sentences(text))
        return spoken

    async def _send_sentence(self, seq: int, text: str, audio: bytes | None) -> None:
        # Order matters: the client pairs a binary frame with the sentence before it.
        await self.ws.send_json({"type": "sentence", "seq": seq, "text": text, "audio": audio is not None})
        if audio is not None:
            await self.ws.send_bytes(audio)

    async def _synthesize(self, text: str) -> bytes | None:
        if time.monotonic() < self._tts_down_until:
            return None  # breaker open: don't add a timeout to every sentence
        try:
            return await self.tts.synthesize(text)
        except TTSError as e:
            logger.warning("TTS failed, using browser voice for %.0f s: %s", TTS_COOLDOWN_S, e)
            self._tts_down_until = time.monotonic() + TTS_COOLDOWN_S
            return None

    async def _ack_audio(self, phrase: str) -> bytes | None:
        if phrase not in _ack_audio:
            audio = await self._synthesize(phrase)
            if audio is None:
                return None
            _ack_audio[phrase] = audio
        return _ack_audio[phrase]


async def _aiter(items: AsyncIterable[str] | Iterable[str]):
    if isinstance(items, AsyncIterable):
        async for item in items:
            yield item
    else:
        for item in items:
            yield item
