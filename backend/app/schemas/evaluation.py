from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationDimensions(BaseModel):
    """Multi-dimensional scoring breakdown."""

    technical_accuracy: int = Field(..., ge=1, le=5, description="Correctness of technical content")
    depth_of_knowledge: int = Field(..., ge=1, le=5, description="Depth beyond surface-level")
    communication: int = Field(..., ge=1, le=5, description="Clarity and structure")
    problem_solving: int = Field(..., ge=1, le=5, description="Logical approach and edge cases")


class EvaluationResult(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    dimensions: EvaluationDimensions | None = None


class AnswerReport(BaseModel):
    question_text: str
    category: str
    difficulty: str
    order_index: int
    status: str
    answer_content: str | None = None
    score: int | None = None
    score_comment: str | None = None
    dimensions: EvaluationDimensions | None = None


class ConversationEntry(BaseModel):
    """A single message in the interview conversation transcript."""

    role: str
    content: str
    timestamp: str


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
    dimension_averages: dict[str, float] | None = None
    conversation_transcript: list[ConversationEntry] | None = None
