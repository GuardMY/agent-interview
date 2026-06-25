import pytest

from app.core.evaluator import EvaluationEngine
from app.schemas.question import QuestionData


class TestEvaluationEngine:
    @pytest.fixture
    def engine(self, mock_llm) -> EvaluationEngine:
        return EvaluationEngine(mock_llm)

    @pytest.fixture
    def sample_question(self) -> QuestionData:
        return QuestionData(
            question_text="What is REST?",
            category="backend",
            difficulty="junior",
            expected_keywords=["HTTP", "stateless", "CRUD"],
        )

    @pytest.mark.asyncio
    async def test_evaluate_returns_valid_score(
        self, engine: EvaluationEngine, sample_question: QuestionData
    ) -> None:
        result = await engine.evaluate(sample_question, "REST uses HTTP and is stateless.")
        assert result.score == 4
        assert result.comment is not None
        assert len(result.strengths) > 0

    @pytest.mark.asyncio
    async def test_evaluate_handles_empty_answer(
        self, engine: EvaluationEngine, sample_question: QuestionData
    ) -> None:
        result = await engine.evaluate(sample_question, "I don't know.")
        assert 1 <= result.score <= 5

    @pytest.mark.asyncio
    async def test_fallback_on_malformed_json(self, mock_llm) -> None:
        # Override mock to return bad JSON
        class BadJsonMock:
            calls = []

            async def generate(self, prompt, system_prompt=None, max_tokens=1000, temperature=0.7):
                self.calls.append({"prompt": prompt})
                return "not valid json at all {{{"

        engine = EvaluationEngine(BadJsonMock())
        question = QuestionData(
            question_text="Test?",
            category="general",
            difficulty="junior",
            expected_keywords=[],
        )
        result = await engine.evaluate(question, "answer")
        assert result.score == 3  # Fallback score
        assert "manually" in result.comment.lower()

    @pytest.mark.asyncio
    async def test_parse_json_with_code_fences(
        self, engine: EvaluationEngine, sample_question: QuestionData
    ) -> None:
        # Verify the JSON parsing handles valid JSON from our mock
        result = await engine.evaluate(sample_question, "REST stands for Representational State Transfer.")
        assert isinstance(result.score, int)
        assert 1 <= result.score <= 5

    @pytest.mark.asyncio
    async def test_evaluation_result_has_required_fields(
        self, engine: EvaluationEngine, sample_question: QuestionData
    ) -> None:
        result = await engine.evaluate(sample_question, "An answer about REST.")
        assert hasattr(result, "score")
        assert hasattr(result, "comment")
        assert hasattr(result, "strengths")
        assert hasattr(result, "weaknesses")
        assert hasattr(result, "matched_keywords")
        assert hasattr(result, "missing_points")
