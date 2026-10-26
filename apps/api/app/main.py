from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.router import router as analysis_router
from app.config import get_settings
from app.db import create_pool
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
    max_age=600,  # browsers cache the preflight for 10 min instead of re-asking per request
)
app.include_router(resume_router)
app.include_router(analysis_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
