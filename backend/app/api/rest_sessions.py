import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.session import InterviewSession
from app.schemas.session import CreateSessionRequest, SessionResponse, CreateSessionResponse
from app.schemas.evaluation import SessionReport
from app.services.report import ReportService
from app.api.auth import verify_admin_token, verify_candidate_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])


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


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session: InterviewSession = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an interview session and all related records (admin only)."""
    from sqlalchemy import delete
    from app.models.answer import Answer
    from app.models.question import Question

    await db.execute(delete(Answer).where(Answer.session_id == session.id))
    await db.execute(delete(Question).where(Question.session_id == session.id))
    await db.flush()
    await db.delete(session)
    await db.commit()
