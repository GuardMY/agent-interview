import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.db.database import async_session_factory
from app.llm.base import BaseLLMAdapter
from app.core.agent import InterviewAgent
from app.services.question_bank import QuestionBankService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["interview"])

# Shared question bank instance (loaded once, reused across sessions)
_question_bank: QuestionBankService | None = None


def _get_question_bank() -> QuestionBankService:
    global _question_bank
    if _question_bank is None:
        _question_bank = QuestionBankService()
    return _question_bank


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
    """WebSocket endpoint for conducting an interview."""
    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    llm = _create_llm_adapter()
    question_bank = _get_question_bank()

    async with async_session_factory() as db:
        agent = InterviewAgent(
            session_id=session_id,
            websocket=websocket,
            db=db,
            llm=llm,
            question_service=question_bank,
        )

        try:
            # Start interview (loads session, sends intro)
            await agent.start()

            # Main message loop
            while agent._fsm.is_active:
                try:
                    raw = await websocket.receive_text()
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
