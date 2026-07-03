import json
import logging
import re
from typing import TYPE_CHECKING

from app.llm.base import BaseLLMAdapter
from app.llm.prompts.scoring import get_scoring_prompt, get_scoring_prompt_v2
from app.schemas.evaluation import (
    BehavioralDimensions,
    EvaluationDimensions,
    EvaluationResult,
    PositionMatchDimensions,
)
from app.schemas.question import QuestionData

if TYPE_CHECKING:
    from app.schemas.session import ScoringWeights

logger = logging.getLogger(__name__)

# Default weights for simple mode (4-dimension legacy)
DEFAULT_WEIGHTS = {
    "technical_accuracy": 0.30,
    "depth_of_knowledge": 0.20,
    "communication": 0.15,
    "problem_solving": 0.35,
}


class EvaluationEngine:
    """Evaluates candidate answers using LLM-based scoring.

    Supports two modes:
    - Simple mode: 4-dimension scoring with hardcoded weights (legacy)
    - Strategy mode: Phase-aware scoring with dynamic weights including
      behavioral + position_match dimensions
    """

    def __init__(self, llm: BaseLLMAdapter) -> None:
        self._llm = llm

    async def evaluate(
        self,
        question: QuestionData,
        answer: str,
        language: str = "en",
        *,
        weights: "ScoringWeights | None" = None,
        phase: str | None = None,
        position_context: str | None = None,
    ) -> EvaluationResult:
        """Score a candidate's answer. Falls back to default on failure.

        Args:
            question: The question data
            answer: The candidate's answer text
            language: "en" or "zh"
            weights: Dynamic scoring weights (strategy mode). If None, uses defaults.
            phase: Current interview phase for phase-aware prompts
            position_context: Position summary for context injection
        """
        # Choose prompt: V2 (phase-aware) or V1 (simple)
        if phase and phase in (
            "ice_break", "project_deep_dive", "technical_assessment",
            "behavioral", "candidate_qa", "wrapup",
        ):
            template = get_scoring_prompt_v2(
                language=language,
                phase=phase,
                position_context=position_context or "",
            )
        else:
            template = get_scoring_prompt(language)

        prompt = template.format(
            question_text=question.question_text,
            category=question.category,
            difficulty=question.difficulty,
            expected_keywords=", ".join(question.expected_keywords),
            candidate_answer=answer,
        )

        raw_json: dict | None = None
        try:
            response = await self._llm.generate(
                prompt=prompt,
                max_tokens=600,
                temperature=0.3,
            )
            logger.debug(f"Scoring raw response: {response[:300]}")
            raw_json = self._parse_json(response)
        except Exception as e:
            logger.warning(f"LLM evaluation failed: {e}. Using fallback score.")

        if raw_json is None:
            return self._fallback_result(language)

        return self._build_result(raw_json, language, weights=weights)

    # ── JSON parsing ──────────────────────────────────────────

    def _parse_json(self, raw: str) -> dict | None:
        """Robust JSON parsing with multiple fallback strategies."""
        raw = raw.strip()

        # 1. Remove code fences
        fence_match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?```", raw
        )
        if fence_match:
            raw = fence_match.group(1).strip()

        # 2. Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 3. Extract first JSON object
        brace_match = re.search(r"\{[\s\S]*\}", raw)
        if brace_match:
            extracted = brace_match.group(0)
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                # 4. Fix common issues: trailing commas, unquoted keys
                try:
                    fixed = re.sub(r",\s*}", "}", extracted)
                    fixed = re.sub(r",\s*]", "]", fixed)
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        # 5. Last resort: regex extract score + comment
        logger.warning(f"Could not parse scoring JSON from: {raw[:200]}")
        score_match = re.search(r'"score"\s*:\s*(\d)', raw)
        comment_match = re.search(r'"comment"\s*:\s*"([^"]*)"', raw)
        if score_match:
            return {
                "score": int(score_match.group(1)),
                "comment": comment_match.group(1) if comment_match else "",
                "strengths": [],
                "weaknesses": [],
                "matched_keywords": [],
                "missing_points": [],
            }

        return None

    # ── Dimension parsing ─────────────────────────────────────

    def _parse_dimensions(self, data: dict) -> EvaluationDimensions | None:
        """Parse core + extended dimension scores from LLM output."""
        dims_raw = data.get("dimensions")
        if not isinstance(dims_raw, dict):
            return None

        try:
            behavioral = self._parse_behavioral_dimensions(dims_raw)
            position_match = self._parse_position_match_dimensions(dims_raw)

            return EvaluationDimensions(
                technical_accuracy=self._clamp_dim(dims_raw.get("technical_accuracy")),
                depth_of_knowledge=self._clamp_dim(dims_raw.get("depth_of_knowledge")),
                communication=self._clamp_dim(dims_raw.get("communication")),
                problem_solving=self._clamp_dim(dims_raw.get("problem_solving")),
                behavioral=behavioral,
                position_match=position_match,
            )
        except Exception:
            # Fallback: parse only core 4 dimensions
            try:
                return EvaluationDimensions(
                    technical_accuracy=self._clamp_dim(dims_raw.get("technical_accuracy")),
                    depth_of_knowledge=self._clamp_dim(dims_raw.get("depth_of_knowledge")),
                    communication=self._clamp_dim(dims_raw.get("communication")),
                    problem_solving=self._clamp_dim(dims_raw.get("problem_solving")),
                )
            except Exception:
                return None

    def _parse_behavioral_dimensions(self, dims_raw: dict) -> BehavioralDimensions | None:
        """Parse behavioral sub-dimensions if present."""
        keys = ("teamwork", "leadership", "ownership", "growth_mindset", "culture_fit")
        if not any(k in dims_raw for k in keys):
            return None
        return BehavioralDimensions(
            teamwork=self._clamp_opt_dim(dims_raw.get("teamwork")),
            leadership=self._clamp_opt_dim(dims_raw.get("leadership")),
            ownership=self._clamp_opt_dim(dims_raw.get("ownership")),
            growth_mindset=self._clamp_opt_dim(dims_raw.get("growth_mindset")),
            culture_fit=self._clamp_opt_dim(dims_raw.get("culture_fit")),
        )

    def _parse_position_match_dimensions(self, dims_raw: dict) -> PositionMatchDimensions | None:
        """Parse position match sub-dimensions if present."""
        keys = ("skill_coverage", "experience_alignment", "level_alignment",
                "domain_fit", "growth_potential")
        if not any(k in dims_raw for k in keys):
            return None
        return PositionMatchDimensions(
            skill_coverage=self._clamp_opt_dim(dims_raw.get("skill_coverage")),
            experience_alignment=self._clamp_opt_dim(dims_raw.get("experience_alignment")),
            level_alignment=self._clamp_opt_dim(dims_raw.get("level_alignment")),
            domain_fit=self._clamp_opt_dim(dims_raw.get("domain_fit")),
            growth_potential=self._clamp_opt_dim(dims_raw.get("growth_potential")),
        )

    # ── Clamping helpers ──────────────────────────────────────

    @staticmethod
    def _clamp_dim(value: object) -> int:
        """Clamp a dimension score to 1-5, defaulting to 3."""
        try:
            return max(1, min(5, int(value)))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return 3

    @staticmethod
    def _clamp_opt_dim(value: object) -> int | None:
        """Clamp an optional dimension score. Returns None if missing."""
        if value is None:
            return None
        try:
            return max(1, min(5, int(value)))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return None

    # ── Score computation ─────────────────────────────────────

    def _compute_weighted_score(
        self,
        dimensions: EvaluationDimensions,
        weights: "ScoringWeights | None" = None,
    ) -> int:
        """Compute overall score as weighted average of dimensions.

        Uses dynamic weights from strategy when available, falling back
        to hardcoded 4-dimension defaults for simple mode.
        """
        total = 0.0
        weight_sum = 0.0

        # Core 4 dimensions always present
        core_map = {
            "technical_accuracy": dimensions.technical_accuracy,
            "depth_of_knowledge": dimensions.depth_of_knowledge,
            "communication": dimensions.communication,
            "problem_solving": dimensions.problem_solving,
        }

        for dim_name, dim_value in core_map.items():
            w = getattr(weights, dim_name, None) if weights else None
            if w is None:
                w = DEFAULT_WEIGHTS.get(dim_name, 0.25)
            total += dim_value * w
            weight_sum += w

        # Behavioral dimensions (if present and have scores)
        if dimensions.behavioral and weights:
            b = dimensions.behavioral
            b_map = {
                "teamwork": b.teamwork,
                "leadership": b.leadership,
                "ownership": b.ownership,
                "growth_mindset": b.growth_mindset,
                "culture_fit": b.culture_fit,
            }
            for dim_name, dim_value in b_map.items():
                if dim_value is not None and getattr(weights, dim_name, 0) > 0:
                    w = getattr(weights, dim_name, 0)
                    total += dim_value * w
                    weight_sum += w

        # Position match dimensions (if present and have scores)
        if dimensions.position_match and weights:
            pm = dimensions.position_match
            pm_map = {
                "skill_coverage": pm.skill_coverage,
                "experience_alignment": pm.experience_alignment,
                "level_alignment": pm.level_alignment,
                "domain_fit": pm.domain_fit,
                "growth_potential": pm.growth_potential,
            }
            for dim_name, dim_value in pm_map.items():
                if dim_value is not None and getattr(weights, dim_name, 0) > 0:
                    w = getattr(weights, dim_name, 0)
                    total += dim_value * w
                    weight_sum += w

        if weight_sum == 0:
            return 3
        return max(1, min(5, round(total / weight_sum)))

    # ── Result building ───────────────────────────────────────

    def _build_result(
        self,
        data: dict,
        language: str = "en",
        weights: "ScoringWeights | None" = None,
    ) -> EvaluationResult:
        """Build an EvaluationResult from raw dict, with validation."""
        dimensions = self._parse_dimensions(data)

        if dimensions is not None:
            score = self._compute_weighted_score(dimensions, weights=weights)
        else:
            score = data.get("score", 3)
            try:
                score = int(score)
                score = max(1, min(5, score))
            except (ValueError, TypeError):
                score = 3

        default_comment = (
            "无法自动评估，请人工审核。"
            if language == "zh" else
            "Unable to evaluate automatically. Please review manually."
        )

        # Extract extended fields
        behavioral = dimensions.behavioral if dimensions else None
        position_match = dimensions.position_match if dimensions else None

        return EvaluationResult(
            score=score,
            comment=data.get("comment", default_comment),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            matched_keywords=data.get("matched_keywords", []),
            missing_points=data.get("missing_points", []),
            dimensions=dimensions,
            behavioral=behavioral,
            position_match=position_match,
        )

    def _fallback_result(self, language: str = "en") -> EvaluationResult:
        """Return a neutral fallback when LLM evaluation fails."""
        return EvaluationResult(
            score=3,
            comment=(
                "无法自动评估，请人工审核。"
                if language == "zh" else
                "Unable to evaluate automatically. Please review manually."
            ),
            strengths=[],
            weaknesses=[],
            matched_keywords=[],
            missing_points=[],
        )
