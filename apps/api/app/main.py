import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.account import router as account_router
from app.analysis.router import router as analysis_router
from app.config import get_settings
from app.db import create_pool
from app.deps import get_report_llm
from app.interview.router import router as interview_router
from app.interview.socket import close_all_for_restart
from app.interview.socket import router as interview_socket_router
from app.jobs.worker import Worker
from app.llm import LLMBusyError, LLMError
from app.observability import init_error_tracking
from app.report.service import report_handlers
from app.resume.router import router as resume_router
from app.speech.tts import KokoroTTS


def _configure_logging(level: str) -> None:
    """Make app.* logs visible (per-turn latency, job results) without changing uvicorn's loggers."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("app")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False  # don't print twice through uvicorn's root handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _configure_logging(settings.log_level)
    init_error_tracking(settings.sentry_dsn, settings.environment)
    if not settings.database_url:
        # Fail at startup, not on the first user request.
        raise RuntimeError("DATABASE_URL is not set")
    app.state.pool = await create_pool(settings.database_url, settings.db_pool_max_size)
    # One HTTP client for Kokoro: keeps connections warm between sentences.
    tts_http = httpx.AsyncClient(timeout=settings.tts_timeout_s)
    app.state.tts = KokoroTTS(tts_http, settings.kokoro_url, settings.kokoro_voice)
    # Background jobs (interview reports) run in this process (D31).
    worker_task = None
    if settings.run_jobs:
        handlers, on_failed = report_handlers(app.state.pool, get_report_llm())
        worker_task = asyncio.create_task(Worker(app.state.pool, handlers, on_failed).run_forever())
    try:
        yield
    finally:
        await close_all_for_restart()  # a deploy: clients reconnect and resume (D43)
        if worker_task:
            worker_task.cancel()  # an interrupted job goes back to the queue (requeue_stale)
            await asyncio.gather(worker_task, return_exceptions=True)
        await tts_http.aclose()
        await app.state.pool.close()


app = FastAPI(title="AI Interviewer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],  # so the browser can read it on a 503
    max_age=600,  # browsers cache the preflight for 10 min instead of re-asking per request
)
app.include_router(resume_router)
app.include_router(analysis_router)
app.include_router(interview_router)
app.include_router(interview_socket_router)
app.include_router(account_router)


# LLM failures are handled here once, so routes contain only the happy path.
# Routes do all LLM work before writing to the DB (D18), so a failure here
# never leaves half-saved data.


@app.exception_handler(LLMBusyError)
async def llm_busy(_: Request, e: LLMBusyError) -> JSONResponse:
    return JSONResponse(
        {"detail": "Our AI is at capacity right now. Please try again in a minute."},
        status_code=503,
        headers={"Retry-After": str(e.retry_after_s)},
    )


@app.exception_handler(LLMError)
async def llm_failed(_: Request, e: LLMError) -> JSONResponse:
    return JSONResponse({"detail": "The AI couldn't process this. Please try again."}, status_code=502)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Cheap and dependency-free, so a restart loop never hinges on the database."""
    return {"status": "ok"}


@app.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse | dict[str, str]:
    """Readiness: can we serve users? The database is required (503 without it). TTS is reported but not
    required: when it is down, interviews fall back to browser speech (D26). Point uptime monitors here."""
    try:
        await asyncio.wait_for(request.app.state.pool.fetchval("select 1"), timeout=3)
    except Exception as e:  # noqa: BLE001 - any failure, including a timeout, means "not ready"
        logging.getLogger(__name__).warning("not ready: %r", e)
        return JSONResponse({"status": "unavailable", "database": "down"}, status_code=503)
    tts = "up" if await request.app.state.tts.healthy() else "down"
    return {"status": "ok", "database": "up", "tts": tts}
