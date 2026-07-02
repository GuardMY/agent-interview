import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.conversation import ConversationManager, IntentType
from app.core.evaluator import EvaluationEngine
from app.core.fsm import InterviewEvent, InterviewFSM, InterviewState
from app.llm.base import BaseLLMAdapter
from app.llm.prompts.system import SystemPromptBuilder
from app.llm.prompts.interviewer import get_prompt
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.message import WSMessage
from app.schemas.question import QuestionData
from app.services.question_bank import QuestionBankService

logger = logging.getLogger(__name__)


class InterviewAgent:
    """Orchestrates a complete interview session."""

    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        db: AsyncSession,
        llm: BaseLLMAdapter,
        question_service: QuestionBankService,
    ) -> None:
        self.session_id = session_id
        self._ws = websocket
        self._db = db
        self._llm = llm
        self._questions = question_service
        self._fsm = InterviewFSM()
        self._conversation = ConversationManager()
        self._evaluator = EvaluationEngine(llm)
        self._session: InterviewSession | None = None
        self._current_question_id: str | None = None
        self._skip_count: int = 0
        self._started_at: datetime | None = None
        # Timeout mechanism
        self._timeout_event = asyncio.Event()
        self._pending_timeout: str | None = None  # "skip" | "wrapup"
        self._per_question_task: asyncio.Task | None = None
        self._total_interview_task: asyncio.Task | None = None

    # ── Public API ──────────────────────────────────────────────

    async def start(self) -> None:
        """Begin the interview: load session, send intro, transition to INTRO."""
        self._session = await self._get_session()
        if self._session is None:
            await self._send_error("Session not found")
            return

        self._fsm.transition(InterviewEvent.START)
        self._session.status = InterviewState.INTRO.value
        self._started_at = datetime.now(timezone.utc)
        await self._db.commit()

        self._questions.set_seed(self._generate_seed())
        self._questions.set_initial_difficulty(self._session.experience_level)

        # Send interview.start
        await self._send_message("interview.start", {
            "session_id": self.session_id,
            "job_title": self._session.job_title,
            "total_questions": self._session.total_questions,
            "duration_minutes": settings.default_time_limit_minutes,
        })

        # Generate and send intro message
        intro_text = await self._generate_intro()
        self._conversation.add_message("interviewer", intro_text)
        await self._send_message("interview.chat", {"content": intro_text})

        # Start total interview timeout
        self._start_total_interview_timer()

    async def handle_message(self, raw: dict) -> None:
        """Dispatch an incoming WebSocket message based on current FSM state."""
        state = self._fsm.state

        if state == InterviewState.INTRO:
            await self._handle_intro(raw)
        elif state == InterviewState.QA_LOOP:
            await self._handle_qa(raw)
        elif state == InterviewState.WRAPUP:
            await self._handle_wrapup(raw)

    async def on_disconnect(self) -> None:
        """Handle client disconnect — persist state and mark PAUSED for later resume."""
        if not self._fsm.is_active:
            return
        if self._fsm.state == InterviewState.PAUSED:
            return  # Already paused

        self._cancel_per_question_timer()

        # Persist recoverable state to DB
        self._persist_state()

        # Transition to PAUSED (not DONE — allow reconnect)
        self._fsm.transition(InterviewEvent.CONNECTION_LOST)
        if self._session:
            self._session.status = InterviewState.PAUSED.value
            await self._db.commit()
            logger.info(f"Session {self.session_id} paused, state preserved for reconnect")

    # ── Phase Handlers ──────────────────────────────────────────

    async def _handle_intro(self, raw: dict) -> None:
        """After candidate responds to intro, transition to QA_LOOP."""
        content = raw.get("payload", {}).get("content", "")
        self._conversation.add_message("candidate", content)

        self._fsm.transition(InterviewEvent.INTRO_COMPLETE)
        if self._session:
            self._session.status = InterviewState.QA_LOOP.value
            await self._db.commit()

        # Transition acknowledgment + first question
        await self._send_message("interview.chat", {
            "content": get_prompt("intro_transition", self._lang)
        })
        await self._ask_next_question()

    async def _handle_qa(self, raw: dict) -> None:
        """Handle a message in the Q&A loop phase."""
        msg_type = raw.get("type", "")

        # Command: skip
        if msg_type == "command.skip":
            await self._handle_skip()
            return

        # Command: repeat
        if msg_type == "command.repeat":
            await self._handle_repeat()
            return

        # Default: treat as answer
        content = raw.get("payload", {}).get("content", "")
        if not content:
            return

        self._conversation.add_message("candidate", content)

        # Detect intent
        intent = self._conversation.detect_intent(content)

        if intent == IntentType.SKIP:
            await self._handle_skip()
            return

        if intent == IntentType.DISENGAGE:
            await self._end_interview_early()
            return

        if intent == IntentType.CLARIFY:
            clarification = await self._llm.generate(
                prompt=get_prompt("clarify", self._lang),
                system_prompt=self._build_system_prompt(),
                max_tokens=200,
                temperature=0.8,
            )
            await self._send_message("interview.chat", {"content": clarification})
            return

        if intent == IntentType.CHAT:
            # Brief acknowledgment, then continue
            if not self._current_question_id:
                await self._ask_next_question()
            return

        # Evaluate the answer
        await self._evaluate_and_continue(content)

    async def _handle_wrapup(self, raw: dict) -> None:
        """Handle messages during wrapup phase."""
        content = raw.get("payload", {}).get("content", "")
        self._conversation.add_message("candidate", content)

        closing = await self._llm.generate(
            prompt=f"The candidate said: '{content}'. This is the wrapup phase. "
                   "Respond warmly and conclude the interview.",
            system_prompt=self._build_system_prompt(),
            max_tokens=300,
            temperature=0.7,
        )
        await self._send_message("interview.chat", {"content": closing})

        self._fsm.transition(InterviewEvent.WRAPUP_COMPLETE)
        await self._finalize_session()

    # ── Question Flow ───────────────────────────────────────────

    async def _ask_next_question(self) -> None:
        """Select and ask the next question, or transition to wrapup."""
        if not self._session:
            return

        idx = self._session.current_question_index
        if idx >= self._session.total_questions:
            await self._start_wrapup()
            return

        if not self._questions.has_more_questions():
            await self._start_wrapup()
            return

        q_data = self._questions.select_question()
        if q_data is None:
            await self._start_wrapup()
            return

        # Create DB record
        question = Question(
            session_id=self.session_id,
            question_text=q_data.question_text,
            category=q_data.category,
            difficulty=q_data.difficulty,
            expected_keywords=q_data.expected_keywords,
            order_index=idx,
            status="asked",
            asked_at=datetime.now(timezone.utc),
        )
        self._db.add(question)
        await self._db.flush()
        self._current_question_id = question.id
        self._session.current_question_index = idx + 1
        await self._db.commit()

        # Wrap question in natural language (text is already in the target language)
        try:
            wrapped = await self._llm.generate(
                prompt=get_prompt("question_wrap", self._lang,
                                  question=q_data.question_text,
                                  category=q_data.category,
                                  difficulty=q_data.difficulty),
                system_prompt=self._build_system_prompt(),
                max_tokens=200,
                temperature=0.8,
            )
            if not wrapped or not wrapped.strip():
                wrapped = q_data.question_text
        except Exception:
            wrapped = q_data.question_text

        self._conversation.add_message("interviewer", wrapped)
        await self._send_message("interview.question", {
            "question_id": question.id,
            "content": wrapped,
            "category": q_data.category,
            "difficulty": q_data.difficulty,
            "question_number": idx + 1,
            "total_questions": self._session.total_questions,
        })

        # Start per-question answer timeout
        self._start_per_question_timer()

    async def _evaluate_and_continue(self, answer_text: str) -> None:
        """Evaluate the answer, send results, and move to next question."""
        if not self._current_question_id or not self._session:
            return

        self._cancel_per_question_timer()

        stmt = select(Question).where(Question.id == self._current_question_id)
        result = await self._db.execute(stmt)
        question = result.scalar_one_or_none()
        if question is None:
            return

        q_data = QuestionData(
            question_text=question.question_text,
            category=question.category,
            difficulty=question.difficulty,
            expected_keywords=question.expected_keywords or [],
        )

        evaluation = await self._evaluator.evaluate(q_data, answer_text, language=self._lang)

        answer = Answer(
            question_id=question.id,
            session_id=self.session_id,
            content=answer_text,
            score=evaluation.score,
            score_comment=evaluation.comment,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            matched_keywords=evaluation.matched_keywords,
            missing_points=evaluation.missing_points,
            dimension_technical_accuracy=(
                evaluation.dimensions.technical_accuracy if evaluation.dimensions else None
            ),
            dimension_depth_of_knowledge=(
                evaluation.dimensions.depth_of_knowledge if evaluation.dimensions else None
            ),
            dimension_communication=(
                evaluation.dimensions.communication if evaluation.dimensions else None
            ),
            dimension_problem_solving=(
                evaluation.dimensions.problem_solving if evaluation.dimensions else None
            ),
            llm_evaluation_raw={
                "score": evaluation.score,
                "comment": evaluation.comment,
                "strengths": evaluation.strengths,
                "weaknesses": evaluation.weaknesses,
                "matched_keywords": evaluation.matched_keywords,
                "missing_points": evaluation.missing_points,
                "dimensions": (
                    evaluation.dimensions.model_dump()
                    if evaluation.dimensions else None
                ),
            },
        )
        self._db.add(answer)
        question.status = "answered"
        await self._db.commit()

        self._questions.update_difficulty(evaluation.score)

        strength_str = "; ".join(evaluation.strengths[:2]) if evaluation.strengths else "Good effort."
        await self._send_message("interview.evaluation", {
            "feedback": strength_str,
        })

        await self._ask_next_question()

    # ── Commands ────────────────────────────────────────────────

    async def _handle_skip(self) -> None:
        """Skip current question and move to next."""
        self._skip_count += 1

        if self._current_question_id:
            stmt = select(Question).where(Question.id == self._current_question_id)
            result = await self._db.execute(stmt)
            question = result.scalar_one_or_none()
            if question:
                question.status = "skipped"
                await self._db.commit()

        if self._skip_count >= settings.max_skip_count:
            await self._send_message("interview.chat", {
                "content": get_prompt("skip_limit", self._lang)
            })
            await self._start_wrapup()
            return

        await self._send_message("interview.chat", {
            "content": get_prompt("skip_ack", self._lang)
        })
        await self._ask_next_question()

    async def _handle_repeat(self) -> None:
        """Repeat / rephrase the last question."""
        if not self._current_question_id:
            return

        stmt = select(Question).where(Question.id == self._current_question_id)
        result = await self._db.execute(stmt)
        question = result.scalar_one_or_none()
        if question is None:
            return

        rephrased = await self._llm.generate(
            prompt=get_prompt("repeat", self._lang, question=question.question_text),
            system_prompt=self._build_system_prompt(),
            max_tokens=200,
            temperature=0.8,
        )
        await self._send_message("interview.chat", {"content": rephrased})

    # ── Phase Transitions ───────────────────────────────────────

    async def _start_wrapup(self) -> None:
        """Transition from QA_LOOP to WRAPUP, then finalize immediately."""
        self._fsm.transition(InterviewEvent.QUESTION_EXHAUSTED)
        if self._session:
            self._session.status = InterviewState.WRAPUP.value
            await self._db.commit()

        try:
            wrapup_msg = await self._llm.generate(
                prompt=get_prompt("wrapup", self._lang),
                system_prompt=self._build_system_prompt(),
                max_tokens=300,
                temperature=0.7,
            )
        except Exception:
            wrapup_msg = get_prompt("wrapup_fallback", self._lang)

        self._conversation.add_message("interviewer", wrapup_msg)
        await self._send_message("interview.chat", {"content": wrapup_msg})

        self._fsm.transition(InterviewEvent.WRAPUP_COMPLETE)
        await self._finalize_session()

    async def _end_interview_early(self) -> None:
        """Handle candidate disengagement."""
        await self._send_message("interview.chat", {
            "content": get_prompt("early_end", self._lang)
        })
        self._fsm.transition(InterviewEvent.CANDIDATE_DISCONNECT)
        await self._finalize_session()

    async def _finalize_session(self) -> None:
        """Complete the session and send the final report."""
        self._cancel_per_question_timer()
        if self._total_interview_task and not self._total_interview_task.done():
            self._total_interview_task.cancel()
            self._total_interview_task = None

        if self._session:
            self._session.status = InterviewState.DONE.value
            self._session.completed_at = datetime.now(timezone.utc)
            # Persist conversation transcript
            transcript = [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in self._conversation.get_full_history()
            ]
            self._session.metadata_json["transcript"] = transcript
            flag_modified(self._session, "metadata_json")
            await self._db.commit()

        await self._send_message("interview.end", {
            "session_id": self.session_id,
            "message": get_prompt("end_message", self._lang),
        })

    # ── Helpers ─────────────────────────────────────────────────

    async def _get_session(self) -> InterviewSession | None:
        stmt = select(InterviewSession).where(
            InterviewSession.id == self.session_id
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    @property
    def _lang(self) -> str:
        return self._session.interview_language if self._session else "en"

    def _generate_seed(self) -> str:
        """Generate a deterministic random seed from the session ID."""
        return hashlib.sha256(self.session_id.encode()).hexdigest()

    # ── Timeout Management ─────────────────────────────────────

    def _start_per_question_timer(self) -> None:
        """Start the per-question answer timeout. Fires warning, then force-skip."""
        self._cancel_per_question_timer()

        async def _timer() -> None:
            try:
                await asyncio.sleep(settings.answer_timeout_seconds)
                # Phase 1: send warning
                await self._send_message("interview.chat", {
                    "content": get_prompt("timeout_warning", self._lang),
                })
                await asyncio.sleep(settings.timeout_grace_period_seconds)
                # Phase 2: force skip
                self._pending_timeout = "skip"
                self._timeout_event.set()
            except asyncio.CancelledError:
                pass

        self._per_question_task = asyncio.create_task(_timer())

    def _cancel_per_question_timer(self) -> None:
        """Cancel the per-question timeout (called when answer received)."""
        if self._per_question_task and not self._per_question_task.done():
            self._per_question_task.cancel()
            self._per_question_task = None
        self._pending_timeout = None
        self._timeout_event.clear()

    def _start_total_interview_timer(self) -> None:
        """Start the total interview timeout. Forces wrapup when exceeded."""
        if not self._session:
            return
        total_seconds = self._session.total_questions * 180  # 3 min per question

        async def _timer() -> None:
            try:
                await asyncio.sleep(total_seconds)
                self._pending_timeout = "wrapup"
                self._timeout_event.set()
            except asyncio.CancelledError:
                pass

        self._total_interview_task = asyncio.create_task(_timer())

    async def _handle_timeout_skip(self) -> None:
        """Handle per-question timeout: mark skipped, move to next question."""
        await self._send_message("interview.chat", {
            "content": get_prompt("timeout_skip", self._lang),
        })

        if self._current_question_id:
            stmt = select(Question).where(Question.id == self._current_question_id)
            result = await self._db.execute(stmt)
            question = result.scalar_one_or_none()
            if question:
                question.status = "timeout"
                await self._db.commit()

        self._timeout_event.clear()
        await self._ask_next_question()

    async def resolve_timeout(self) -> None:
        """Called from main loop when a timeout event fires."""
        pending = self._pending_timeout
        self._pending_timeout = None
        self._timeout_event.clear()

        if pending == "skip":
            await self._handle_timeout_skip()
        elif pending == "wrapup":
            self._cancel_per_question_timer()
            await self._start_wrapup()

    # ── Resume / Persistence ────────────────────────────────────

    def _persist_state(self) -> None:
        """Serialize recoverable interview state to session metadata_json."""
        if not self._session:
            return

        conv_data = [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in self._conversation.get_full_history()
        ]

        self._session.metadata_json["paused_state"] = {
            "previous_state": self._fsm.state.value,
            "current_question_id": self._current_question_id,
            "current_question_index": self._session.current_question_index,
            "skip_count": self._skip_count,
            "conversation_history": conv_data,
        }
        flag_modified(self._session, "metadata_json")

    async def resume(self) -> None:
        """Restore a paused interview from persisted state."""
        self._session = await self._get_session()
        if not self._session:
            await self._send_error("Session not found")
            return

        paused = self._session.metadata_json.get("paused_state", {})
        if not paused:
            await self._send_error("No saved state to resume from")
            return

        # Restore conversation history
        self._conversation = ConversationManager()
        for msg_data in paused.get("conversation_history", []):
            self._conversation.add_message(msg_data["role"], msg_data["content"])

        # Restore tracking state
        self._current_question_id = paused.get("current_question_id")
        self._skip_count = paused.get("skip_count", 0)
        self._started_at = datetime.now(timezone.utc)

        # Restore question index
        restored_idx = paused.get("current_question_index", 0)
        if self._session:
            self._session.current_question_index = restored_idx

        # Restore FSM state via direct assignment
        prev_state_str = paused.get("previous_state", InterviewState.QA_LOOP.value)
        prev_state = InterviewState(prev_state_str)
        self._fsm.force_state(prev_state)

        # Update session
        if self._session:
            self._session.status = prev_state.value
            await self._db.commit()

        # Restore question bank seed
        self._questions.set_seed(self._generate_seed())
        self._questions.set_initial_difficulty(
            self._session.experience_level if self._session else "mid"
        )

        # Send resume notification with full context for frontend restoration
        conv_history = [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in self._conversation.get_full_history()
        ]
        await self._send_message("interview.resume", {
            "session_id": self.session_id,
            "job_title": self._session.job_title if self._session else "",
            "previous_state": prev_state_str,
            "question_index": restored_idx,
            "total_questions": self._session.total_questions if self._session else 0,
            "conversation_history": conv_history,
        })

        # Restart timers if in QA_LOOP
        if prev_state_str == InterviewState.QA_LOOP.value and self._current_question_id:
            self._start_per_question_timer()

        self._start_total_interview_timer()
        logger.info(f"Session {self.session_id} resumed from {prev_state_str}")

    def _build_system_prompt(self) -> str:
        if self._session is None:
            return SystemPromptBuilder.build(
                job_title="Software Engineer",
                experience_level="mid",
                current_phase=self._fsm.state.value,
                language="en",
            )
        elapsed = 0
        if self._started_at:
            elapsed = int((datetime.now(timezone.utc) - self._started_at).total_seconds() / 60)
        return SystemPromptBuilder.build(
            job_title=self._session.job_title,
            experience_level=self._session.experience_level,
            current_phase=self._fsm.state.value,
            key_skills=self._session.key_skills or [],
            questions_asked=self._session.current_question_index,
            total_questions=self._session.total_questions,
            elapsed_minutes=elapsed,
            recent_history=self._conversation.format_window_for_llm(),
            language=self._lang,
        )

    async def _generate_intro(self) -> str:
        return await self._llm.generate(
            prompt=get_prompt("intro_en", self._lang),
            system_prompt=self._build_system_prompt(),
            max_tokens=300,
            temperature=0.8,
        )

    async def _send_message(self, msg_type: str, payload: dict) -> None:
        """Send a structured WebSocket message to the client."""
        try:
            msg = WSMessage(type=msg_type, payload=payload)
            await self._ws.send_text(msg.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send WS message '{msg_type}': {e}")

    async def _send_error(self, message: str, code: str = "ERROR") -> None:
        try:
            msg = WSMessage(
                type="error", payload={"code": code, "message": message}
            )
            await self._ws.send_text(msg.model_dump_json())
        except Exception:
            pass
