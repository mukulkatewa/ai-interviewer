from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.analysis.router import router as analysis_router
from app.config import get_settings
from app.db import create_pool
from app.llm import LLMBusyError, LLMError
from app.resume.router import router as resume_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.database_url:
        # Fail at startup, not on the first user request.
        raise RuntimeError("DATABASE_URL is not set")
    app.state.pool = await create_pool(settings.database_url, settings.db_pool_max_size)
    try:
        yield
    finally:
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
    return {"status": "ok"}
