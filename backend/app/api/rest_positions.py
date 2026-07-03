"""REST API for JobPosition CRUD — master admin only."""

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_master_admin
from app.db.database import get_db
from app.models.job_position import JobPosition
from app.schemas.job_position import (
    JobPositionCreate,
    JobPositionListItem,
    JobPositionListResponse,
    JobPositionResponse,
    JobPositionUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["positions"])


def _validate_position_exists(position: JobPosition | None, position_id: str) -> JobPosition:
    """Raise 404 if position is None or has been archived."""
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.status == "archived":
        raise HTTPException(status_code=404, detail="Position has been archived")
    return position


@router.post("/positions", response_model=JobPositionResponse, status_code=201)
async def create_position(
    req: JobPositionCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> JobPosition:
    """Create a new job position (master admin only)."""
    position = JobPosition(
        title=req.title,
        department=req.department,
        level=req.level,
        description=req.description,
        responsibilities=req.responsibilities,
        required_skills=[s.model_dump() for s in req.required_skills],
        preferred_skills=[s.model_dump() for s in req.preferred_skills],
        soft_skill_requirements=req.soft_skill_requirements.model_dump(),
        domain_knowledge=req.domain_knowledge,
        default_total_questions=req.default_total_questions,
        default_duration_minutes=req.default_duration_minutes,
        interview_focus_areas=req.interview_focus_areas,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    logger.info(f"Position created: {position.id} — {position.title}")
    return position


@router.get("/positions", response_model=JobPositionListResponse)
async def list_positions(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    level: str | None = Query(None, description="Filter by level (junior/mid/senior)"),
    status: str | None = Query(None, description="Filter by status (active/archived)"),
    q: str | None = Query(None, description="Search in title and department"),
    sort: str = Query("created_at", description="Sort column"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> JobPositionListResponse:
    """List all job positions with pagination, filtering, and search."""
    query = select(JobPosition)

    if level:
        query = query.where(JobPosition.level == level)
    if status:
        query = query.where(JobPosition.status == status)
    if q:
        search = f"%{q}%"
        query = query.where(
            (JobPosition.title.ilike(search)) |
            (JobPosition.department.ilike(search))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(JobPosition, sort, JobPosition.created_at)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Paginate
    pages = max(1, math.ceil(total / size))
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    rows = result.scalars().all()
    items = [JobPositionListItem.model_validate(p) for p in rows]

    return JobPositionListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/positions/{position_id}", response_model=JobPositionResponse)
async def get_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> JobPosition:
    """Get a single job position by ID."""
    result = await db.execute(
        select(JobPosition).where(JobPosition.id == position_id)
    )
    position = result.scalar_one_or_none()
    return _validate_position_exists(position, position_id)


@router.put("/positions/{position_id}", response_model=JobPositionResponse)
async def update_position(
    position_id: str,
    req: JobPositionUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> JobPosition:
    """Update an existing job position — partial update (master admin only)."""
    result = await db.execute(
        select(JobPosition).where(JobPosition.id == position_id)
    )
    position = result.scalar_one_or_none()
    _validate_position_exists(position, position_id)

    updates = req.model_dump(exclude_unset=True)

    # Handle nested model: convert SoftSkillRequirements to dict
    if "soft_skill_requirements" in updates and updates["soft_skill_requirements"] is not None:
        ssr = updates["soft_skill_requirements"]
        if hasattr(ssr, "model_dump"):
            updates["soft_skill_requirements"] = ssr.model_dump()

    # Handle list of SkillRequirement models
    for field_name in ("required_skills", "preferred_skills"):
        if field_name in updates and updates[field_name] is not None:
            skills = updates[field_name]
            updates[field_name] = [
                s.model_dump() if hasattr(s, "model_dump") else s
                for s in skills
            ]

    for field, value in updates.items():
        if value is not None:
            setattr(position, field, value)

    await db.commit()
    await db.refresh(position)
    logger.info(f"Position updated: {position_id}")
    return position


@router.delete("/positions/{position_id}", status_code=204)
async def archive_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> None:
    """Archive a job position (soft delete — master admin only)."""
    result = await db.execute(
        select(JobPosition).where(JobPosition.id == position_id)
    )
    position = result.scalar_one_or_none()
    _validate_position_exists(position, position_id)

    position.status = "archived"
    await db.commit()
    logger.info(f"Position archived: {position_id}")
