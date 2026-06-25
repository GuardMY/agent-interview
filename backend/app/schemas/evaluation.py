from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)


class AnswerReport(BaseModel):
    question_text: str
    category: str
    difficulty: str
    order_index: int
    status: str
    answer_content: str | None = None
    score: int | None = None
    score_comment: str | None = None


class SessionReport(BaseModel):
    session_id: str
    candidate_name: str
    job_title: str
    experience_level: str
    status: str
    total_questions: int
    answered_count: int
    average_score: float | None = None
    answers: list[AnswerReport]
    started_at: datetime
    completed_at: datetime | None = None
