"""Pydantic schemas for question bank CRUD API."""

from datetime import datetime

from pydantic import BaseModel, Field


class QuestionBankEntry(BaseModel):
    """A single question from the master question bank."""

    id: str
    question_text: str
    category: str
    difficulty: str
    expected_keywords: list[str]
    question_zh: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateQuestionRequest(BaseModel):
    """Payload for creating a new question."""

    question_text: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., min_length=1, max_length=50)
    difficulty: str = Field(..., pattern=r"^(junior|mid|senior)$")
    expected_keywords: list[str] = Field(default_factory=list)
    question_zh: str | None = Field(None, max_length=2000)


class UpdateQuestionRequest(BaseModel):
    """Payload for updating an existing question — all fields optional."""

    question_text: str | None = Field(None, min_length=1, max_length=2000)
    category: str | None = Field(None, min_length=1, max_length=50)
    difficulty: str | None = Field(None, pattern=r"^(junior|mid|senior)$")
    expected_keywords: list[str] | None = None
    question_zh: str | None = Field(None, max_length=2000)


class QuestionListResponse(BaseModel):
    """Paginated list of questions."""

    items: list[QuestionBankEntry]
    total: int
    page: int
    size: int
    pages: int


class CategoryListResponse(BaseModel):
    """Available question categories."""

    categories: list[str]
