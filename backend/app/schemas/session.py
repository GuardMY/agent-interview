import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_html(v: str) -> str:
    """Remove HTML tags and trim whitespace."""
    return re.sub(r"<[^>]*>", "", v).strip()


class CreateSessionRequest(BaseModel):
    candidate_name: str = Field(..., min_length=1, max_length=100)
    job_title: str = Field(..., min_length=1, max_length=200)
    experience_level: str = Field(
        default="mid", pattern="^(junior|mid|senior)$"
    )
    key_skills: list[str] = Field(default_factory=list)
    interview_language: str = Field(default="en", pattern="^(en|zh)$")

    @field_validator("candidate_name", "job_title")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _strip_html(v)

    @field_validator("key_skills")
    @classmethod
    def sanitize_skills(cls, v: list[str]) -> list[str]:
        return [_strip_html(s) for s in v if s.strip()]


class SessionResponse(BaseModel):
    id: str
    candidate_name: str
    job_title: str
    experience_level: str
    interview_language: str
    status: str
    current_question_index: int
    total_questions: int
    started_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateSessionResponse(SessionResponse):
    """Returned only on session creation — includes auth tokens."""
    admin_token: str
    candidate_token: str
