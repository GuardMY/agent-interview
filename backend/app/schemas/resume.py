from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResumeData(BaseModel):
    """LLM-parsed structured resume data."""

    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: str = ""  # "junior" | "mid" | "senior"
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    suggested_job_title: str = ""


class ResumeUploadResponse(BaseModel):
    resume_id: str
    filename: str
    file_size_bytes: int
    parse_status: str  # "pending" | "parsing" | "done" | "failed"
    parsed_data: ResumeData | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
