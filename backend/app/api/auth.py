"""FastAPI dependencies for token-based authentication."""

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.session import InterviewSession


async def verify_admin_token(
    session_id: str,
    x_admin_token: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> InterviewSession:
    """Verify admin token for Dashboard access (view reports, delete)."""
    if not x_admin_token:
        raise HTTPException(403, "Missing X-Admin-Token header")

    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, "Session not found")
    if session.admin_token != x_admin_token:
        raise HTTPException(403, "Forbidden")

    return session


async def verify_candidate_token(
    session_id: str,
    token: str = Query(None),
    db: AsyncSession = Depends(get_db),
) -> InterviewSession:
    """Verify candidate token for interview & report access."""
    if not token:
        raise HTTPException(403, "Missing token parameter")

    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, "Session not found")
    if session.candidate_token != token:
        raise HTTPException(403, "Forbidden")

    return session


async def verify_master_admin(
    x_admin_token: str = Header(None),
) -> bool:
    """Verify the master admin token (global, not session-scoped).

    When master_admin_token is not configured, authentication is skipped
    (the frontend is management-only and does not require auth).
    """
    if not settings.master_admin_token:
        return True
    if not x_admin_token or x_admin_token != settings.master_admin_token:
        raise HTTPException(403, "Forbidden")
    return True
