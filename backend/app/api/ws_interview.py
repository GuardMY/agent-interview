import asyncio
import json
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.db.database import async_session_factory
from app.core.fsm import InterviewState
from app.llm.base import BaseLLMAdapter
from app.core.agent import InterviewAgent
from app.services.question_bank import QuestionBankService
from app.models.session import InterviewSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["interview"])

# Per-language question bank cache (loaded once per language, reused across sessions)
_question_banks: dict[str, QuestionBankService] = {}


def _get_question_bank(language: str = "en") -> QuestionBankService:
    global _question_banks
    if language not in _question_banks:
        _question_banks[language] = QuestionBankService(language=language)
    return _question_banks[language]


def _create_llm_adapter() -> BaseLLMAdapter:
    """Create the LLM adapter based on configured provider."""
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        from app.llm.claude import ClaudeAdapter
        return ClaudeAdapter()

    if provider == "deepseek":
        from app.llm.deepseek import DeepSeekAdapter
        return DeepSeekAdapter()

    if provider == "openai":
        from app.llm.deepseek import DeepSeekAdapter
        return DeepSeekAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url="https://api.openai.com/v1",
        )

    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


@router.websocket("/ws/interview/{session_id}")
async def ws_interview(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for conducting an interview. Requires candidate token."""
    # Validate candidate token from query string
    qs = parse_qs(websocket.scope.get("query_string", b"").decode())
    token = qs.get("token", [None])[0]

    async with async_session_factory() as check_db:
        result = await check_db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session or token != session.candidate_token:
            await websocket.close(code=4003, reason="Forbidden")
            return

    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    llm = _create_llm_adapter()
    # Load question bank in the session's language (or default to "en")
    question_bank = _get_question_bank(session.interview_language if session else "en")

    # Create dynamic question generator for strategy mode
    from app.services.question_generator import DynamicQuestionGenerator
    question_generator = DynamicQuestionGenerator(
        llm=llm,
        question_bank=question_bank,
    )

    async with async_session_factory() as db:
        agent = InterviewAgent(
            session_id=session_id,
            websocket=websocket,
            db=db,
            llm=llm,
            question_service=question_bank,
            question_generator=question_generator,
        )

        try:
            # Detect if this is a reconnection to a paused session
            if session and session.status == InterviewState.PAUSED.value:
                await agent.resume()
            else:
                await agent.start()

            # Main message loop — race between receive and timeout
            while agent._fsm.is_active:
                try:
                    # Race: WebSocket receive vs timeout event
                    receive_task = asyncio.create_task(websocket.receive_text())
                    timeout_task = asyncio.create_task(agent._timeout_event.wait())

                    done, pending = await asyncio.wait(
                        [receive_task, timeout_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Cancel the unfinished task
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass

                    # If timeout fired first, handle it
                    if timeout_task in done:
                        await agent.resolve_timeout()
                        continue

                    # Otherwise, process the received message
                    raw = receive_task.result()
                    message = json.loads(raw)
                    await agent.handle_message(message)

                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "payload": {"code": "INVALID_JSON", "message": "Invalid JSON format"},
                        "timestamp": "",
                    }))
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for session {session_id}")
                    await agent.on_disconnect()
                    return

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected during start for session {session_id}")
            await agent.on_disconnect()
        except Exception as e:
            logger.exception(f"Unexpected error in interview session {session_id}: {e}")
            try:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "payload": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
                    "timestamp": "",
                }))
            except Exception:
                pass
