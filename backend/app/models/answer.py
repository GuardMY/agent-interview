import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weaknesses: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    matched_keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    missing_points: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_evaluation_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Multi-dimensional scores (nullable = backward compatible with old data)
    dimension_technical_accuracy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimension_depth_of_knowledge: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimension_communication: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimension_problem_solving: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    question: Mapped["Question"] = relationship(
        "Question", back_populates="answer"
    )
    session: Mapped["InterviewSession"] = relationship(
        "InterviewSession", back_populates="answers"
    )
