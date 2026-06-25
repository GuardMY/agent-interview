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

        return self._build_result(raw_json)

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

    def _build_result(self, data: dict) -> EvaluationResult:
        """Build an EvaluationResult from raw dict, with validation."""
        score = data.get("score", 3)
        # Clamp score to valid range
        try:
            score = int(score)
            score = max(1, min(5, score))
        except (ValueError, TypeError):
            score = 3

        return EvaluationResult(
            score=score,
            comment=data.get("comment", "No evaluation available."),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            matched_keywords=data.get("matched_keywords", []),
            missing_points=data.get("missing_points", []),
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
