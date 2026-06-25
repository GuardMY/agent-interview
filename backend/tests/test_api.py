import pytest
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db.database import async_session_factory, engine, Base
from app.main import app


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Override DB to in-memory SQLite and create tables before each test."""
    # Override config for testing
    original_url = settings.database_url
    settings.database_url = "sqlite+aiosqlite://"

    # Create a fresh engine and session factory for tests
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    test_engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override the get_db dependency
    app.dependency_overrides = {}

    async def override_get_db():
        async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    from app.db.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    yield

    # Cleanup
    app.dependency_overrides.clear()
    settings.database_url = original_url
    await test_engine.dispose()


# ── TestClient fixtures ────────────────────────────────────────

@pytest.fixture
def client():
    """Synchronous FastAPI test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestRESTEndpoints:
    def test_create_session(self, client) -> None:
        payload = {
            "candidate_name": "Alice",
            "job_title": "Backend Engineer",
            "experience_level": "mid",
            "key_skills": ["Python", "FastAPI"],
        }
        response = client.post("/api/sessions", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["candidate_name"] == "Alice"
        assert data["job_title"] == "Backend Engineer"
        assert data["status"] == "idle"
        assert "id" in data

    def test_get_session(self, client) -> None:
        create_resp = client.post("/api/sessions", json={
            "candidate_name": "Bob",
            "job_title": "Frontend Engineer",
            "experience_level": "senior",
        })
        session_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/sessions/{session_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["candidate_name"] == "Bob"

    def test_get_session_not_found(self, client) -> None:
        response = client.get("/api/sessions/nonexistent-id")
        assert response.status_code == 404

    def test_get_session_report(self, client) -> None:
        create_resp = client.post("/api/sessions", json={
            "candidate_name": "Carol",
            "job_title": "Backend Engineer",
            "experience_level": "mid",
        })
        session_id = create_resp.json()["id"]

        report_resp = client.get(f"/api/sessions/{session_id}/report")
        assert report_resp.status_code == 200
        data = report_resp.json()
        assert data["session_id"] == session_id
        assert data["candidate_name"] == "Carol"
        assert "answers" in data

    def test_delete_session(self, client) -> None:
        create_resp = client.post("/api/sessions", json={
            "candidate_name": "Dave",
            "job_title": "DevOps Engineer",
            "experience_level": "senior",
        })
        session_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/sessions/{session_id}")
        assert delete_resp.status_code == 204

        get_resp = client.get(f"/api/sessions/{session_id}")
        assert get_resp.status_code == 404

    def test_health_check(self, client) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_ws_invalid_session(self, client, mock_llm) -> None:
        """WebSocket with invalid session ID should receive an error."""
        # Ensure a session exists so DB is initialized
        client.post("/api/sessions", json={
            "candidate_name": "Temp",
            "job_title": "Test",
            "experience_level": "junior",
        })

        with patch("app.api.ws_interview._create_llm_adapter", return_value=mock_llm):
            with client.websocket_connect("/ws/interview/nonexistent-id") as ws:
                data = ws.receive_json()
                assert data["type"] == "error"
