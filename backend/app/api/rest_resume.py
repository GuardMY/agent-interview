"""REST endpoints for resume upload, parsing, and retrieval."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import verify_admin_token
from app.config import settings
from app.db.database import get_db
from app.llm.base import BaseLLMAdapter
from app.models.resume import Resume
from app.models.session import InterviewSession
from app.schemas.resume import ResumeData, ResumeUploadResponse
from app.services.file_storage import FileStorage
from app.services.resume_parser import ResumeParserService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["resume"])

# Shared singletons
_storage: FileStorage | None = None


def _get_storage() -> FileStorage:
    global _storage
    if _storage is None:
        _storage = FileStorage(settings.upload_dir)
    return _storage


def _create_llm() -> BaseLLMAdapter:
    """Create LLM adapter based on configured provider."""
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        from app.llm.claude import ClaudeAdapter
        return ClaudeAdapter()
    if provider in ("deepseek", "openai"):
        from app.llm.deepseek import DeepSeekAdapter
        return DeepSeekAdapter()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


# ── Upload Resume ────────────────────────────────────────────────

@router.post("/resumes/parse", response_model=ResumeUploadResponse, status_code=201)
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ResumeUploadResponse:
    """Upload a PDF resume and parse it with LLM. No auth required — usable before session creation."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are accepted")

    # Validate file size (read first chunk to check)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(413, f"File exceeds maximum size of {settings.max_upload_size_mb}MB")

    # Reset file pointer for saving
    await file.seek(0)

    # Save file
    storage = _get_storage()
    file_path, file_size = await storage.save(file, subdir="temp")

    # Create Resume record
    resume = Resume(
        original_filename=file.filename or "resume.pdf",
        file_path=file_path,
        file_size_bytes=file_size,
        parse_status="parsing",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    # Parse with LLM
    try:
        parser = ResumeParserService(_create_llm())
        parsed = await parser.parse(
            storage.get_absolute_path(file_path).as_posix(),
            language="en",  # PDF language detection could be added later
        )

        # Update Resume record with parsed data
        resume.parsed_name = parsed.name or None
        resume.parsed_email = parsed.email or None
        resume.parsed_phone = parsed.phone or None
        resume.parsed_summary = parsed.summary or None
        resume.parsed_skills = parsed.skills
        resume.parsed_experience = parsed.experience
        resume.parsed_education = parsed.education
        resume.parsed_projects = parsed.projects
        resume.inferred_experience_level = parsed.experience_years or None
        resume.suggested_job_title = parsed.suggested_job_title or None
        resume.parse_status = "done"
        await db.commit()
        await db.refresh(resume)

        return ResumeUploadResponse(
            resume_id=resume.id,
            filename=resume.original_filename,
            file_size_bytes=resume.file_size_bytes,
            parse_status=resume.parse_status,
            parsed_data=parsed,
            created_at=resume.created_at,
        )

    except Exception as e:
        logger.exception(f"Resume parsing failed for {resume.id}: {e}")
        resume.parse_status = "failed"
        resume.parse_error = str(e)
        await db.commit()
        await db.refresh(resume)

        return ResumeUploadResponse(
            resume_id=resume.id,
            filename=resume.original_filename,
            file_size_bytes=resume.file_size_bytes,
            parse_status=resume.parse_status,
            parsed_data=None,
            created_at=resume.created_at,
        )


# ── Get Resume for Session ───────────────────────────────────────

@router.get("/sessions/{session_id}/resume", response_model=ResumeUploadResponse)
async def get_session_resume(
    session: InterviewSession = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeUploadResponse:
    """Get the resume associated with a session (admin access only)."""
    stmt = (
        select(Resume)
        .where(Resume.session_id == session.id)
    )
    result = await db.execute(stmt)
    resume = result.scalar_one_or_none()

    if resume is None:
        raise HTTPException(404, "No resume found for this session")

    parsed_data = None
    if resume.parse_status == "done":
        parsed_data = ResumeData(
            name=resume.parsed_name or "",
            email=resume.parsed_email or "",
            phone=resume.parsed_phone or "",
            summary=resume.parsed_summary or "",
            skills=resume.parsed_skills or [],
            experience_years=resume.inferred_experience_level or "",
            experience=resume.parsed_experience or [],
            education=resume.parsed_education or [],
            projects=resume.parsed_projects or [],
            suggested_job_title=resume.suggested_job_title or "",
        )

    return ResumeUploadResponse(
        resume_id=resume.id,
        filename=resume.original_filename,
        file_size_bytes=resume.file_size_bytes,
        parse_status=resume.parse_status,
        parsed_data=parsed_data,
        created_at=resume.created_at,
    )
