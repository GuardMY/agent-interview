import json
import logging
import re

from app.llm.base import BaseLLMAdapter
from app.llm.prompts.scoring import get_scoring_prompt
from app.schemas.evaluation import EvaluationResult
from app.schemas.question import QuestionData

logger = logging.getLogger(__name__)


class EvaluationEngine:
    """Evaluates candidate answers using LLM-based scoring."""

    def __init__(self, llm: BaseLLMAdapter) -> None:
        self._llm = llm

    async def evaluate(
        self, question: QuestionData, answer: str, language: str = "en"
    ) -> EvaluationResult:
        """Score a candidate's answer. Falls back to default on failure."""
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
                max_tokens=500,
                temperature=0.3,
            )
            logger.debug(f"Scoring raw response: {response[:300]}")
            raw_json = self._parse_json(response)
        except Exception as e:
            logger.warning(f"LLM evaluation failed: {e}. Using fallback score.")

        if raw_json is None:
            return self._fallback_result(language)

        return self._build_result(raw_json, language)

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

    # Dimension weights for computing overall score from subscores
    DIMENSION_WEIGHTS = {
        "technical_accuracy": 0.30,
        "depth_of_knowledge": 0.20,
        "communication": 0.15,
        "problem_solving": 0.35,
    }

    def _parse_dimensions(self, data: dict) -> "EvaluationDimensions | None":
        """Parse dimension scores from LLM output, return None if missing."""
        from app.schemas.evaluation import EvaluationDimensions

        dims_raw = data.get("dimensions")
        if not isinstance(dims_raw, dict):
            return None

        try:
            return EvaluationDimensions(
                technical_accuracy=self._clamp_dim(dims_raw.get("technical_accuracy")),
                depth_of_knowledge=self._clamp_dim(dims_raw.get("depth_of_knowledge")),
                communication=self._clamp_dim(dims_raw.get("communication")),
                problem_solving=self._clamp_dim(dims_raw.get("problem_solving")),
            )
        except Exception:
            return None

    @staticmethod
    def _clamp_dim(value: object) -> int:
        """Clamp a dimension score to 1-5, defaulting to 3."""
        try:
            return max(1, min(5, int(value)))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return 3

    def _compute_weighted_score(self, dimensions: "EvaluationDimensions") -> int:
        """Compute overall score as weighted average of dimensions."""
        total = 0.0
        total += dimensions.technical_accuracy * self.DIMENSION_WEIGHTS["technical_accuracy"]
        total += dimensions.depth_of_knowledge * self.DIMENSION_WEIGHTS["depth_of_knowledge"]
        total += dimensions.communication * self.DIMENSION_WEIGHTS["communication"]
        total += dimensions.problem_solving * self.DIMENSION_WEIGHTS["problem_solving"]
        return max(1, min(5, round(total)))

    def _build_result(self, data: dict, language: str = "en") -> EvaluationResult:
        """Build an EvaluationResult from raw dict, with validation."""
        # Parse dimensions first (so we can compute score from them)
        dimensions = self._parse_dimensions(data)

        if dimensions is not None:
            # Server-side weighted average (more reliable than LLM-calculated)
            score = self._compute_weighted_score(dimensions)
        else:
            # Fallback: use LLM-reported score
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
        return EvaluationResult(
            score=score,
            comment=data.get("comment", default_comment),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            matched_keywords=data.get("matched_keywords", []),
            missing_points=data.get("missing_points", []),
            dimensions=dimensions,
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
