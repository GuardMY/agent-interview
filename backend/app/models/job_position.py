"""Job position model — reusable JD templates for interview sessions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class JobPosition(Base):
    """Job position definition — reusable across interview sessions."""

    __tablename__ = "job_positions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )
    level: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default="mid"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )  # "active" | "archived"

    # Position description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    # ["Design and implement microservices", "Code review team members", ...]

    # Skill requirements (categorized)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    # [{"skill": "Python", "min_years": 3, "level": "proficient"}, ...]
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    # [{"skill": "Rust", "level": "familiar"}, ...]

    # Soft skill requirements
    soft_skill_requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"teamwork": "high", "communication": "high", "ownership": "high", "leadership": "medium"}

    # Domain / business knowledge
    domain_knowledge: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # ["FinTech", "High-concurrency systems", "Data processing"]

    # Interview defaults (can be overridden per session)
    default_total_questions: Mapped[int] = mapped_column(Integer, default=8)
    default_duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    interview_focus_areas: Mapped[list] = mapped_column(JSON, default=list)
    # ["System Design", "Code Quality", "Troubleshooting", "Team Collaboration"]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
