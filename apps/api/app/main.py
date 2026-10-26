from fastapi import FastAPI

from app.resume.router import router as resume_router

app = FastAPI(title="AI Interviewer API")
app.include_router(resume_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
