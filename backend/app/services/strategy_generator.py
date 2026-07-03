"""Interview strategy generator — creates personalized interview plan from resume + position + gap analysis."""

import json
import logging
import re

from app.llm.base import BaseLLMAdapter
from app.models.job_position import JobPosition
from app.schemas.session import (
    BehavioralTheme,
    GapAnalysis,
    InterviewStrategy,
    PhaseConfig,
    ProjectDeepDiveTarget,
    ResumeProfile,
    ScoringWeights,
    TechFocusArea,
)

logger = logging.getLogger(__name__)

STRATEGY_SYSTEM_PROMPT = """You are an expert technical interviewer designing a personalized interview strategy.
Given a candidate's resume profile, a job position's requirements, and a gap analysis, create a detailed interview execution plan.

Return ONLY valid JSON matching this schema:
{
  "resume_summary": "One-sentence summary of the candidate",
  "position_summary": "One-sentence summary of the role",
  "phases": [
    {
      "phase_name": "ice_break",
      "max_duration_minutes": 5,
      "min_questions": 1,
      "max_questions": 2,
      "focus_areas": ["Current role confirmation", "Career motivation"]
    },
    {
      "phase_name": "project_deep_dive",
      "max_duration_minutes": 12,
      "min_questions": 2,
      "max_questions": 3,
      "focus_areas": ["Project architecture decisions", "Technical challenge handling"]
    },
    {
      "phase_name": "technical_assessment",
      "max_duration_minutes": 18,
      "min_questions": 3,
      "max_questions": 5,
      "focus_areas": ["Core language proficiency", "System design"]
    },
    {
      "phase_name": "behavioral",
      "max_duration_minutes": 8,
      "min_questions": 1,
      "max_questions": 3,
      "focus_areas": ["Team collaboration", "Growth mindset"]
    }
  ],
  "tech_focus_areas": [
    {
      "topic": "Python async programming",
      "source": "both",
      "priority": 5,
      "suggested_difficulty": "senior",
      "candidate_claimed_level": "expert",
      "position_required_level": "proficient"
    }
  ],
  "project_deep_dive_targets": [
    {
      "project_name": "E-commerce Platform",
      "relevance_to_position": 5,
      "suggested_angle": "Focus on microservice decomposition decisions and database sharding approach",
      "tech_stack_overlap_with_position": ["Python", "PostgreSQL", "Docker"]
    }
  ],
  "behavioral_themes": [
    {
      "theme": "Technical decision-making under pressure",
      "priority": 5,
      "source": "position",
      "position_context": "This role requires making architecture decisions with incomplete information",
      "suggested_questions": ["Tell me about a time you had to change your technical approach mid-project."]
    }
  ],
  "scoring_weights": {
    "technical_accuracy": 0.15,
    "depth_of_knowledge": 0.15,
    "problem_solving": 0.20,
    "communication": 0.10,
    "behavioral": 0.20,
    "position_match": 0.20
  },
  "difficulty_strategy": "standard",
  "suggested_question_distribution": {
    "project_deep_dive": 2,
    "technical_base": 2,
    "technical_deep": 2,
    "technical_scenario": 1,
    "behavioral": 2
  }
}

Phase names must be one of: "ice_break", "project_deep_dive", "technical_assessment", "behavioral", "candidate_qa", "wrapup"
source values: "resume", "position", "both", "level", "resume_gap"
difficulty_strategy: "conservative", "standard", "aggressive"
priority: 1-5 (5 = highest)
suggested_difficulty: "junior", "mid", "senior"
"""

# ── Level-based scoring weight presets ──────────────────────────────

WEIGHT_PRESETS: dict[str, ScoringWeights] = {
    "junior": ScoringWeights(
        technical_accuracy=0.20,
        depth_of_knowledge=0.10,
        problem_solving=0.15,
        communication=0.10,
        behavioral=0.20,
        position_match=0.25,
    ),
    "mid": ScoringWeights(
        technical_accuracy=0.15,
        depth_of_knowledge=0.15,
        problem_solving=0.20,
        communication=0.10,
        behavioral=0.20,
        position_match=0.20,
    ),
    "senior": ScoringWeights(
        technical_accuracy=0.10,
        depth_of_knowledge=0.20,
        problem_solving=0.25,
        communication=0.05,
        behavioral=0.20,
        position_match=0.20,
    ),
}

# ── Default phase configurations ────────────────────────────────────

DEFAULT_PHASES: list[PhaseConfig] = [
    PhaseConfig(phase_name="ice_break", max_duration_minutes=5, min_questions=1, max_questions=2,
                focus_areas=["Current role", "Career background", "Position awareness"]),
    PhaseConfig(phase_name="project_deep_dive", max_duration_minutes=12, min_questions=2, max_questions=3,
                focus_areas=["Project architecture", "Technical decisions", "Team collaboration"]),
    PhaseConfig(phase_name="technical_assessment", max_duration_minutes=18, min_questions=3, max_questions=5,
                focus_areas=["Core skills", "System design", "Problem solving"]),
    PhaseConfig(phase_name="behavioral", max_duration_minutes=8, min_questions=1, max_questions=3,
                focus_areas=["Teamwork", "Growth mindset", "Leadership"]),
    PhaseConfig(phase_name="candidate_qa", max_duration_minutes=5, min_questions=0, max_questions=5,
                focus_areas=["Role questions", "Team questions"]),
    PhaseConfig(phase_name="wrapup", max_duration_minutes=3, min_questions=0, max_questions=0,
                focus_areas=["Closing"]),
]

DEFAULT_QUESTION_DISTRIBUTION = {
    "project_deep_dive": 2,
    "technical_base": 2,
    "technical_deep": 2,
    "technical_scenario": 1,
    "behavioral": 2,
}


class StrategyGeneratorService:
    """Generates interview strategy from resume + position + gap analysis."""

    def __init__(self, llm: BaseLLMAdapter | None = None):
        self._llm = llm

    async def _get_llm(self) -> BaseLLMAdapter:
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

    async def generate(
        self,
        session_id: str,
        profile: ResumeProfile,
        position: JobPosition,
        gap: GapAnalysis | None = None,
        experience_level: str = "mid",
    ) -> InterviewStrategy:
        """Generate interview strategy. Falls back to deterministic defaults if LLM fails."""

        # ── Deterministic base ────────────────────────────────────
        scoring_weights = WEIGHT_PRESETS.get(experience_level, WEIGHT_PRESETS["mid"])

        # Map candidate skills to tech focus areas
        position_skill_names = {
            s.get("skill", "").lower(): s.get("level", "familiar")
            for s in (position.required_skills or [])
        }
        preferred_skill_names = {
            s.get("skill", "").lower(): s.get("level", "familiar")
            for s in (position.preferred_skills or [])
        }

        tech_focus_areas: list[TechFocusArea] = []
        for skill in profile.skills:
            if skill.name.lower() in position_skill_names:
                tech_focus_areas.append(
                    TechFocusArea(
                        topic=skill.name,
                        source="both",
                        priority=5,
                        suggested_difficulty=position.level,
                        candidate_claimed_level=skill.level_inferred,
                        position_required_level=position_skill_names[skill.name.lower()],
                    )
                )
            elif skill.name.lower() in preferred_skill_names:
                tech_focus_areas.append(
                    TechFocusArea(
                        topic=skill.name,
                        source="both",
                        priority=4,
                        suggested_difficulty=position.level,
                        candidate_claimed_level=skill.level_inferred,
                        position_required_level=preferred_skill_names[skill.name.lower()],
                    )
                )

        # Add position-unique required skills as focus areas (gaps)
        for skill_name, level in position_skill_names.items():
            if skill_name not in {s.name.lower() for s in profile.skills}:
                tech_focus_areas.append(
                    TechFocusArea(
                        topic=skill_name.replace("_", " ").title(),
                        source="position",
                        priority=5,
                        suggested_difficulty=experience_level,
                        candidate_claimed_level="familiar",
                        position_required_level=level,
                    )
                )

        # Project deep dive targets
        project_targets: list[ProjectDeepDiveTarget] = []
        position_tech_keywords = set(position_skill_names.keys()) | set(preferred_skill_names.keys())
        for proj in profile.projects:
            relevance = 1
            overlap: list[str] = []
            for tech in proj.tech_stack:
                tech_lower = tech.lower()
                if tech_lower in position_tech_keywords:
                    relevance = min(5, relevance + 2)
                    overlap.append(tech)
                elif any(pk in tech_lower for pk in position_tech_keywords):
                    relevance = min(5, relevance + 1)
                    overlap.append(tech)
            project_targets.append(
                ProjectDeepDiveTarget(
                    project_name=proj.name,
                    relevance_to_position=min(5, relevance),
                    suggested_angle=(
                        f"Explore {proj.name} architecture and technical decisions"
                    ),
                    tech_stack_overlap_with_position=list(set(overlap)),
                )
            )

        # Sort by relevance
        project_targets.sort(key=lambda t: t.relevance_to_position, reverse=True)

        # Behavioral themes
        soft_skills = position.soft_skill_requirements or {}
        behavioral_themes: list[BehavioralTheme] = []
        if soft_skills.get("teamwork") in ("medium", "high"):
            behavioral_themes.append(
                BehavioralTheme(
                    theme="Team collaboration",
                    priority=4,
                    source="position",
                    position_context="Position requires strong team collaboration",
                    suggested_questions=["Describe a cross-team project you led."],
                )
            )
        if soft_skills.get("leadership") in ("medium", "high") or experience_level == "senior":
            behavioral_themes.append(
                BehavioralTheme(
                    theme="Technical leadership",
                    priority=5 if experience_level == "senior" else 3,
                    source="level",
                    position_context="Senior role requires mentoring and technical direction",
                    suggested_questions=["How do you approach technical decision-making for your team?"],
                )
            )
        if soft_skills.get("ownership") in ("medium", "high"):
            behavioral_themes.append(
                BehavioralTheme(
                    theme="Ownership and accountability",
                    priority=3,
                    source="position",
                    position_context="Role requires end-to-end ownership",
                    suggested_questions=["Tell me about a time you took ownership of a failing project."],
                )
            )

        # Build deterministic strategy
        strategy = InterviewStrategy(
            session_id=session_id,
            resume_summary=f"{profile.name}: {profile.years_of_experience}y exp, {len(profile.skills)} skills, level ~{profile.inferred_level}",
            position_summary=f"{position.title} ({position.level}) — {position.department or 'N/A'}",
            gap_analysis=gap,
            phases=list(DEFAULT_PHASES),
            tech_focus_areas=tech_focus_areas,
            project_deep_dive_targets=project_targets[:3],
            behavioral_themes=behavioral_themes,
            scoring_weights=scoring_weights,
            difficulty_strategy=self._pick_difficulty(profile, gap),
            suggested_question_distribution=dict(DEFAULT_QUESTION_DISTRIBUTION),
        )

        # ── LLM enrichment ────────────────────────────────────────
        try:
            enriched = await self._llm_enrich(strategy, profile, position, gap)
            if enriched:
                return enriched
        except Exception as exc:
            logger.warning(f"LLM strategy enrichment failed: {exc}")

        return strategy

    def _pick_difficulty(
        self, profile: ResumeProfile, gap: GapAnalysis | None
    ) -> str:
        """Pick difficulty strategy based on candidate strength vs position."""
        if gap is None:
            return "standard"
        if gap.level_delta > 0:
            return "aggressive"  # Candidate stronger than position
        elif gap.level_delta < 0 or gap.skill_coverage_pct < 60:
            return "conservative"  # Candidate weaker — verify basics
        return "standard"

    async def _llm_enrich(
        self,
        strategy: InterviewStrategy,
        profile: ResumeProfile,
        position: JobPosition,
        gap: GapAnalysis | None,
    ) -> InterviewStrategy | None:
        """Use LLM to generate a richer, more personalized strategy."""
        llm = await self._get_llm()

        prompt_parts = [
            "## Candidate",
            f"Name: {profile.name}",
            f"Years of Experience: {profile.years_of_experience}",
            f"Skills: {', '.join(s.name + ' (' + s.level_inferred + ', ' + str(s.years) + 'y)' for s in profile.skills)}",
            f"Projects: {', '.join(p.name for p in profile.projects)}",
            f"Strengths: {', '.join(profile.key_strengths)}",
            f"Risks: {', '.join(profile.potential_risk_areas)}",
            f"Inferred Level: {profile.inferred_level}",
            "",
            "## Position",
            f"Title: {position.title} ({position.level})",
            f"Department: {position.department}",
            f"Required Skills: {json.dumps(position.required_skills or [])}",
            f"Preferred Skills: {json.dumps(position.preferred_skills or [])}",
            f"Responsibilities: {json.dumps(position.responsibilities or [])}",
            f"Soft Skills: {json.dumps(position.soft_skill_requirements or {})}",
            f"Focus Areas: {json.dumps(position.interview_focus_areas or [])}",
            "",
            "## Gap Analysis",
            json.dumps(gap.model_dump() if gap else {}, default=str),
        ]

        raw = await llm.generate(
            prompt="\n".join(prompt_parts),
            system_prompt=STRATEGY_SYSTEM_PROMPT,
            max_tokens=2000,
            temperature=0.4,
        )

        data = self._parse_json(raw)
        if not data:
            return None

        # Merge LLM output into strategy
        strategy.resume_summary = str(data.get("resume_summary", strategy.resume_summary))
        strategy.position_summary = str(data.get("position_summary", strategy.position_summary))
        strategy.difficulty_strategy = str(data.get("difficulty_strategy", strategy.difficulty_strategy))

        if data.get("phases"):
            strategy.phases = [
                PhaseConfig(**p) for p in data["phases"] if isinstance(p, dict)
            ] or strategy.phases

        if data.get("tech_focus_areas"):
            strategy.tech_focus_areas = [
                TechFocusArea(**t) for t in data["tech_focus_areas"] if isinstance(t, dict)
            ] or strategy.tech_focus_areas

        if data.get("project_deep_dive_targets"):
            strategy.project_deep_dive_targets = [
                ProjectDeepDiveTarget(**t) for t in data["project_deep_dive_targets"] if isinstance(t, dict)
            ] or strategy.project_deep_dive_targets

        if data.get("behavioral_themes"):
            strategy.behavioral_themes = [
                BehavioralTheme(**b) for b in data["behavioral_themes"] if isinstance(b, dict)
            ] or strategy.behavioral_themes

        if data.get("scoring_weights"):
            strategy.scoring_weights = ScoringWeights(**data["scoring_weights"])

        if data.get("suggested_question_distribution"):
            strategy.suggested_question_distribution = data["suggested_question_distribution"]

        return strategy

    def _parse_json(self, raw: str) -> dict:
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger.warning(f"Could not parse LLM strategy output: {raw[:500]}")
        return {}
