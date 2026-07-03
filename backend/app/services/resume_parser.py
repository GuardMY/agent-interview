"""Resume parsing service — extracts structured ResumeProfile via LLM."""

import json
import logging
import re

from app.llm.base import BaseLLMAdapter
from app.schemas.session import (
    EducationEntry,
    ProjectEntry,
    ResumeProfile,
    SkillEntry,
    WorkEntry,
)

logger = logging.getLogger(__name__)

RESUME_PARSE_SYSTEM_PROMPT = """You are a resume parsing expert. Extract structured information from the candidate's resume text.
Return ONLY valid JSON matching the schema below. Do not include any other text.

{
  "name": "Candidate full name",
  "years_of_experience": 5.5,
  "education": [
    {"school": "University Name", "degree": "Bachelor/Master/PhD", "major": "Computer Science", "year": "2020"}
  ],
  "skills": [
    {"name": "Python", "level_inferred": "expert", "years": 5.0},
    {"name": "Docker", "level_inferred": "proficient", "years": 3.0}
  ],
  "projects": [
    {
      "name": "Project Name",
      "description": "Brief description of the project",
      "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
      "role": "Backend Developer",
      "highlights": ["Designed RESTful APIs", "Improved performance by 30%"]
    }
  ],
  "work_history": [
    {
      "company": "Company Name",
      "title": "Software Engineer",
      "duration": "2020-2023",
      "highlights": ["Led migration to microservices", "Mentored 3 junior developers"]
    }
  ],
  "inferred_level": "mid",
  "key_strengths": ["Strong backend architecture skills", "Deep database knowledge"],
  "potential_risk_areas": ["No cloud deployment experience claimed", "Short tenure at last role"]
}

Rules:
- level_inferred: one of "familiar", "proficient", "expert"
- inferred_level: one of "junior", "mid", "senior" based on overall experience
- years_of_experience: total professional experience in years (float)
- Extract ALL skills mentioned, including those implied by projects
- Flag suspicious patterns in potential_risk_areas (tenure gaps, skill contradictions, etc.)
- If a field cannot be determined, use empty/default values
"""


class ResumeParserService:
    """Parses raw resume text into structured ResumeProfile using an LLM."""

    def __init__(self, llm: BaseLLMAdapter | None = None):
        self._llm = llm

    async def _get_llm(self) -> BaseLLMAdapter:
        """Lazy-init the LLM adapter using current config."""
        if self._llm is not None:
            return self._llm
        from app.llm.claude import ClaudeAdapter
        from app.llm.deepseek import DeepSeekAdapter
        from app.config import settings

        if settings.llm_provider == "anthropic":
            return ClaudeAdapter()
        elif settings.llm_provider == "openai":
            return DeepSeekAdapter(base_url="https://api.openai.com/v1")
        return DeepSeekAdapter()

    async def parse(self, resume_text: str) -> ResumeProfile | None:
        """Extract structured profile from resume text.

        Returns None if parsing fails after retries.
        """
        # Truncate very long resumes to avoid token limits
        max_chars = 8000
        if len(resume_text) > max_chars:
            logger.warning(
                f"Resume text truncated from {len(resume_text)} to {max_chars} chars"
            )
            resume_text = resume_text[:max_chars]

        llm = await self._get_llm()

        try:
            raw = await llm.generate(
                prompt=resume_text,
                system_prompt=RESUME_PARSE_SYSTEM_PROMPT,
                max_tokens=2000,
                temperature=0.2,
            )
            data = self._parse_json(raw)
            return self._build_profile(data)
        except Exception as exc:
            logger.error(f"Resume parsing failed: {exc}")
            return None

    def _parse_json(self, raw: str) -> dict:
        """Robust JSON extraction from LLM response."""
        # Strip code fences
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = raw.strip()

        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse LLM resume output: {raw[:500]}")
        return {}

    def _build_profile(self, data: dict) -> ResumeProfile:
        """Build ResumeProfile from parsed data, with defaults for missing fields."""
        try:
            return ResumeProfile(
                name=str(data.get("name", "")),
                years_of_experience=float(data.get("years_of_experience", 0)),
                education=[
                    EducationEntry(**e)
                    for e in data.get("education", [])
                    if isinstance(e, dict)
                ],
                skills=[
                    SkillEntry(
                        name=s.get("name", ""),
                        level_inferred=s.get("level_inferred", "familiar"),
                        years=float(s.get("years", 0)),
                    )
                    for s in data.get("skills", [])
                    if isinstance(s, dict) and s.get("name")
                ],
                projects=[
                    ProjectEntry(
                        name=p.get("name", ""),
                        description=p.get("description", ""),
                        tech_stack=p.get("tech_stack", []),
                        role=p.get("role", ""),
                        highlights=p.get("highlights", []),
                    )
                    for p in data.get("projects", [])
                    if isinstance(p, dict)
                ],
                work_history=[
                    WorkEntry(
                        company=w.get("company", ""),
                        title=w.get("title", ""),
                        duration=w.get("duration", ""),
                        highlights=w.get("highlights", []),
                    )
                    for w in data.get("work_history", [])
                    if isinstance(w, dict)
                ],
                inferred_level=str(data.get("inferred_level", "mid")),
                key_strengths=[
                    str(s) for s in data.get("key_strengths", []) if s
                ],
                potential_risk_areas=[
                    str(r) for r in data.get("potential_risk_areas", []) if r
                ],
            )
        except Exception as exc:
            logger.error(f"Failed to build ResumeProfile: {exc}")
            return ResumeProfile()
