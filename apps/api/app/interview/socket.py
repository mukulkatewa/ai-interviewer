"""The interview WebSocket (protocol: projectprep.md, section 6).

`interview_socket` handles the connection: accept, authenticate, load, close.
`InterviewSession` runs the conversation once the user is known.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from enum import IntEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.auth import AuthUnavailable, CurrentUser, InvalidToken, TokenVerifier, get_token_verifier
from app.config import Settings, get_settings
from app.db import Db
from app.deps import get_live_llm, get_stt, get_tts
from app.interview import repo, script
from app.interview.conversation import TurnReply, advance
from app.interview.plan import InterviewPlan, normalize
from app.interview.speaker import ACKNOWLEDGEMENTS, Speaker
from app.interview.vocabulary import vocabulary_prompt
from app.llm import TextStreamer
from app.speech.stt import STTBusyError, STTError, STTProvider
from app.speech.tts import TTSProvider
from app.speech.wav import AnswerTooLong, BadAudio, wav_duration

logger = logging.getLogger(__name__)
router = APIRouter()


class Close(IntEnum):
    BAD_MESSAGE = 4400
    UNAUTHORIZED = 4401
    NOT_FOUND = 4404
    TAKEN_OVER = 4409  # the same interview was opened in another tab (D30)
    TRY_AGAIN_LATER = 1013  # standard code: server overloaded / dependency down


# One live socket per interview in this process (D30): a new tab takes over.
_live: dict[UUID, WebSocket] = {}


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


class InterviewSession:
    """One authenticated user's live interview on one socket."""

    def __init__(self, ws: WebSocket, db: Db, user: CurrentUser, ctx: repo.InterviewContext, turns: list[repo.Turn],
                 tts: TTSProvider, stt: STTProvider, llm: TextStreamer, settings: Settings):  # fmt: skip
        self.ws, self.db, self.user, self.ctx = ws, db, user, ctx
        self.speaker = Speaker(ws, tts)
        self.stt, self.llm, self.settings = stt, llm, settings
        self.turns = turns  # everything said so far, in order (from the DB on reconnect)
        # Interviews created before phase 8 have no plan: normalize() gives the fallback questions.
        self.plan: InterviewPlan = ctx.plan or normalize(InterviewPlan(questions=[]))
        self.position = ctx.position
        self.vocabulary = vocabulary_prompt(ctx.resume, ctx.job)  # D24, built once
        self.awaiting_answer = False  # binary answers are accepted only after our turn_end
        self.started = ctx.interview.status == "in_progress"

    @property
    def interview_id(self) -> UUID:
        return self.ctx.interview.id

    async def run(self) -> None:
        await self.ws.send_json({"type": "ready", "interview_id": str(self.interview_id), "resumable": self.started})
        while True:
            message = await _receive(self.ws)
            if isinstance(message, bytes):
                await self.on_answer(message)
                continue
            match message.get("type"):
                case "start":
                    await self.on_start()
                case "end":
                    await self.on_end()
                    return
                case _:
                    await self.error("bad_message", "Unknown message.")

    # --- events ---------------------------------------------------------------

    async def on_start(self) -> None:
        if self.started:
            await self.resume()
            return
        if not await repo.mark_started(self.db, self.user.id, self.interview_id):
            await self.error("already_started", "This interview already started.")
            return
        self.started = True
        self.ctx.interview.started_at = datetime.now(UTC)
        text = await self.speaker.say(script.intro(self.ctx.interview))
        await self.record_reply(text, self.position, llm_ms=None, tts_ms=None)
        await self.give_turn()

    async def resume(self) -> None:
        """Reconnected mid-interview: repeat the last thing the interviewer asked."""
        last = next((t.text for t in reversed(self.turns) if t.role == "interviewer"), None)
        if last is None:
            # Dropped during the intro, before it was saved: just give the intro again.
            text = await self.speaker.say(script.intro(self.ctx.interview))
            await self.record_reply(text, self.position, llm_ms=None, tts_ms=None)
        else:
            await self.speaker.say(script.welcome_back(last))
        await self.give_turn()

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

        await self.ws.send_json({"type": "transcript", "role": "candidate", "text": transcript.text})
        turn = repo.Turn(seq=len(self.turns), role="candidate", question_index=self.position.question, text=transcript.text)
        await repo.save_candidate_turn(self.db, self.user.id, self.interview_id, turn, seconds, transcript.stt_ms,
                                       [s.model_dump() for s in transcript.segments])  # fmt: skip
        self.turns.append(turn)
        await self.reply_to_answer()

    async def reply_to_answer(self) -> None:
        time_up = self.time_up()
        reply = TurnReply(self.llm, self.ctx, self.plan, self.position,
                          [(t.role, t.text) for t in self.turns], time_up)  # fmt: skip
        # Cached acknowledgement first: the candidate hears something at once (D23).
        ack = ACKNOWLEDGEMENTS[len(self.turns) % len(ACKNOWLEDGEMENTS)]
        text, tts_ms = await self.speaker.reply(reply.sentences(), acknowledgement=ack)
        new_position = advance(self.position, reply.action, len(self.plan.questions), time_up)
        await self.record_reply(text, new_position, reply.llm_ms, tts_ms)
        logger.info("turn action=%s llm_ms=%s tts_ms=%s", reply.action, reply.llm_ms, tts_ms)

        if reply.action == "END":
            await self.finish()
        else:
            await self.give_turn()

    async def on_end(self) -> None:
        """The candidate pressed "End interview"."""
        if self.started:
            await self.speaker.say(script.ended_early(self.ctx.interview))
            await self.finish()
        else:
            await self.ws.close()

    # --- helpers --------------------------------------------------------------

    def time_up(self) -> bool:
        started = self.ctx.interview.started_at
        if started is None:
            return False
        return (datetime.now(UTC) - started).total_seconds() > self.settings.interview_max_minutes * 60

    async def record_reply(self, text: str, position: repo.Position, llm_ms: int | None, tts_ms: int | None) -> None:
        turn = repo.Turn(seq=len(self.turns), role="interviewer", question_index=position.question, text=text)
        await repo.save_interviewer_turn(self.db, self.user.id, self.interview_id, turn, position, llm_ms, tts_ms)
        self.turns.append(turn)
        self.position = position

    async def finish(self) -> None:
        await repo.finish(self.db, self.user.id, self.interview_id)
        await self.ws.send_json({"type": "ended", "interview_id": str(self.interview_id)})
        await self.ws.close()

    async def give_turn(self) -> None:
        self.awaiting_answer = True
        await self.ws.send_json({"type": "turn_end", "question": self.position.question})

    async def retry_turn(self, code: str, message: str) -> None:
        """An answer couldn't be used: say why and let the candidate answer again."""
        await self.error(code, message)
        await self.give_turn()

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
    llm: Annotated[TextStreamer, Depends(get_live_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ws.accept()
    try:
        user = await _authenticate(ws, verify, settings.ws_auth_timeout_s)
        if user is None:
            return
        ctx = await repo.get_context(db, user.id, interview_id)
        if ctx is None:
            await ws.close(Close.NOT_FOUND, "Interview not found")
            return
        if ctx.interview.status not in ("created", "in_progress"):
            await ws.send_json({"type": "ended", "interview_id": str(interview_id)})
            await ws.close()
            return

        previous = _live.get(interview_id)
        _live[interview_id] = ws
        if previous is not None:
            await previous.close(Close.TAKEN_OVER, "Opened in another tab")
        try:
            turns = await repo.list_turns(db, user.id, interview_id)
            await InterviewSession(ws, db, user, ctx, turns, tts, stt, llm, settings).run()
        finally:
            if _live.get(interview_id) is ws:
                del _live[interview_id]
    except WebSocketDisconnect:
        pass  # every turn is already saved; reconnecting resumes (projectprep.md 5.11)
