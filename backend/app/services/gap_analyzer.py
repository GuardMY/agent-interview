"""Gap analysis service — compares ResumeProfile with JobPosition requirements."""

import json
import logging
import re
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import BaseLLMAdapter
from app.models.job_position import JobPosition
from app.schemas.session import GapAnalysis, ResumeProfile, SkillMatch

logger = logging.getLogger(__name__)

GAP_ANALYSIS_SYSTEM_PROMPT = """You are an interview strategy analyst. Given a candidate's resume profile and a job position's requirements, analyze the gaps and matches.

Return ONLY valid JSON matching this schema:
{
  "skills_matched": [
    {"skill_name": "Python", "required_level": "proficient", "candidate_level": "expert", "is_gap": false}
  ],
  "skills_missing": ["Kubernetes", "Terraform"],
  "skills_exceeding": ["Rust", "GraphQL"],
  "skill_coverage_pct": 75.0,
  "experience_gap_summary": "Candidate has 3 years of backend experience but position requires 5 years in high-concurrency systems.",
  "project_relevance_score": 3.5,
  "candidate_inferred_level": "mid",
  "position_target_level": "senior",
  "level_delta": -1,
  "recommended_focus_areas": ["System design", "High-concurrency patterns", "Team leadership"],
  "risk_areas": ["No experience with required cloud platform", "Frequent job changes"]
}

Rules:
- level values: "familiar", "proficient", "expert"
- candidate/position levels: "junior", "mid", "senior"
- level_delta: -1 (candidate lower), 0 (match), +1 (candidate higher)
- skill_coverage_pct: percentage of required+preferred skills the candidate covers (0-100)
- project_relevance_score: 1-5 scale how relevant candidate projects are to position
- Be specific in experience_gap_summary — mention concrete numbers and domains
"""


class GapAnalyzerService:
    """Analyzes gaps between a parsed ResumeProfile and a JobPosition."""

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

    async def analyze(
        self,
        profile: ResumeProfile,
        position: JobPosition,
    ) -> GapAnalysis | None:
        """Run gap analysis between resume profile and job position.

        First performs a deterministic comparison, then enriches with LLM analysis.
        """
        # ── Deterministic skill coverage ──────────────────────────
        candidate_skill_names = {s.name.lower() for s in profile.skills}
        candidate_skill_map = {
            s.name.lower(): s.level_inferred for s in profile.skills
        }

        required_names = {s.get("skill", "").lower() for s in (position.required_skills or [])}
        preferred_names = {s.get("skill", "").lower() for s in (position.preferred_skills or [])}
        all_position_skills = required_names | preferred_names

        # Build skill matches
        skills_matched: list[SkillMatch] = []
        skills_missing: list[str] = []

        for skill_data in (position.required_skills or []):
            skill_name = skill_data.get("skill", "")
            required_level = skill_data.get("level", "familiar")
            candidate_level = candidate_skill_map.get(skill_name.lower(), "familiar")
            is_gap = skill_name.lower() not in candidate_skill_names

            skills_matched.append(
                SkillMatch(
                    skill_name=skill_name,
                    required_level=required_level,
                    candidate_level=candidate_level,
                    is_gap=is_gap,
                )
            )
            if is_gap:
                skills_missing.append(skill_name)

        for skill_data in (position.preferred_skills or []):
            skill_name = skill_data.get("skill", "")
            if skill_name.lower() not in required_names:
                required_level = skill_data.get("level", "familiar")
                candidate_level = candidate_skill_map.get(skill_name.lower(), "familiar")
                is_gap = skill_name.lower() not in candidate_skill_names
                skills_matched.append(
                    SkillMatch(
                        skill_name=skill_name,
                        required_level=required_level,
                        candidate_level=candidate_level,
                        is_gap=is_gap,
                    )
                )
                if is_gap:
                    skills_missing.append(skill_name)

        # Skills the candidate has that the position doesn't require
        skills_exceeding = [
            s.name for s in profile.skills
            if s.name.lower() not in all_position_skills
        ]

        # Coverage percentage
        total_position_skills = len(all_position_skills)
        covered = total_position_skills - len(
            [m for m in skills_matched if m.is_gap]
        )
        skill_coverage_pct = (
            round(covered / total_position_skills * 100, 1)
            if total_position_skills > 0
            else 100.0
        )

        # Level comparison
        level_order = {"junior": 0, "mid": 1, "senior": 2}
        candidate_idx = level_order.get(profile.inferred_level, 1)
        position_idx = level_order.get(position.level, 1)
        level_delta = candidate_idx - position_idx

        # Deterministic base result
        gap = GapAnalysis(
            position_id=position.id,
            position_title=position.title,
            skills_matched=skills_matched,
            skills_missing=skills_missing,
            skills_exceeding=skills_exceeding,
            skill_coverage_pct=skill_coverage_pct,
            candidate_inferred_level=profile.inferred_level,
            position_target_level=position.level,
            level_delta=level_delta,
        )

        # ── LLM enrichment ────────────────────────────────────────
        try:
            enriched = await self._llm_enrich(gap, profile, position)
            if enriched:
                return enriched
        except Exception as exc:
            logger.warning(f"LLM gap analysis enrichment failed: {exc}")

        # Fall back to deterministic result
        gap.experience_gap_summary = (
            f"Candidate level ({profile.inferred_level}) vs "
            f"position level ({position.level}): "
            f"{'above' if level_delta > 0 else 'below' if level_delta < 0 else 'matches'} target. "
            f"Skill coverage: {skill_coverage_pct}%."
        )
        gap.recommended_focus_areas = skills_missing[:5] if skills_missing else ["General technical assessment"]
        gap.risk_areas = profile.potential_risk_areas[:5]
        return gap

    async def _llm_enrich(
        self,
        gap: GapAnalysis,
        profile: ResumeProfile,
        position: JobPosition,
    ) -> GapAnalysis | None:
        """Use LLM to enrich the gap analysis with qualitative insights."""
        llm = await self._get_llm()

        prompt_parts = [
            "## Candidate Resume Profile",
            f"Name: {profile.name}",
            f"Years of Experience: {profile.years_of_experience}",
            f"Inferred Level: {profile.inferred_level}",
            f"Skills: {', '.join(s.name + ' (' + s.level_inferred + ')' for s in profile.skills)}",
            f"Key Strengths: {', '.join(profile.key_strengths)}",
            f"Risk Areas: {', '.join(profile.potential_risk_areas)}",
            "",
            "## Job Position Requirements",
            f"Title: {position.title}",
            f"Level: {position.level}",
            f"Required Skills: {json.dumps(position.required_skills or [])}",
            f"Preferred Skills: {json.dumps(position.preferred_skills or [])}",
            f"Responsibilities: {json.dumps(position.responsibilities or [])}",
            f"Focus Areas: {json.dumps(position.interview_focus_areas or [])}",
            "",
            "## Deterministic Analysis",
            f"Skill Coverage: {gap.skill_coverage_pct}%",
            f"Missing Skills: {', '.join(gap.skills_missing)}",
            f"Level Delta: {gap.level_delta}",
        ]

        raw = await llm.generate(
            prompt="\n".join(prompt_parts),
            system_prompt=GAP_ANALYSIS_SYSTEM_PROMPT,
            max_tokens=1500,
            temperature=0.3,
        )

        data = self._parse_json(raw)
        if not data:
            return None

        # Merge LLM enrichment into the deterministic base
        gap.experience_gap_summary = str(data.get("experience_gap_summary", gap.experience_gap_summary))
        gap.project_relevance_score = float(data.get("project_relevance_score", 0))
        gap.recommended_focus_areas = [
            str(a) for a in data.get("recommended_focus_areas", []) if a
        ] or gap.recommended_focus_areas
        gap.risk_areas = [
            str(r) for r in data.get("risk_areas", []) if r
        ] or gap.risk_areas

        return gap

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
        logger.warning(f"Could not parse LLM gap analysis output: {raw[:500]}")
        return {}
