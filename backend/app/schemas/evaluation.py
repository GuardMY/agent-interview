from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── P3: Behavioral & Position Match Dimensions ──────────────

class BehavioralDimensions(BaseModel):
    """Behavioral interview dimensions (scored during BEHAVIORAL phase)."""

    teamwork: int | None = Field(None, ge=1, le=5)
    leadership: int | None = Field(None, ge=1, le=5)
    ownership: int | None = Field(None, ge=1, le=5)
    growth_mindset: int | None = Field(None, ge=1, le=5)
    culture_fit: int | None = Field(None, ge=1, le=5)


class PositionMatchDimensions(BaseModel):
    """Position match dimensions — how well the candidate fits the target role."""

    skill_coverage: int | None = Field(None, ge=1, le=5, description="Skill stack coverage vs position requirements")
    experience_alignment: int | None = Field(None, ge=1, le=5, description="Past experience alignment with role responsibilities")
    level_alignment: int | None = Field(None, ge=1, le=5, description="Candidate level vs position target level")
    domain_fit: int | None = Field(None, ge=1, le=5, description="Industry/domain experience fit")
    growth_potential: int | None = Field(None, ge=1, le=5, description="Growth trajectory within this role")


# ── Core Evaluation Schemas ─────────────────────────────────

class EvaluationDimensions(BaseModel):
    """Multi-dimensional scoring breakdown."""

    technical_accuracy: int = Field(..., ge=1, le=5, description="Correctness of technical content")
    depth_of_knowledge: int = Field(..., ge=1, le=5, description="Depth beyond surface-level")
    communication: int = Field(..., ge=1, le=5, description="Clarity and structure")
    problem_solving: int = Field(..., ge=1, le=5, description="Logical approach and edge cases")
    # P3: Extended dimensions
    behavioral: BehavioralDimensions | None = None
    position_match: PositionMatchDimensions | None = None


class EvaluationResult(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    dimensions: EvaluationDimensions | None = None
    # P3: Extended fields
    behavioral: BehavioralDimensions | None = None
    position_match: PositionMatchDimensions | None = None
    question_chain_depth: int = 0
    is_follow_up: bool = False
    relates_to_position_requirement: str | None = None


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
    # P3: Extended fields
    behavioral: BehavioralDimensions | None = None
    position_match: PositionMatchDimensions | None = None
    phase: str | None = None
    relates_to_position_requirement: str | None = None


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
    # P3: Enhanced report fields
    phase_scores: dict[str, float] | None = None
    position_match_summary: dict[str, float] | None = None
    gap_summary: dict | None = None
