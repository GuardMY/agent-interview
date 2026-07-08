import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("interview_sessions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")

    # ── Parsed data (JSON) ──
    parsed_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parsed_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parsed_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parsed_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    parsed_experience: Mapped[list | None] = mapped_column(JSON, nullable=True)
    parsed_education: Mapped[list | None] = mapped_column(JSON, nullable=True)
    parsed_projects: Mapped[list | None] = mapped_column(JSON, nullable=True)
    parsed_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_experience_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "junior" | "mid" | "senior"
    suggested_job_title: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    parse_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # "pending" | "parsing" | "done" | "failed"
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    session: Mapped["InterviewSession | None"] = relationship(
        "InterviewSession", back_populates="resume"
    )
