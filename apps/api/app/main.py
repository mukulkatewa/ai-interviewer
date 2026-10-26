from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.llm import GroqClient, LLMClient, LLMError
from app.resume.extract import ResumeExtractionError, extract_text
from app.resume.schema import ResumeProfile
from app.resume.structure import structure_resume

app = FastAPI(title="AI Interviewer API")

PDF_MAGIC = b"%PDF-"


@lru_cache
def get_extraction_llm() -> LLMClient:
    # Cached so the whole process shares one client (and its connection pool).
    # Tests replace this via app.dependency_overrides.
    settings = get_settings()
    return GroqClient(settings.groq_api_key, settings.groq_extraction_model)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/resumes/parse")
async def parse_resume(
    file: UploadFile,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMClient, Depends(get_extraction_llm)],
) -> ResumeProfile:
    # Read at most one byte past the limit: enough to detect "too big"
    # without loading an arbitrarily large upload into memory.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "File too large (max 5 MB)")

    # The Content-Type header is set by the client and can't be trusted;
    # every PDF starts with these magic bytes.
    if not data.startswith(PDF_MAGIC):
        raise HTTPException(415, "Upload a PDF file")

    try:
        text = extract_text(data)
    except ResumeExtractionError as e:
        raise HTTPException(422, str(e)) from e

    try:
        return await structure_resume(text, llm)
    except LLMError as e:
        raise HTTPException(502, "Could not read the resume. Please try again.") from e
