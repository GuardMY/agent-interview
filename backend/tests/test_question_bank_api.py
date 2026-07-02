"""Integration tests for question bank CRUD REST API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.database import Base, get_db
from app.main import app

ADMIN_HEADERS = {"X-Admin-Token": "test-master-token"}


@pytest.fixture(autouse=True)
async def _setup_question_bank_api(monkeypatch):
    """Set up test DB + master admin token. Runs before each test."""
    monkeypatch.setattr(settings, "master_admin_token", "test-master-token")

    # Create in-memory SQLite for this test module
    original_url = settings.database_url
    settings.database_url = "sqlite+aiosqlite://"

    test_engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override get_db dependency
    async def override_get_db():
        async_session = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()
    settings.database_url = original_url
    await test_engine.dispose()


@pytest.fixture
def api_client():
    """Create a test client."""
    return TestClient(app)


class TestQuestionBankAPI:
    """Tests for GET/POST/PUT/DELETE /api/questions endpoints."""

    def test_list_questions_empty_db(self, api_client):
        """Listing questions on a fresh DB should return empty list (before seed)."""
        resp = api_client.get("/api/questions", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1

    def test_list_questions_forbidden_without_token(self, api_client):
        """Missing master admin token should return 403."""
        resp = api_client.get("/api/questions")
        assert resp.status_code == 403

    def test_create_and_get_question(self, api_client):
        """Create a question, then verify it appears in the list."""
        payload = {
            "question_text": "What is dependency injection?",
            "category": "backend",
            "difficulty": "mid",
            "expected_keywords": ["DI", "IoC", "inversion of control"],
        }
        resp = api_client.post("/api/questions", json=payload, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        created = resp.json()
        assert created["question_text"] == payload["question_text"]
        assert created["category"] == "backend"
        assert created["difficulty"] == "mid"
        assert created["is_active"] is True
        assert "id" in created
        assert "created_at" in created

        # Verify in list
        resp2 = api_client.get("/api/questions", headers=ADMIN_HEADERS)
        assert resp2.status_code == 200
        items = resp2.json()["items"]
        assert any(q["id"] == created["id"] for q in items)

    def test_create_question_invalid_difficulty(self, api_client):
        """Creating with invalid difficulty should return 422."""
        payload = {
            "question_text": "Test",
            "category": "backend",
            "difficulty": "expert",  # Not in junior|mid|senior
        }
        resp = api_client.post("/api/questions", json=payload, headers=ADMIN_HEADERS)
        assert resp.status_code == 422

    def test_update_question(self, api_client):
        """Update a question's text."""
        # Create first
        create_resp = api_client.post(
            "/api/questions",
            json={
                "question_text": "Original text",
                "category": "general",
                "difficulty": "junior",
            },
            headers=ADMIN_HEADERS,
        )
        q_id = create_resp.json()["id"]

        # Update
        update_resp = api_client.put(
            f"/api/questions/{q_id}",
            json={"question_text": "Updated text", "difficulty": "mid"},
            headers=ADMIN_HEADERS,
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["question_text"] == "Updated text"
        assert updated["difficulty"] == "mid"
        assert updated["category"] == "general"  # Unchanged

    def test_update_question_not_found(self, api_client):
        """Updating a non-existent question returns 404."""
        resp = api_client.put(
            "/api/questions/nonexistent-id",
            json={"question_text": "x"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 404

    def test_delete_question_soft(self, api_client):
        """Delete should soft-delete (is_active=False)."""
        create_resp = api_client.post(
            "/api/questions",
            json={
                "question_text": "To be deleted",
                "category": "general",
                "difficulty": "junior",
            },
            headers=ADMIN_HEADERS,
        )
        q_id = create_resp.json()["id"]

        # Delete
        del_resp = api_client.delete(
            f"/api/questions/{q_id}", headers=ADMIN_HEADERS
        )
        assert del_resp.status_code == 204

        # Should not appear in list
        list_resp = api_client.get("/api/questions", headers=ADMIN_HEADERS)
        items = list_resp.json()["items"]
        assert not any(q["id"] == q_id for q in items)

    def test_list_categories(self, api_client):
        """Categories endpoint returns distinct values."""
        # Create questions in different categories
        for cat in ["backend", "frontend", "backend"]:
            api_client.post(
                "/api/questions",
                json={
                    "question_text": f"Q in {cat}",
                    "category": cat,
                    "difficulty": "junior",
                },
                headers=ADMIN_HEADERS,
            )

        resp = api_client.get("/api/questions/categories", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "backend" in data["categories"]
        assert "frontend" in data["categories"]
        # Should be distinct
        assert data["categories"].count("backend") == 1

    def test_pagination(self, api_client):
        """Test pagination parameters work."""
        # Create 5 questions
        for i in range(5):
            api_client.post(
                "/api/questions",
                json={
                    "question_text": f"Question {i}",
                    "category": "general",
                    "difficulty": "junior",
                },
                headers=ADMIN_HEADERS,
            )

        resp = api_client.get(
            "/api/questions?page=1&size=2", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 5
        assert data["pages"] >= 3

    def test_search(self, api_client):
        """Text search should filter questions."""
        api_client.post(
            "/api/questions",
            json={
                "question_text": "Explain Kubernetes pods",
                "category": "devops",
                "difficulty": "senior",
            },
            headers=ADMIN_HEADERS,
        )
        api_client.post(
            "/api/questions",
            json={
                "question_text": "What is React?",
                "category": "frontend",
                "difficulty": "junior",
            },
            headers=ADMIN_HEADERS,
        )

        resp = api_client.get(
            "/api/questions?search=Kubernetes", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert "Kubernetes" in items[0]["question_text"]

    def test_filter_by_category(self, api_client):
        """Filter questions by category."""
        api_client.post(
            "/api/questions",
            json={
                "question_text": "Backend Q",
                "category": "backend",
                "difficulty": "mid",
            },
            headers=ADMIN_HEADERS,
        )
        api_client.post(
            "/api/questions",
            json={
                "question_text": "Frontend Q",
                "category": "frontend",
                "difficulty": "junior",
            },
            headers=ADMIN_HEADERS,
        )

        resp = api_client.get(
            "/api/questions?category=frontend", headers=ADMIN_HEADERS
        )
        items = resp.json()["items"]
        assert all(q["category"] == "frontend" for q in items)
