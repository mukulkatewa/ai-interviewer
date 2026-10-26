"""The interview WebSocket (protocol: projectprep.md, section 6).

`interview_socket` handles the connection: accept, authenticate, load, close.
`InterviewSession` owns the conversation once the user is known.
"""

import asyncio
import json
import logging
import time
from enum import IntEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.auth import AuthUnavailable, CurrentUser, InvalidToken, TokenVerifier, get_token_verifier
from app.config import Settings, get_settings
from app.db import Db
from app.deps import get_stt, get_tts
from app.interview import repo, script
from app.interview.vocabulary import vocabulary_prompt
from app.speech.stt import STTBusyError, STTError, STTProvider
from app.speech.text import split_sentences
from app.speech.tts import TTSError, TTSProvider
from app.speech.wav import AnswerTooLong, BadAudio, wav_duration

logger = logging.getLogger(__name__)
router = APIRouter()


class Close(IntEnum):
    BAD_MESSAGE = 4400
    UNAUTHORIZED = 4401
    NOT_FOUND = 4404
    TRY_AGAIN_LATER = 1013  # standard code: server overloaded / dependency down


async def _receive(ws: WebSocket) -> dict[str, Any] | bytes:
    """Next client message: bytes for binary frames, a dict for JSON objects, {} for anything else."""
    message = await ws.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    if message.get("bytes") is not None:
        return message["bytes"]
    try:
        data = json.loads(message["text"]) if message.get("text") is not None else None
    except ValueError:
        data = None
    return data if isinstance(data, dict) else {}


async def _authenticate(ws: WebSocket, verify: TokenVerifier, timeout_s: float) -> CurrentUser | None:
    """First message must be {"type": "auth", "token": ...}. Closes the socket and returns None otherwise."""
    try:
        message = await asyncio.wait_for(_receive(ws), timeout_s)
    except TimeoutError:
        await ws.close(Close.UNAUTHORIZED, "Auth timeout")
        return None

    token = message.get("token") if isinstance(message, dict) and message.get("type") == "auth" else None
    if not isinstance(token, str):
        await ws.close(Close.UNAUTHORIZED, "First message must be auth")
        return None
    try:
        # verify may block on a JWKS fetch; keep it off the event loop.
        return await asyncio.to_thread(verify, token)
    except InvalidToken:
        await ws.close(Close.UNAUTHORIZED, "Invalid or expired token")
    except AuthUnavailable:
        await ws.close(Close.TRY_AGAIN_LATER, "Auth temporarily unavailable")
    return None


async def speak(ws: WebSocket, tts: TTSProvider, text: str) -> None:
    """Send the full text as a caption, then audio one sentence at a time.

    Each sentence is sent as soon as it's synthesized, so the browser plays
    sentence N while we synthesize N+1 (Kokoro runs ~2x faster than playback, D23).
    If TTS fails, the browser speaks the rest itself (D26).
    """
    await ws.send_json({"type": "transcript", "role": "interviewer", "text": text})
    sentences = split_sentences(text)
    for seq, sentence in enumerate(sentences):
        started = time.perf_counter()
        try:
            audio = await tts.synthesize(sentence)
        except TTSError as e:
            logger.warning("TTS failed at sentence %d: %s", seq, e)
            await ws.send_json(
                {
                    "type": "error",
                    "code": "tts_unavailable",
                    "message": "Voice is unavailable; using your browser's voice.",
                    "text": " ".join(sentences[seq:]),
                }
            )
            return
        logger.info("tts seq=%d words=%d ms=%.0f", seq, len(sentence.split()), (time.perf_counter() - started) * 1000)
        # Order matters: the client pairs each binary frame with the audio_meta before it.
        await ws.send_json({"type": "audio_meta", "seq": seq, "text": sentence})
        await ws.send_bytes(audio)


class InterviewSession:
    """One authenticated user's live interview on one socket."""

    def __init__(self, ws: WebSocket, db: Db, user: CurrentUser, context: repo.InterviewContext,
                 tts: TTSProvider, stt: STTProvider):  # fmt: skip
        self.ws, self.db, self.user, self.ctx = ws, db, user, context
        self.tts, self.stt = tts, stt
        self.vocabulary = vocabulary_prompt(context.resume, context.job)  # D24, built once
        self.awaiting_answer = False  # binary answers are accepted only after our turn_end

    async def run(self) -> None:
        await self.ws.send_json({"type": "ready", "interview_id": str(self.ctx.interview.id)})
        while True:
            message = await _receive(self.ws)
            if isinstance(message, bytes):
                await self.on_answer(message)
                continue
            match message.get("type"):
                case "start":
                    await self.on_start()
                case "end":
                    await self.ws.close()
                    return
                case _:
                    await self.error("bad_message", "Unknown message.")

    async def on_start(self) -> None:
        if not await repo.mark_started(self.db, self.user.id, self.ctx.interview.id):
            await self.error("already_started", "This interview already started.")
            return
        await speak(self.ws, self.tts, script.intro(self.ctx.interview))
        await self.give_turn("intro")

    async def on_answer(self, wav: bytes) -> None:
        if not self.awaiting_answer:
            await self.error("not_your_turn", "Wait for the interviewer to finish.")
            return
        self.awaiting_answer = False

        try:
            seconds = wav_duration(wav)
        except AnswerTooLong:
            return await self.retry_turn("answer_too_long", "Answers can be at most 2 minutes.")
        except BadAudio:
            return await self.retry_turn("bad_audio", "We couldn't read that recording. Please answer again.")

        try:
            transcript = await self.stt.transcribe(wav, self.vocabulary)
        except STTBusyError:
            return await self.retry_turn("stt_busy", "We're at capacity. Please answer again in a moment.")
        except STTError as e:
            logger.warning("STT failed: %s", e)
            return await self.retry_turn("stt_failed", "We couldn't transcribe that. Please answer again.")
        if not transcript.text:
            return await self.retry_turn("no_speech", "We didn't catch that. Please answer again.")

        logger.info("stt seconds=%.1f ms=%d words=%d", seconds, transcript.stt_ms, len(transcript.text.split()))
        await self.ws.send_json({"type": "transcript", "role": "candidate", "text": transcript.text})
        # Phase 7 placeholder reply; phase 8 replaces it with the real conversation.
        await speak(self.ws, self.tts, "Thanks, I've got that.")
        await self.give_turn("intro")

    async def give_turn(self, phase: str) -> None:
        self.awaiting_answer = True
        await self.ws.send_json({"type": "turn_end", "phase": phase})

    async def retry_turn(self, code: str, message: str) -> None:
        """An answer couldn't be used: say why and let the candidate answer again."""
        await self.error(code, message)
        await self.give_turn("intro")

    async def error(self, code: str, message: str) -> None:
        await self.ws.send_json({"type": "error", "code": code, "message": message})


@router.websocket("/interviews/{interview_id}/ws")
async def interview_socket(
    ws: WebSocket,
    interview_id: UUID,
    db: Db,
    verify: Annotated[TokenVerifier, Depends(get_token_verifier)],
    tts: Annotated[TTSProvider, Depends(get_tts)],
    stt: Annotated[STTProvider, Depends(get_stt)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ws.accept()
    try:
        user = await _authenticate(ws, verify, settings.ws_auth_timeout_s)
        if user is None:
            return
        context = await repo.get_context(db, user.id, interview_id)
        if context is None:
            await ws.close(Close.NOT_FOUND, "Interview not found")
            return
        await InterviewSession(ws, db, user, context, tts, stt).run()
    except WebSocketDisconnect:
        pass  # client left; phase 8 saves progress per turn, so nothing is lost
