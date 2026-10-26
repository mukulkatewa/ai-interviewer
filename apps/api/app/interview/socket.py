"""The interview WebSocket (protocol: projectprep.md, section 6).

Phase 6 scope: authenticate, then speak the intro when the client says `start`.
Listening (STT) and the conversation loop arrive in phases 7-8.
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
from app.deps import get_tts
from app.interview import repo, script
from app.speech.text import split_sentences
from app.speech.tts import TTSError, TTSProvider

logger = logging.getLogger(__name__)
router = APIRouter()


class Close(IntEnum):
    BAD_MESSAGE = 4400
    UNAUTHORIZED = 4401
    NOT_FOUND = 4404
    TRY_AGAIN_LATER = 1013  # standard code: server overloaded / dependency down


async def _receive_message(ws: WebSocket) -> dict[str, Any]:
    """Next client message as a JSON object; {} for anything else (binary, bad JSON, non-object)."""
    message = await ws.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    try:
        data = json.loads(message["text"]) if message.get("text") is not None else None
    except ValueError:
        data = None
    return data if isinstance(data, dict) else {}


async def _authenticate(ws: WebSocket, verify: TokenVerifier, timeout_s: float) -> CurrentUser | None:
    """First message must be {"type": "auth", "token": ...}. Closes the socket and returns None otherwise."""
    try:
        message = await asyncio.wait_for(_receive_message(ws), timeout_s)
    except TimeoutError:
        await ws.close(Close.UNAUTHORIZED, "Auth timeout")
        return None

    token = message.get("token") if message.get("type") == "auth" else None
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


@router.websocket("/interviews/{interview_id}/ws")
async def interview_socket(
    ws: WebSocket,
    interview_id: UUID,
    db: Db,
    verify: Annotated[TokenVerifier, Depends(get_token_verifier)],
    tts: Annotated[TTSProvider, Depends(get_tts)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ws.accept()
    try:
        user = await _authenticate(ws, verify, settings.ws_auth_timeout_s)
        if user is None:
            return
        interview = await repo.get(db, user.id, interview_id)
        if interview is None:
            await ws.close(Close.NOT_FOUND, "Interview not found")
            return
        await ws.send_json({"type": "ready", "interview_id": str(interview.id)})

        while True:
            message = await _receive_message(ws)
            match message.get("type"):
                case "start":
                    if not await repo.mark_started(db, user.id, interview.id):
                        await ws.send_json({"type": "error", "code": "already_started", "message": "This interview already started."})
                        continue
                    await speak(ws, tts, script.intro(interview))
                    await ws.send_json({"type": "turn_end", "phase": "intro"})
                case "end":
                    await ws.close()
                    return
                case _:
                    await ws.send_json({"type": "error", "code": "bad_message", "message": "Unknown message."})
    except WebSocketDisconnect:
        pass  # client left; nothing to clean up yet (phase 8 will save progress)
