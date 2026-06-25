import json
from tempfile import NamedTemporaryFile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.llm.base import BaseLLMAdapter
from app.schemas.question import QuestionData


# ── Database fixtures ──────────────────────────────────────────

@pytest.fixture
async def test_engine():
    """In-memory SQLite engine for fast tests."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine):
    """Async session bound to in-memory SQLite."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


# ── Mock LLM fixture ───────────────────────────────────────────

class MockLLM(BaseLLMAdapter):
    """Returns predefined responses without calling any API."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        self.calls.append({
            "prompt_snippet": prompt[:100],
            "system_snippet": (system_prompt or "")[:100],
            "max_tokens": max_tokens,
            "temperature": temperature,
        })

        # Scoring response
        if "evaluate" in prompt.lower() or "scoring" in prompt.lower() or "Evaluate" in prompt:
            return (
                '{"score": 4, "comment": "Good answer with clear understanding.", '
                '"strengths": ["clear explanation", "covered key points"], '
                '"weaknesses": ["could add examples"], '
                '"matched_keywords": ["REST", "HTTP", "stateless"], '
                '"missing_points": ["caching considerations"]}'
            )

        # Intent detection
        if "intent" in prompt.lower() or "classify" in prompt.lower():
            return '{"intent": "answer", "confidence": 0.95}'

        # Default: natural language
        return "Thank you for your response. Let's continue with the next question."


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM()


# ── Sample questions fixture ───────────────────────────────────

@pytest.fixture
def sample_questions() -> list[QuestionData]:
    return [
        QuestionData(
            question_text="What is REST?",
            category="backend",
            difficulty="junior",
            expected_keywords=["HTTP", "stateless", "CRUD"],
        ),
        QuestionData(
            question_text="Explain OOP principles.",
            category="backend",
            difficulty="mid",
            expected_keywords=["encapsulation", "inheritance", "polymorphism"],
        ),
        QuestionData(
            question_text="How would you design a rate limiter?",
            category="backend",
            difficulty="senior",
            expected_keywords=["token bucket", "distributed", "Redis"],
        ),
        QuestionData(
            question_text="What is React's virtual DOM?",
            category="frontend",
            difficulty="junior",
            expected_keywords=["reconciliation", "diffing", "performance"],
        ),
    ]


# ── Shared temp file fixture ─────────────────────────────────

@pytest.fixture
def temp_question_file() -> str:
    """Create a temporary JSON file with test questions. Returns the file path."""
    data = {
        "questions": [
            {
                "question_text": "What is REST?",
                "category": "backend",
                "difficulty": "junior",
                "expected_keywords": ["HTTP", "stateless"],
            },
            {
                "question_text": "Explain microservices.",
                "category": "backend",
                "difficulty": "mid",
                "expected_keywords": ["decoupling", "scalability"],
            },
            {
                "question_text": "Design a rate limiter.",
                "category": "backend",
                "difficulty": "senior",
                "expected_keywords": ["token bucket", "distributed"],
            },
            {
                "question_text": "What is React?",
                "category": "frontend",
                "difficulty": "junior",
                "expected_keywords": ["virtual DOM", "component"],
            },
        ]
    }
    with NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        return f.name
