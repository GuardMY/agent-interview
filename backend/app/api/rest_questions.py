"""REST API for managing the question bank (admin-only CRUD)."""

import math
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_master_admin
from app.db.database import get_db
from app.models.question_bank import QuestionBank
from app.schemas.question_bank import (
    CategoryListResponse,
    CreateQuestionRequest,
    QuestionBankEntry,
    QuestionListResponse,
    UpdateQuestionRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["questions"])


@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    difficulty: str | None = Query(None, description="Filter by difficulty"),
    search: str | None = Query(None, description="Search in question text"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> QuestionListResponse:
    """List questions with pagination, filtering, and text search."""
    # Build base query (only active questions)
    query = select(QuestionBank).where(QuestionBank.is_active == True)

    if category:
        query = query.where(QuestionBank.category == category)
    if difficulty:
        query = query.where(QuestionBank.difficulty == difficulty)
    if search:
        search_term = f"%{search}%"
        query = query.where(QuestionBank.question_text.ilike(search_term))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    pages = max(1, math.ceil(total / size))
    query = query.order_by(QuestionBank.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = [QuestionBankEntry.model_validate(q) for q in result.scalars().all()]

    return QuestionListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post("/questions", response_model=QuestionBankEntry, status_code=201)
async def create_question(
    req: CreateQuestionRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> QuestionBankEntry:
    """Create a new question in the bank."""
    question = QuestionBank(
        question_text=req.question_text,
        category=req.category,
        difficulty=req.difficulty,
        expected_keywords=req.expected_keywords,
        question_zh=req.question_zh,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return QuestionBankEntry.model_validate(question)


@router.put("/questions/{question_id}", response_model=QuestionBankEntry)
async def update_question(
    question_id: str,
    req: UpdateQuestionRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> QuestionBankEntry:
    """Update an existing question (partial update)."""
    result = await db.execute(
        select(QuestionBank).where(
            QuestionBank.id == question_id,
            QuestionBank.is_active == True,
        )
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Partial update: only set fields that are provided
    updates = req.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(question, field, value)

    await db.commit()
    await db.refresh(question)
    return QuestionBankEntry.model_validate(question)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> None:
    """Soft-delete a question (set is_active=False)."""
    result = await db.execute(
        select(QuestionBank).where(
            QuestionBank.id == question_id,
            QuestionBank.is_active == True,
        )
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question.is_active = False
    await db.commit()


@router.get("/questions/categories", response_model=CategoryListResponse)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_master_admin),
) -> CategoryListResponse:
    """Return distinct active categories from the question bank."""
    result = await db.execute(
        select(QuestionBank.category)
        .where(QuestionBank.is_active == True)
        .distinct()
        .order_by(QuestionBank.category)
    )
    categories = [row[0] for row in result.all()]
    return CategoryListResponse(categories=categories)
