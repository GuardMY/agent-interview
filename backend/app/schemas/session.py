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
    position_id: str | None = Field(None, min_length=1, max_length=36)

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
    position_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateSessionResponse(SessionResponse):
    """Returned only on session creation — includes auth tokens."""
    admin_token: str
    candidate_token: str


class SessionListItem(BaseModel):
    """Session in a list view (no tokens)."""

    id: str
    candidate_name: str
    job_title: str
    experience_level: str
    interview_language: str
    status: str
    current_question_index: int
    total_questions: int
    position_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionListStats(BaseModel):
    """Aggregate statistics for the session list."""

    total_count: int
    active_count: int
    completed_count: int
    avg_score: float | None = None
    status_breakdown: dict[str, int] = {}


class SessionListResponse(BaseModel):
    """Paginated session list with aggregate stats."""

    items: list[SessionListItem]
    total: int
    page: int
    size: int
    pages: int
    stats: SessionListStats


# ── Resume-driven interview schemas (P1) ─────────────────────────


class EducationEntry(BaseModel):
    """Education record extracted from resume."""
    school: str = ""
    degree: str = ""
    major: str = ""
    year: str = ""


class SkillEntry(BaseModel):
    """Skill with inferred level from resume."""
    name: str
    level_inferred: str = "familiar"  # familiar | proficient | expert
    years: float = 0.0


class ProjectEntry(BaseModel):
    """Project experience extracted from resume."""
    name: str = ""
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    role: str = ""
    highlights: list[str] = Field(default_factory=list)


class WorkEntry(BaseModel):
    """Work history entry extracted from resume."""
    company: str = ""
    title: str = ""
    duration: str = ""
    highlights: list[str] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    """LLM-extracted structured profile from resume text."""
    name: str = ""
    years_of_experience: float = 0.0
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    work_history: list[WorkEntry] = Field(default_factory=list)
    inferred_level: str = "mid"  # junior | mid | senior
    key_strengths: list[str] = Field(default_factory=list)
    potential_risk_areas: list[str] = Field(default_factory=list)


class SkillMatch(BaseModel):
    """Single skill match between candidate and position."""
    skill_name: str
    required_level: str = "familiar"
    candidate_level: str = "familiar"
    is_gap: bool = False


class GapAnalysis(BaseModel):
    """Gap analysis between resume profile and job position."""
    position_id: str = ""
    position_title: str = ""

    # Skill matching
    skills_matched: list[SkillMatch] = Field(default_factory=list)
    skills_missing: list[str] = Field(default_factory=list)
    skills_exceeding: list[str] = Field(default_factory=list)
    skill_coverage_pct: float = 0.0

    # Experience matching
    experience_gap_summary: str = ""
    project_relevance_score: float = 0.0

    # Level matching
    candidate_inferred_level: str = "mid"
    position_target_level: str = "mid"
    level_delta: int = 0  # -1 (low), 0 (match), +1 (high)

    # Strategy hints
    recommended_focus_areas: list[str] = Field(default_factory=list)
    risk_areas: list[str] = Field(default_factory=list)


class TechFocusArea(BaseModel):
    """Technical focus area for interview questions."""
    topic: str
    source: str = "both"  # resume | position | both
    priority: int = 3  # 1-5
    suggested_difficulty: str = "mid"
    candidate_claimed_level: str = "familiar"
    position_required_level: str = "familiar"


class ProjectDeepDiveTarget(BaseModel):
    """Project selected for deep-dive during interview."""
    project_name: str
    relevance_to_position: int = 3  # 1-5
    suggested_angle: str = ""
    tech_stack_overlap_with_position: list[str] = Field(default_factory=list)


class BehavioralTheme(BaseModel):
    """Behavioral interview theme."""
    theme: str
    priority: int = 3  # 1-5
    source: str = "level"  # level | position | resume_gap
    position_context: str = ""
    suggested_questions: list[str] = Field(default_factory=list)


class ScoringWeights(BaseModel):
    """Dynamic scoring weights based on experience level."""
    technical_accuracy: float = 0.30
    depth_of_knowledge: float = 0.20
    problem_solving: float = 0.35
    communication: float = 0.15
    behavioral: float = 0.0
    position_match: float = 0.0


class PhaseConfig(BaseModel):
    """Configuration for a single interview phase."""
    phase_name: str
    max_duration_minutes: int = 10
    min_questions: int = 1
    max_questions: int = 3
    focus_areas: list[str] = Field(default_factory=list)


class InterviewStrategy(BaseModel):
    """Full interview strategy generated from resume + position + level."""
    session_id: str = ""

    # Input summaries
    resume_summary: str = ""
    position_summary: str = ""
    gap_analysis: GapAnalysis | None = None

    # Phase configuration
    phases: list[PhaseConfig] = Field(default_factory=list)

    # Technical focus
    tech_focus_areas: list[TechFocusArea] = Field(default_factory=list)

    # Project deep dive targets
    project_deep_dive_targets: list[ProjectDeepDiveTarget] = Field(default_factory=list)

    # Behavioral themes
    behavioral_themes: list[BehavioralTheme] = Field(default_factory=list)

    # Scoring
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)

    # Strategy tuning
    difficulty_strategy: str = "standard"  # conservative | standard | aggressive
    suggested_question_distribution: dict[str, int] = Field(default_factory=dict)


class ResumeUploadResponse(BaseModel):
    """Response after resume upload and parsing."""
    session_id: str
    status: str  # processing | completed | failed
    resume_text_length: int = 0
    profile: ResumeProfile | None = None
    message: str = ""
