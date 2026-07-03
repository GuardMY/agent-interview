import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    candidate_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    experience_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="mid"
    )
    key_skills: Mapped[dict] = mapped_column(JSON, default=list)
    interview_language: Mapped[str] = mapped_column(String(10), default="en")
    position_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    admin_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        default=lambda: secrets.token_urlsafe(32),
    )
    candidate_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        default=lambda: secrets.token_urlsafe(32),
    )
    status: Mapped[str] = mapped_column(String(20), default="idle")
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=5)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Resume-driven interview fields (P1) ──────────────────────
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gap_analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    interview_strategy_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phase_question_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="session", order_by="Question.order_index",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    answers: Mapped[list["Answer"]] = relationship(
        "Answer", back_populates="session",
        cascade="all, delete-orphan", passive_deletes=True,
    )
