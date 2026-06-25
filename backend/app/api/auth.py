"""FastAPI dependencies for token-based authentication."""

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    if not session or session.admin_token != x_admin_token:
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

    if not session or session.candidate_token != token:
        raise HTTPException(403, "Forbidden")

    return session
