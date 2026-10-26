from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.deps import get_extraction_llm
from app.llm import LLMClient, LLMError
from app.resume.extract import ResumeExtractionError, extract_text
from app.resume.schema import ResumeProfile
from app.resume.structure import structure_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])

PDF_MAGIC = b"%PDF-"


@router.post("/parse")
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
