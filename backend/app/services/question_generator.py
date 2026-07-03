"""Dynamic question generator — LLM-driven question generation with source distribution.

Generates interview questions dynamically based on phase, strategy, and context.
Sources: 40% position requirements, 35% resume skills/risks, 25% CS fundamentals.
Falls back to QuestionBankService when LLM generation fails.
"""

import json
import logging
import random
import re

from app.llm.base import BaseLLMAdapter
from app.llm.prompts.phases import get_phase_prompt, get_follow_up_prompt
from app.models.job_position import JobPosition
from app.schemas.question import QuestionData
from app.schemas.session import (
    GapAnalysis,
    InterviewStrategy,
    PhaseConfig,
    ResumeProfile,
)
from app.services.question_bank import QuestionBankService

logger = logging.getLogger(__name__)

# Source distribution targets
SOURCE_WEIGHTS = {
    "position": 0.40,
    "resume": 0.35,
    "general": 0.25,
}


class DynamicQuestionGenerator:
    """Generates interview questions dynamically based on phase, strategy, and context."""

    def __init__(
        self,
        llm: BaseLLMAdapter,
        question_bank: QuestionBankService,
    ) -> None:
        self._llm = llm
        self._question_bank = question_bank
        # Track source distribution
        self._source_counts: dict[str, int] = {"position": 0, "resume": 0, "general": 0}
        self._used_topics: set[str] = set()

    async def generate_next(
        self,
        phase: PhaseConfig,
        strategy: InterviewStrategy,
        position: JobPosition | None,
        profile: ResumeProfile | None,
        gap: GapAnalysis | None,
        language: str = "en",
        parent_answer: str | None = None,
        current_depth: int = 0,
        question_number: int = 1,
    ) -> QuestionData | None:
        """Generate the next question for the current context.

        Args:
            phase: Current phase configuration
            strategy: The full interview strategy
            position: Bound job position (may be None)
            profile: Parsed resume profile (may be None)
            gap: Gap analysis result (may be None)
            language: "en" or "zh"
            parent_answer: If set, generates a follow-up
            current_depth: Follow-up depth (0 for top-level)
            question_number: Question number within the phase

        Returns:
            QuestionData or None (caller should fall back to question bank)
        """
        # Follow-up path
        if parent_answer is not None:
            return await self._generate_follow_up(
                phase=phase,
                strategy=strategy,
                position=position,
                parent_answer=parent_answer,
                current_depth=current_depth,
                language=language,
            )

        # Determine source bucket
        source = self._select_source()

        # Generate based on source
        q_data = None
        try:
            if source == "position" and position is not None:
                q_data = await self._generate_from_position(
                    position=position,
                    strategy=strategy,
                    phase=phase,
                    language=language,
                )
            elif source == "resume" and profile is not None:
                q_data = await self._generate_from_resume(
                    profile=profile,
                    gap=gap,
                    strategy=strategy,
                    phase=phase,
                    language=language,
                )
            else:
                q_data = await self._generate_general(
                    strategy=strategy,
                    phase=phase,
                    language=language,
                )

            if q_data is not None:
                self._source_counts[source] = self._source_counts.get(source, 0) + 1
                return q_data
        except Exception as exc:
            logger.warning(f"LLM question generation failed for source={source}: {exc}")

        # Fallback to question bank
        logger.info("Falling back to question bank for next question")
        return self._question_bank.select_question()

    # ── Source selection ───────────────────────────────────────

    def _select_source(self) -> str:
        """Select source bucket maintaining approximate 40/35/25 distribution."""
        total = sum(self._source_counts.values())
        if total == 0:
            # Start with position-driven for strategy mode
            return "position"

        # Calculate current ratios
        current_ratios = {
            k: v / total for k, v in self._source_counts.items()
        }

        # Find the source furthest below target
        deficits = {
            k: SOURCE_WEIGHTS.get(k, 0.25) - current_ratios.get(k, 0)
            for k in SOURCE_WEIGHTS
        }
        return max(deficits, key=deficits.get)  # type: ignore[arg-type]

    # ── Source-specific generators ─────────────────────────────

    async def _generate_from_position(
        self,
        position: JobPosition,
        strategy: InterviewStrategy,
        phase: PhaseConfig,
        language: str,
    ) -> QuestionData | None:
        """Generate a question from position requirements."""
        required = position.required_skills or []
        preferred = position.preferred_skills or []
        all_skills = required + preferred

        if not all_skills:
            return None

        # Pick a skill not yet used
        available = [s for s in all_skills if s.get("skill", "") not in self._used_topics]
        if not available:
            available = all_skills
        skill = random.choice(available)
        skill_name = skill.get("skill", "general programming")
        self._used_topics.add(skill_name)

        difficulty = self._calibrate_difficulty(
            base=position.level or "mid",
            strategy_difficulty=strategy.difficulty_strategy,
        )

        prompt = get_phase_prompt(
            "technical_assessment",
            language,
            source=f"position-driven (skill: {skill_name})",
            difficulty=difficulty,
            position_skills=skill_name,
            candidate_skills=", ".join(s.name for s in (profile.skills)) if hasattr(self, '_profile') else "unknown",
            gap_areas="N/A",
            difficulty_strategy=strategy.difficulty_strategy,
        )

        raw = await self._llm.generate(
            prompt=prompt,
            system_prompt="You are a technical interviewer. Generate ONE interview question. Output ONLY the question text, no labels or prefixes.",
            max_tokens=300,
            temperature=0.8,
        )

        if raw and raw.strip():
            return QuestionData(
                question_text=raw.strip(),
                category=skill.get("skill", "technical"),
                difficulty=difficulty,
                expected_keywords=[],
            )
        return None

    async def _generate_from_resume(
        self,
        profile: ResumeProfile,
        gap: GapAnalysis | None,
        strategy: InterviewStrategy,
        phase: PhaseConfig,
        language: str,
    ) -> QuestionData | None:
        """Generate a question targeting resume skill gaps or risks."""
        risk_areas = profile.potential_risk_areas or []
        skills = profile.skills or []

        if gap and gap.skills_missing:
            # Target a missing skill
            topic = random.choice(gap.skills_missing)
        elif risk_areas:
            topic = random.choice(risk_areas)
        elif skills:
            topic = random.choice(skills).name
        else:
            return None

        self._used_topics.add(topic)

        difficulty = self._calibrate_difficulty(
            base=profile.inferred_level or "mid",
            strategy_difficulty=strategy.difficulty_strategy,
        )

        prompt = get_phase_prompt(
            "technical_assessment",
            language,
            source=f"resume-driven (topic: {topic})",
            difficulty=difficulty,
            position_skills=", ".join(gap.skills_missing) if gap else "N/A",
            candidate_skills=", ".join(s.name for s in profile.skills[:5]),
            gap_areas=topic,
            difficulty_strategy=strategy.difficulty_strategy,
        )

        raw = await self._llm.generate(
            prompt=prompt,
            system_prompt="You are a technical interviewer. Generate ONE interview question. Output ONLY the question text, no labels or prefixes.",
            max_tokens=300,
            temperature=0.8,
        )

        if raw and raw.strip():
            return QuestionData(
                question_text=raw.strip(),
                category="technical",
                difficulty=difficulty,
                expected_keywords=[],
            )
        return None

    async def _generate_general(
        self,
        strategy: InterviewStrategy,
        phase: PhaseConfig,
        language: str,
    ) -> QuestionData | None:
        """Generate a general CS fundamentals question."""
        topics = [
            "Data structures", "Algorithms", "System design",
            "Design patterns", "Networking", "Databases",
            "Operating systems", "Concurrency",
            "数据结构", "算法", "系统设计", "设计模式", "网络", "数据库", "操作系统", "并发",
        ]
        topic = random.choice(topics)
        self._used_topics.add(topic)

        difficulty = self._calibrate_difficulty(
            base="mid",
            strategy_difficulty=strategy.difficulty_strategy,
        )

        prompt = get_phase_prompt(
            "technical_assessment",
            language,
            source="general CS fundamentals",
            difficulty=difficulty,
            position_skills="General CS knowledge",
            candidate_skills="To be assessed",
            gap_areas=topic,
            difficulty_strategy=strategy.difficulty_strategy,
        )

        raw = await self._llm.generate(
            prompt=prompt,
            system_prompt="You are a technical interviewer. Generate ONE interview question. Output ONLY the question text, no labels or prefixes.",
            max_tokens=300,
            temperature=0.8,
        )

        if raw and raw.strip():
            return QuestionData(
                question_text=raw.strip(),
                category="general",
                difficulty=difficulty,
                expected_keywords=[],
            )
        return None

    async def _generate_follow_up(
        self,
        phase: PhaseConfig,
        strategy: InterviewStrategy,
        position: JobPosition | None,
        parent_answer: str,
        current_depth: int,
        language: str,
    ) -> QuestionData | None:
        """Generate a follow-up question based on the candidate's answer."""
        position_skills = ""
        if position:
            skills = (position.required_skills or []) + (position.preferred_skills or [])
            position_skills = ", ".join(s.get("skill", "") for s in skills[:5])

        prompt = get_follow_up_prompt(
            "generate",
            language,
            question="(previous question)",
            answer=parent_answer,
            depth=str(current_depth),
            topic="the candidate's last response",
            position_skills=position_skills or "general technical skills",
        )

        raw = await self._llm.generate(
            prompt=prompt,
            system_prompt="You are a technical interviewer asking a follow-up question. Output ONLY the question, no labels.",
            max_tokens=250,
            temperature=0.7,
        )

        if raw and raw.strip():
            return QuestionData(
                question_text=raw.strip(),
                category="follow_up",
                difficulty="mid",
                expected_keywords=[],
            )
        return None

    # ── Difficulty calibration ─────────────────────────────────

    def _calibrate_difficulty(
        self,
        base: str,
        strategy_difficulty: str,
    ) -> str:
        """Adjust difficulty based on strategy."""
        levels = ["junior", "mid", "senior"]
        try:
            base_idx = levels.index(base)
        except ValueError:
            base_idx = 1

        if strategy_difficulty == "conservative":
            return levels[max(0, base_idx - 1)]
        elif strategy_difficulty == "aggressive":
            return levels[min(2, base_idx + 1)]
        return levels[base_idx]
