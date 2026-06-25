import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agent import InterviewAgent
from app.core.fsm import InterviewEvent, InterviewFSM, InterviewState
from app.models.session import InterviewSession
from app.services.question_bank import QuestionBankService


class MockWebSocket:
    """Mock FastAPI WebSocket for testing."""

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self._receive_queue: asyncio.Queue = asyncio.Queue()

    async def send_text(self, data: str) -> None:
        import json
        self.sent_messages.append(json.loads(data))

    async def receive_text(self) -> str:
        return await self._receive_queue.get()

    def enqueue_message(self, msg: dict) -> None:
        import json
        self._receive_queue.put_nowait(json.dumps(msg))

    async def accept(self) -> None:
        pass


@pytest.fixture
def mock_ws() -> MockWebSocket:
    return MockWebSocket()


@pytest.fixture
def session_data() -> dict:
    return {
        "id": "test-session-123",
        "candidate_name": "Alice",
        "job_title": "Backend Engineer",
        "experience_level": "mid",
        "key_skills": ["Python", "FastAPI", "PostgreSQL"],
        "status": "idle",
        "current_question_index": 0,
        "total_questions": 3,
        "started_at": None,
        "completed_at": None,
    }


@pytest.mark.asyncio
async def test_agent_sends_start_message_on_start(
    mock_ws: MockWebSocket, mock_llm, test_db, temp_question_file: str
) -> None:
    """Agent.start() should send interview.start and interview.chat messages."""
    # Create session in DB
    session = InterviewSession(
        id="test-session-001",
        candidate_name="Alice",
        job_title="Backend Engineer",
        experience_level="mid",
        key_skills=["Python"],
    )
    test_db.add(session)
    await test_db.commit()

    qs = QuestionBankService(data_path=temp_question_file)
    agent = InterviewAgent(
        session_id="test-session-001",
        websocket=mock_ws,
        db=test_db,
        llm=mock_llm,
        question_service=qs,
    )

    await agent.start()

    assert len(mock_ws.sent_messages) >= 2
    types = [m["type"] for m in mock_ws.sent_messages]
    assert "interview.start" in types
    assert "interview.chat" in types


@pytest.mark.asyncio
async def test_agent_intro_to_qa_transition(
    mock_ws: MockWebSocket, mock_llm, test_db, temp_question_file: str
) -> None:
    """After candidate responds in INTRO, should ask a question."""
    session = InterviewSession(
        id="test-session-002",
        candidate_name="Bob",
        job_title="Frontend Engineer",
        experience_level="junior",
        key_skills=["React"],
        total_questions=2,
    )
    test_db.add(session)
    await test_db.commit()

    qs = QuestionBankService(data_path=temp_question_file)
    qs.set_initial_difficulty("junior")
    agent = InterviewAgent(
        session_id="test-session-002",
        websocket=mock_ws,
        db=test_db,
        llm=mock_llm,
        question_service=qs,
    )

    await agent.start()
    assert agent._fsm.state == InterviewState.INTRO

    # Simulate candidate's intro response
    await agent.handle_message({
        "type": "message.chat",
        "payload": {"content": "Hi, I'm Bob. I've been doing frontend for 3 years."},
    })

    # Should have transitioned and asked a question
    assert agent._fsm.state == InterviewState.QA_LOOP
    question_msgs = [m for m in mock_ws.sent_messages if m["type"] == "interview.question"]
    assert len(question_msgs) >= 1


@pytest.mark.asyncio
async def test_agent_skip_command(
    mock_ws: MockWebSocket, mock_llm, test_db, temp_question_file: str
) -> None:
    """Skip command should skip current question and move to next."""
    session = InterviewSession(
        id="test-session-003",
        candidate_name="Carol",
        job_title="Backend Engineer",
        experience_level="mid",
        key_skills=["SQL"],
        total_questions=3,
    )
    test_db.add(session)
    await test_db.commit()

    qs = QuestionBankService(data_path=temp_question_file)
    agent = InterviewAgent(
        session_id="test-session-003",
        websocket=mock_ws,
        db=test_db,
        llm=mock_llm,
        question_service=qs,
    )

    await agent.start()
    # Transition to QA loop
    await agent.handle_message({
        "type": "message.chat",
        "payload": {"content": "Hi there!"},
    })

    assert agent._fsm.state == InterviewState.QA_LOOP

    # Skip
    await agent.handle_message({
        "type": "command.skip",
        "payload": {},
    })

    # Agent should have handled skip (sent chat acknowledging it)
    chat_msgs = [m for m in mock_ws.sent_messages if m["type"] == "interview.chat"]
    assert any("No problem" in m["payload"].get("content", "") for m in chat_msgs) or \
           any("move on" in m["payload"].get("content", "") for m in chat_msgs)


@pytest.mark.asyncio
async def test_agent_full_qa_cycle(
    mock_ws: MockWebSocket, mock_llm, test_db, temp_question_file: str
) -> None:
    """Complete Q&A cycle: question -> answer -> evaluation."""
    session = InterviewSession(
        id="test-session-005",
        candidate_name="Eve",
        job_title="Backend Engineer",
        experience_level="junior",
        key_skills=["Python"],
        total_questions=1,
    )
    test_db.add(session)
    await test_db.commit()

    qs = QuestionBankService(data_path=temp_question_file)
    qs.set_initial_difficulty("junior")
    agent = InterviewAgent(
        session_id="test-session-005",
        websocket=mock_ws,
        db=test_db,
        llm=mock_llm,
        question_service=qs,
    )

    await agent.start()
    # Transition to QA
    await agent.handle_message({
        "type": "message.chat",
        "payload": {"content": "Hello, I'm Eve."},
    })

    # Find the question ID from the sent message
    question_msgs = [m for m in mock_ws.sent_messages if m["type"] == "interview.question"]
    assert len(question_msgs) >= 1

    # Answer the question
    await agent.handle_message({
        "type": "message.answer",
        "payload": {"content": "REST is an architectural style using HTTP, it is stateless."},
    })

    # Should have sent evaluation feedback
    eval_msgs = [m for m in mock_ws.sent_messages if m["type"] == "interview.evaluation"]
    # After total_questions=1 is exhausted, it goes straight to wrapup
    # So evaluation feedback should be sent after the answer
    assert len(eval_msgs) >= 1


@pytest.mark.asyncio
async def test_agent_max_skips_triggers_wrapup(
    mock_ws: MockWebSocket, mock_llm, test_db, temp_question_file: str
) -> None:
    """After max skip count, agent should go to wrapup."""
    session = InterviewSession(
        id="test-session-006",
        candidate_name="Frank",
        job_title="Backend Engineer",
        experience_level="mid",
        key_skills=["Python"],
        total_questions=10,
    )
    test_db.add(session)
    await test_db.commit()

    qs = QuestionBankService(data_path=temp_question_file)
    agent = InterviewAgent(
        session_id="test-session-006",
        websocket=mock_ws,
        db=test_db,
        llm=mock_llm,
        question_service=qs,
    )

    await agent.start()
    # Transition to QA
    await agent.handle_message({
        "type": "message.chat",
        "payload": {"content": "Hi!"},
    })

    # Skip 3 times (max_skip_count = 3 in config)
    for _ in range(3):
        await agent.handle_message({"type": "command.skip", "payload": {}})

    # After 3 skips, wrapup auto-finalizes to DONE
    assert agent._fsm.state == InterviewState.DONE
    chat_msgs = [m for m in mock_ws.sent_messages if m["type"] == "interview.chat"]
    assert any("maximum" in m["payload"].get("content", "").lower() for m in chat_msgs)
