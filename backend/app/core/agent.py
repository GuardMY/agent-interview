import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.conversation import ConversationManager, IntentType
from app.core.evaluator import EvaluationEngine
from app.core.fsm import InterviewEvent, InterviewFSM, InterviewState
from app.llm.base import BaseLLMAdapter
from app.llm.prompts.system import SystemPromptBuilder
from app.llm.prompts.interviewer import get_prompt
from app.models.answer import Answer
from app.models.question import Question
from app.models.resume import Resume
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
        self._resume: Resume | None = None
        self._resume_deep_dive_count: int = 0
        self._max_resume_deep_dive: int = settings.max_resume_deep_dive_questions

    # ── Public API ──────────────────────────────────────────────

    async def start(self) -> None:
        """Begin the interview: load session, send intro, transition to INTRO."""
        self._session = await self._get_session()
        if self._session is None:
            await self._send_error("Session not found")
            return

        # Load associated resume if any
        self._resume = await self._get_resume()

        self._fsm.transition(InterviewEvent.START)
        self._session.status = InterviewState.INTRO.value
        self._started_at = datetime.now(timezone.utc)
        await self._db.commit()

        self._questions.set_initial_difficulty(self._session.experience_level)

        # Send interview.start
        await self._send_message("interview.start", {
            "session_id": self.session_id,
            "job_title": self._session.job_title,
            "total_questions": self._session.total_questions,
            "duration_minutes": settings.default_time_limit_minutes,
            "has_resume": self._resume is not None and self._resume.parse_status == "done",
        })

        # Generate and send intro message
        intro_text = await self._generate_intro()
        self._conversation.add_message("interviewer", intro_text)
        await self._send_message("interview.chat", {"content": intro_text})

    async def handle_message(self, raw: dict) -> None:
        """Dispatch an incoming WebSocket message based on current FSM state."""
        state = self._fsm.state

        if state == InterviewState.INTRO:
            await self._handle_intro(raw)
        elif state == InterviewState.RESUME_DEEP_DIVE:
            await self._handle_resume_deep_dive(raw)
        elif state == InterviewState.QA_LOOP:
            await self._handle_qa(raw)
        elif state == InterviewState.WRAPUP:
            await self._handle_wrapup(raw)

    async def on_disconnect(self) -> None:
        """Handle client disconnect."""
        if self._fsm.is_active:
            self._fsm.transition(InterviewEvent.CANDIDATE_DISCONNECT)
            if self._session:
                self._session.status = InterviewState.DONE.value
                await self._db.commit()

    # ── Phase Handlers ──────────────────────────────────────────

    async def _handle_intro(self, raw: dict) -> None:
        """After candidate responds to intro, branch to resume deep-dive or QA_LOOP."""
        content = raw.get("payload", {}).get("content", "")
        self._conversation.add_message("candidate", content)

        # Check if we have a parsed resume for deep-dive
        if self._resume and self._resume.parse_status == "done":
            await self._start_resume_deep_dive()
        else:
            # No resume: keep existing behavior, go straight to QA_LOOP
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

    # ── Resume Deep-Dive ────────────────────────────────────────

    async def _start_resume_deep_dive(self) -> None:
        """Enter the resume deep-dive phase."""
        self._fsm.transition(InterviewEvent.RESUME_DIVE)
        if self._session:
            self._session.status = InterviewState.RESUME_DEEP_DIVE.value
            await self._db.commit()

        self._resume_deep_dive_count = 0

        # Phase announcement
        await self._send_message("interview.chat", {
            "content": get_prompt("resume_deep_dive_intro", self._lang)
        })

        # Ask first resume question
        await self._ask_resume_question()

    async def _handle_resume_deep_dive(self, raw: dict) -> None:
        """Handle a message during the resume deep-dive phase."""
        content = raw.get("payload", {}).get("content", "")
        if not content:
            return

        self._conversation.add_message("candidate", content)
        self._resume_deep_dive_count += 1

        if self._resume_deep_dive_count >= self._max_resume_deep_dive:
            # Done — move to QA_LOOP
            self._fsm.transition(InterviewEvent.DEEP_DIVE_COMPLETE)
            if self._session:
                self._session.status = InterviewState.QA_LOOP.value
                await self._db.commit()

            await self._send_message("interview.chat", {
                "content": get_prompt("resume_deep_dive_done", self._lang)
            })
            await self._ask_next_question()
        else:
            # Ask another resume question
            await self._ask_resume_question()

    async def _ask_resume_question(self) -> None:
        """Generate and send a question based on resume content."""
        if not self._resume:
            return

        # Build a concise resume summary for the LLM
        resume_parts = []
        if self._resume.parsed_name:
            resume_parts.append(f"Name: {self._resume.parsed_name}")
        if self._resume.suggested_job_title:
            resume_parts.append(f"Current/Most Recent Role: {self._resume.suggested_job_title}")
        if self._resume.parsed_skills:
            resume_parts.append(f"Skills: {', '.join(self._resume.parsed_skills[:10])}")
        if self._resume.parsed_summary:
            resume_parts.append(f"Summary: {self._resume.parsed_summary}")
        if self._resume.parsed_experience:
            exp_lines = []
            for exp in self._resume.parsed_experience[:3]:
                company = exp.get("company", "")
                title = exp.get("title", "")
                duration = exp.get("duration", "")
                exp_lines.append(f"  - {title} at {company} ({duration})")
            if exp_lines:
                resume_parts.append(f"Experience:\n" + "\n".join(exp_lines))
        if self._resume.parsed_projects:
            proj_lines = []
            for proj in self._resume.parsed_projects[:2]:
                name = proj.get("name", "")
                desc = proj.get("description", "")
                proj_lines.append(f"  - {name}: {desc}")
            if proj_lines:
                resume_parts.append(f"Projects:\n" + "\n".join(proj_lines))

        resume_summary = "\n".join(resume_parts)

        question = await self._llm.generate(
            prompt=get_prompt("resume_deep_dive_question", self._lang,
                              resume_summary=resume_summary),
            system_prompt=self._build_system_prompt(),
            max_tokens=300,
            temperature=0.8,
        )
        self._conversation.add_message("interviewer", question)
        await self._send_message("interview.chat", {"content": question})

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

        # Wrap question in natural language (fallback to raw text on failure)
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

    async def _evaluate_and_continue(self, answer_text: str) -> None:
        """Evaluate the answer, send results, and move to next question."""
        if not self._current_question_id or not self._session:
            return

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
            llm_evaluation_raw={
                "score": evaluation.score,
                "comment": evaluation.comment,
                "strengths": evaluation.strengths,
                "weaknesses": evaluation.weaknesses,
                "matched_keywords": evaluation.matched_keywords,
                "missing_points": evaluation.missing_points,
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
        if self._session:
            self._session.status = InterviewState.DONE.value
            self._session.completed_at = datetime.now(timezone.utc)
            await self._db.commit()

        await self._send_message("interview.end", {
            "session_id": self.session_id,
            "message": get_prompt("end_message", self._lang),
        })

    # ── Helpers ─────────────────────────────────────────────────

    async def _get_session(self) -> InterviewSession | None:
        stmt = (
            select(InterviewSession)
            .where(InterviewSession.id == self.session_id)
            .options(selectinload(InterviewSession.resume))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_resume(self) -> Resume | None:
        """Load the resume associated with this session, if any."""
        stmt = select(Resume).where(Resume.session_id == self.session_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    @property
    def _lang(self) -> str:
        return self._session.interview_language if self._session else "en"

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

        # Build resume context string for system prompt
        resume_context = ""
        if self._resume and self._resume.parse_status == "done":
            parts = []
            if self._resume.parsed_name:
                parts.append(f"Name: {self._resume.parsed_name}")
            if self._resume.suggested_job_title:
                parts.append(f"Current Role: {self._resume.suggested_job_title}")
            if self._resume.parsed_skills:
                parts.append(f"Skills: {', '.join(self._resume.parsed_skills[:10])}")
            if self._resume.parsed_experience:
                for exp in self._resume.parsed_experience[:3]:
                    company = exp.get("company", "")
                    title = exp.get("title", "")
                    duration = exp.get("duration", "")
                    parts.append(f"Experience: {title} at {company} ({duration})")
            if self._resume.parsed_summary:
                parts.append(f"Summary: {self._resume.parsed_summary}")
            resume_context = "\n".join(parts)

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
            resume_context=resume_context,
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
