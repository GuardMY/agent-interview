import json
import logging
import math
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_admin_token, verify_candidate_token, verify_master_admin
from app.db.database import get_db
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.evaluation import SessionReport
from app.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionListItem,
    SessionListResponse,
    SessionListStats,
    SessionResponse,
)
from app.services.report import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])

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
    session = InterviewSession(
        candidate_name=req.candidate_name,
        job_title=req.job_title,
        experience_level=req.experience_level,
        key_skills=req.key_skills,
        interview_language=req.interview_language,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info(f"Session created: {session.id} for {session.candidate_name}")
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
