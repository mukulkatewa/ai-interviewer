from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

from app import limits
from app.auth import AuthUser
from app.config import Settings, get_settings
from app.db import Db
from app.deps import get_resume_llm
from app.llm import LLMClient
from app.resume import repo
from app.resume.extract import ResumeExtractionError, extract_text
from app.resume.structure import structure_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])

PDF_MAGIC = b"%PDF-"
MAX_FILE_NAME = 255


@router.post("", status_code=201)
async def upload_resume(
    file: UploadFile,
    user: AuthUser,
    db: Db,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMClient, Depends(get_resume_llm)],
) -> repo.StoredResume:
    await limits.enforce(db, user.id, "resumes", settings.limit_resumes_per_day)
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

    # LLM first, DB after: never hold a connection while waiting on the model (D18).
    # LLM failures become 502/503 in app/main.py.
    profile = await structure_resume(text, llm)
    file_name = (file.filename or "resume.pdf")[:MAX_FILE_NAME]
    return await repo.insert(db, user.id, file_name, text, profile)


@router.get("")
async def list_resumes(user: AuthUser, db: Db) -> list[repo.ResumeSummary]:
    return await repo.list_for_user(db, user.id)


@router.get("/{resume_id}")
async def get_resume(resume_id: UUID, user: AuthUser, db: Db) -> repo.StoredResume:
    resume = await repo.get(db, user.id, resume_id)
    if resume is None:
        # Same answer for "doesn't exist" and "not yours": IDs can't be probed.
        raise HTTPException(404, "Resume not found")
    return resume


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(resume_id: UUID, user: AuthUser, db: Db) -> Response:
    if not await repo.delete(db, user.id, resume_id):
        raise HTTPException(404, "Resume not found")
    return Response(status_code=204)
