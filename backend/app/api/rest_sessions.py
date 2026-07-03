import io
import json
import logging
import math
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_admin_token, verify_candidate_token, verify_master_admin
from app.config import settings
from app.db.database import get_db
from app.models.answer import Answer
from app.models.question import Question
from app.models.job_position import JobPosition
from app.models.session import InterviewSession
from app.schemas.evaluation import SessionReport
from app.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    ResumeUploadResponse,
    SessionListItem,
    SessionListResponse,
    SessionListStats,
    SessionResponse,
)
from app.services.report import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])

# ── File-format extraction helpers ────────────────────────────────────

_MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _extract_text_from_txt(content: bytes) -> str:
    """Extract text from plain text file."""
    return content.decode("utf-8", errors="replace")


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF parsing is not available (PyPDF2 not installed)",
        )
    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="DOCX parsing is not available (python-docx not installed)",
        )
    doc = Document(io.BytesIO(content))
    paragraphs: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)
    return "\n".join(paragraphs)


def _extract_resume_text(filename: str, content: bytes) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )
    if ext == ".pdf":
        return _extract_text_from_pdf(content)
    elif ext == ".docx":
        return _extract_text_from_docx(content)
    else:
        return _extract_text_from_txt(content)

_TEMPLATES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "interview_templates.json"
)


@router.get("/templates")
async def list_templates() -> list[dict]:
    """Return available interview templates (no auth required)."""
    if not _TEMPLATES_PATH.exists():
        return []
    with open(_TEMPLATES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("templates", [])


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> InterviewSession:
    """Create a new interview session. Returns admin + candidate tokens (only once)."""
    # Validate position_id if provided
    position_title = None
    position_level = None
    total_questions = settings.default_total_questions

    if req.position_id:
        result = await db.execute(
            select(JobPosition).where(
                JobPosition.id == req.position_id,
                JobPosition.status == "active",
            )
        )
        position = result.scalar_one_or_none()
        if position is None:
            raise HTTPException(
                status_code=400,
                detail=f"Position '{req.position_id}' not found or inactive",
            )
        position_title = position.title
        position_level = position.level
        total_questions = position.default_total_questions
        # Auto-fill job_title from position if not explicitly provided
        if not req.job_title or req.job_title == req.candidate_name:
            req.job_title = position.title
        # Auto-fill experience_level from position if default
        if req.experience_level == "mid" and position.level != "mid":
            req.experience_level = position.level

    session = InterviewSession(
        candidate_name=req.candidate_name,
        job_title=req.job_title,
        experience_level=req.experience_level,
        key_skills=req.key_skills,
        interview_language=req.interview_language,
        position_id=req.position_id,
        total_questions=total_questions,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info(
        f"Session created: {session.id} for {session.candidate_name}"
        f"{' (position: ' + position_title + ')' if position_title else ''}"
    )
    return session


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    sort: str = Query("started_at", description="Sort column"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    date_from: date | None = Query(None, description="Filter from date (inclusive)"),
    date_to: date | None = Query(None, description="Filter to date (inclusive)"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> SessionListResponse:
    """List all sessions with pagination, filtering, and aggregate stats."""
    # Build base query
    query = select(InterviewSession)

    if status:
        query = query.where(InterviewSession.status == status)
    if date_from:
        dt_from = datetime.combine(date_from, datetime.min.time())
        query = query.where(InterviewSession.started_at >= dt_from)
    if date_to:
        dt_to = datetime.combine(date_to, datetime.max.time())
        query = query.where(InterviewSession.started_at <= dt_to)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort and paginate
    sort_col = getattr(InterviewSession, sort, InterviewSession.started_at)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pages = max(1, math.ceil(total / size))
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    rows = result.scalars().all()
    items = [SessionListItem.model_validate(s) for s in rows]

    # Aggregate stats (across all matching sessions, not just the page)
    stats = await _compute_session_stats(db, status, date_from, date_to)

    return SessionListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
        stats=stats,
    )


async def _compute_session_stats(
    db: AsyncSession,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> SessionListStats:
    """Compute aggregate statistics across sessions."""
    # Status breakdown
    breakdown_query = select(
        InterviewSession.status,
        func.count(InterviewSession.id),
    )
    if date_from:
        breakdown_query = breakdown_query.where(
            InterviewSession.started_at >= datetime.combine(date_from, datetime.min.time())
        )
    if date_to:
        breakdown_query = breakdown_query.where(
            InterviewSession.started_at <= datetime.combine(date_to, datetime.max.time())
        )
    breakdown_query = breakdown_query.group_by(InterviewSession.status)

    result = await db.execute(breakdown_query)
    status_breakdown = {row[0]: row[1] for row in result.all()}
    total_count = sum(status_breakdown.values())
    active_count = sum(
        v for k, v in status_breakdown.items() if k != "done"
    )
    completed_count = status_breakdown.get("done", 0)

    # Average score for completed sessions
    avg_query = (
        select(func.avg(Answer.score))
        .join(InterviewSession, Answer.session_id == InterviewSession.id)
        .where(InterviewSession.status == "done")
    )
    if date_from:
        avg_query = avg_query.where(
            InterviewSession.started_at >= datetime.combine(date_from, datetime.min.time())
        )
    if date_to:
        avg_query = avg_query.where(
            InterviewSession.started_at <= datetime.combine(date_to, datetime.max.time())
        )

    avg_result = await db.execute(avg_query)
    avg_score = avg_result.scalar()
    avg_score = round(float(avg_score), 2) if avg_score is not None else None

    return SessionListStats(
        total_count=total_count,
        active_count=active_count,
        completed_count=completed_count,
        avg_score=avg_score,
        status_breakdown=status_breakdown,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session: InterviewSession = Depends(verify_candidate_token),
) -> InterviewSession:
    """Get interview session status (candidate access only)."""
    return session


@router.get("/sessions/{session_id}/report", response_model=SessionReport)
async def get_session_report(
    session: InterviewSession = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> SessionReport:
    """Get the full interview report (admin access only)."""
    report = await ReportService.build_report(session.id, db)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report


@router.get("/sessions/{session_id}/candidate-report", response_model=SessionReport)
async def get_candidate_report(
    session: InterviewSession = Depends(verify_candidate_token),
    db: AsyncSession = Depends(get_db),
) -> SessionReport:
    """Get interview report with candidate token (candidate view)."""
    report = await ReportService.build_report(session.id, db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session: InterviewSession = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an interview session and all related records (admin only)."""
    from sqlalchemy import delete

    await db.execute(delete(Answer).where(Answer.session_id == session.id))
    await db.execute(delete(Question).where(Question.session_id == session.id))
    await db.flush()
    await db.delete(session)
    await db.commit()


# ── Resume upload endpoint (P1) ──────────────────────────────────────


@router.post("/sessions/{session_id}/resume", response_model=ResumeUploadResponse)
async def upload_resume(
    session: InterviewSession = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
) -> ResumeUploadResponse:
    """Upload a resume file (PDF/DOCX/TXT) for an interview session.

    Extracts raw text and triggers structured parsing via LLM.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    # Read and validate size
    content = await file.read()
    if len(content) > _MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {_MAX_RESUME_BYTES // (1024 * 1024)} MB",
        )

    # Extract text
    resume_text = _extract_resume_text(file.filename, content)

    if not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from the uploaded file. The file may be empty or contain only images.",
        )

    # Store raw text on session
    session.resume_text = resume_text
    await db.commit()

    logger.info(
        f"Resume uploaded for session {session.id}: "
        f"{len(resume_text)} chars from {file.filename}"
    )

    # Try LLM parsing (non-blocking — will be async in P2)
    profile = None
    parse_status = "completed"
    parse_message = "Resume text extracted. Structured parsing not yet triggered."

    try:
        from app.services.resume_parser import ResumeParserService
        parser = ResumeParserService()
        profile = await parser.parse(resume_text)
        if profile:
            session.resume_profile_json = profile.model_dump()
            await db.commit()
            parse_message = "Resume parsed successfully."
            logger.info(f"Resume parsed for session {session.id}: {profile.name}")
        else:
            parse_status = "processing"
            parse_message = "Resume text saved. LLM parsing failed — will retry."
    except Exception as exc:
        parse_status = "processing"
        parse_message = f"Resume text saved. Parsing error: {exc}"
        logger.warning(f"Resume parse failed for session {session.id}: {exc}")

    return ResumeUploadResponse(
        session_id=session.id,
        status=parse_status,
        resume_text_length=len(resume_text),
        profile=profile,
        message=parse_message,
    )


@router.get("/sessions/{session_id}/resume", response_model=ResumeUploadResponse)
async def get_resume_profile(
    session: InterviewSession = Depends(verify_admin_token),
) -> ResumeUploadResponse:
    """Get the parsed resume profile and status for a session."""
    profile = None
    if session.resume_profile_json:
        from app.schemas.session import ResumeProfile
        profile = ResumeProfile(**session.resume_profile_json)

    status = "completed" if profile else (
        "processing" if session.resume_text else "not_uploaded"
    )

    return ResumeUploadResponse(
        session_id=session.id,
        status=status,
        resume_text_length=len(session.resume_text) if session.resume_text else 0,
        profile=profile,
        message="Resume profile loaded." if profile else "No resume uploaded yet.",
    )
