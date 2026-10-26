from fastapi import FastAPI

from app.analysis.router import router as analysis_router
from app.resume.router import router as resume_router

app = FastAPI(title="AI Interviewer API")
app.include_router(resume_router)
app.include_router(analysis_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
