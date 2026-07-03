"""Pydantic schemas for JobPosition CRUD operations."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_html(v: str) -> str:
    """Remove HTML tags and trim whitespace."""
    return re.sub(r"<[^>]*>", "", v).strip()


# ── Nested models ──────────────────────────────────────────────


class SkillRequirement(BaseModel):
    """A single skill requirement entry."""
    skill: str = Field(..., min_length=1, max_length=100)
    min_years: int = Field(default=0, ge=0)
    level: str = Field(default="familiar", pattern="^(familiar|proficient|expert)$")


class SoftSkillRequirements(BaseModel):
    """Soft skill expectations for the position."""
    teamwork: str = Field(default="medium", pattern="^(low|medium|high)$")
    communication: str = Field(default="medium", pattern="^(low|medium|high)$")
    ownership: str = Field(default="medium", pattern="^(low|medium|high)$")
    leadership: str = Field(default="low", pattern="^(low|medium|high)$")


# ── Request schemas ────────────────────────────────────────────


class JobPositionCreate(BaseModel):
    """Create a new job position."""
    title: str = Field(..., min_length=1, max_length=200)
    department: str = Field(default="", max_length=100)
    level: str = Field(default="mid", pattern="^(junior|mid|senior)$")
    description: str | None = Field(None, max_length=5000)
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[SkillRequirement] = Field(default_factory=list)
    preferred_skills: list[SkillRequirement] = Field(default_factory=list)
    soft_skill_requirements: SoftSkillRequirements = Field(
        default_factory=SoftSkillRequirements
    )
    domain_knowledge: list[str] | None = Field(default=None)
    default_total_questions: int = Field(default=8, ge=1, le=30)
    default_duration_minutes: int = Field(default=45, ge=5, le=180)
    interview_focus_areas: list[str] = Field(default_factory=list)

    @field_validator("title", "department")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _strip_html(v)

    @field_validator("responsibilities", "domain_knowledge", "interview_focus_areas")
    @classmethod
    def sanitize_list(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [_strip_html(s) for s in v if s.strip()]


class JobPositionUpdate(BaseModel):
    """Update an existing job position — all fields optional."""
    title: str | None = Field(None, min_length=1, max_length=200)
    department: str | None = Field(None, max_length=100)
    level: str | None = Field(None, pattern="^(junior|mid|senior)$")
    description: str | None = Field(None, max_length=5000)
    responsibilities: list[str] | None = None
    required_skills: list[SkillRequirement] | None = None
    preferred_skills: list[SkillRequirement] | None = None
    soft_skill_requirements: SoftSkillRequirements | None = None
    domain_knowledge: list[str] | None = None
    default_total_questions: int | None = Field(None, ge=1, le=30)
    default_duration_minutes: int | None = Field(None, ge=5, le=180)
    interview_focus_areas: list[str] | None = None

    @field_validator("title", "department")
    @classmethod
    def sanitize_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _strip_html(v)


# ── Response schemas ───────────────────────────────────────────


class JobPositionResponse(BaseModel):
    """Full job position response."""
    id: str
    title: str
    department: str
    level: str
    status: str
    description: str | None = None
    responsibilities: list[str] = []
    required_skills: list[dict] = []
    preferred_skills: list[dict] = []
    soft_skill_requirements: dict = {}
    domain_knowledge: list[str] | None = None
    default_total_questions: int = 8
    default_duration_minutes: int = 45
    interview_focus_areas: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobPositionListItem(BaseModel):
    """Brief position info for list views."""
    id: str
    title: str
    department: str
    level: str
    status: str
    default_total_questions: int
    default_duration_minutes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobPositionListResponse(BaseModel):
    """Paginated job position list."""
    items: list[JobPositionListItem]
    total: int
    page: int
    size: int
    pages: int
