import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.conversation import ConversationManager, IntentType
from app.core.evaluator import EvaluationEngine
from app.core.fsm import InterviewEvent, InterviewFSM, InterviewState
from app.core.phase_router import PhaseRouter
from app.llm.base import BaseLLMAdapter
from app.llm.prompts.system import SystemPromptBuilder
from app.llm.prompts.interviewer import get_prompt
from app.llm.prompts.phases import get_phase_prompt, get_follow_up_prompt
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.message import WSMessage
from app.schemas.question import QuestionData
from app.schemas.session import (
    GapAnalysis,
    InterviewStrategy,
    ResumeProfile,
)
from app.services.question_bank import QuestionBankService

logger = logging.getLogger(__name__)


def _make_empty_position() -> "JobPosition":
    """Create a minimal JobPosition for fallback scenarios."""
    from app.models.job_position import JobPosition
    return JobPosition(
        id="",
        title="Software Engineer",
        department="",
        level="mid",
        status="active",
    )

logger = logging.getLogger(__name__)


class InterviewAgent:
    """Orchestrates a complete interview session.

    Supports two modes:
    - simple: Legacy IDLE→INTRO→QA_LOOP→WRAPUP→DONE flow (no resume/position)
    - strategy: Multi-phase adaptive flow driven by InterviewStrategy
    """

    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        db: AsyncSession,
        llm: BaseLLMAdapter,
        question_service: QuestionBankService,
        question_generator: "DynamicQuestionGenerator | None" = None,
    ) -> None:
        self.session_id = session_id
        self._ws = websocket
        self._db = db
        self._llm = llm
        self._questions = question_service
        self._question_generator = question_generator
        self._fsm = InterviewFSM()
        self._conversation = ConversationManager()
        self._evaluator = EvaluationEngine(llm)
        self._session: InterviewSession | None = None
        self._current_question_id: str | None = None
        self._current_question_text: str = ""
        self._skip_count: int = 0
        self._started_at: datetime | None = None

        # Strategy mode state
        self._mode: str = "simple"  # "simple" | "strategy"
        self._phase_router: PhaseRouter | None = None
        self._strategy: InterviewStrategy | None = None
        self._profile: ResumeProfile | None = None
        self._gap: GapAnalysis | None = None
        self._position: "JobPosition | None" = None
        self._follow_up_depth: int = 0
        self._parent_question_id: str | None = None

        # Timeout mechanism
        self._timeout_event = asyncio.Event()
        self._pending_timeout: str | None = None  # "skip" | "wrapup"
        self._per_question_task: asyncio.Task | None = None
        self._total_interview_task: asyncio.Task | None = None

    # ── Public API ──────────────────────────────────────────────

    async def start(self) -> None:
        """Begin the interview: load session, detect mode, send intro."""
        self._session = await self._get_session()
        if self._session is None:
            await self._send_error("Session not found")
            return

        self._started_at = datetime.now(timezone.utc)

        # ── Detect mode ────────────────────────────────────────
        strategy_json = self._session.interview_strategy_json
        has_resume_or_position = bool(
            self._session.resume_text or self._session.position_id
        )

        if strategy_json:
            await self._init_strategy_mode(from_json=strategy_json)
        elif has_resume_or_position and self._question_generator:
            await self._init_strategy_mode(from_json=None)
        else:
            await self._init_simple_mode()

    async def _init_simple_mode(self) -> None:
        """Initialize legacy simple mode."""
        self._mode = "simple"
        self._fsm.transition(InterviewEvent.START)
        if self._session:
            self._session.status = InterviewState.INTRO.value
        await self._db.commit()

        self._questions.set_seed(self._generate_seed())
        self._questions.set_initial_difficulty(
            self._session.experience_level if self._session else "mid"
        )

        await self._send_message("interview.start", {
            "session_id": self.session_id,
            "job_title": self._session.job_title if self._session else "",
            "total_questions": self._session.total_questions if self._session else 5,
            "duration_minutes": settings.default_time_limit_minutes,
        })

        intro_text = await self._generate_intro()
        self._conversation.add_message("interviewer", intro_text)
        await self._send_message("interview.chat", {"content": intro_text})
        self._start_total_interview_timer()

    async def _init_strategy_mode(self, from_json: dict | None = None) -> None:
        """Initialize strategy mode with phase-based interview flow."""
        self._mode = "strategy"

        # Deserialize strategy from session or generate it
        if from_json:
            self._strategy = InterviewStrategy(**from_json)
        else:
            await self._generate_strategy()

        if not self._strategy:
            # Fallback to simple mode if strategy generation failed
            logger.warning("Strategy generation failed, falling back to simple mode")
            await self._init_simple_mode()
            return

        # Load related data
        await self._load_strategy_context()

        # Build phase router and FSM
        self._phase_router = PhaseRouter(self._strategy)
        phase_order = self._phase_router.get_phase_order_for_fsm()
        self._fsm.set_phase_order(phase_order)

        # Transition: IDLE → STRATEGY_GEN → first phase
        self._fsm.transition(InterviewEvent.START)
        self._fsm.force_state(InterviewState.STRATEGY_GEN)

        # Send strategy_ready
        await self._send_message("interview.strategy_ready", {
            "strategy_summary": self._strategy.resume_summary,
            "phases_count": len(self._strategy.phases),
            "phase_names": [p.phase_name for p in self._strategy.phases],
        })

        # Transition to first interview phase
        self._fsm.transition(InterviewEvent.STRATEGY_GEN_COMPLETE)
        first_state = self._phase_router.get_first_phase_state()
        self._fsm.force_state(first_state)

        if self._session:
            self._session.status = first_state.value
            self._session.current_phase = self._phase_router.current_phase.phase_name
        await self._db.commit()

        # Seed question bank for fallback
        self._questions.set_seed(self._generate_seed())
        self._questions.set_initial_difficulty(
            self._session.experience_level if self._session else "mid"
        )

        # Send interview.start
        total_q = self._calculate_total_questions()
        await self._send_message("interview.start", {
            "session_id": self.session_id,
            "job_title": self._session.job_title if self._session else "",
            "total_questions": total_q,
            "duration_minutes": settings.default_time_limit_minutes,
        })

        # Send phase intro
        phase_intro = await self._generate_phase_intro()
        self._conversation.add_message("interviewer", phase_intro)
        await self._send_message("interview.chat", {"content": phase_intro})

        # Send phase_change for first phase
        await self._send_message("interview.phase_change", {
            "from_phase": "strategy_gen",
            "to_phase": first_state.value,
            "phase_index": 0,
            "total_phases": len(self._strategy.phases),
            "phase_description": ", ".join(self._phase_router.current_phase.focus_areas),
            "position_context": self._strategy.position_summary,
        })

        # Ask first question if phase has questions
        if self._phase_router.current_phase.max_questions > 0:
            await self._ask_phase_question()
        else:
            await self._advance_phase()

        self._start_total_interview_timer()

    async def handle_message(self, raw: dict) -> None:
        """Dispatch an incoming WebSocket message based on current FSM state."""
        if self._mode == "simple":
            await self._dispatch_simple(raw)
        else:
            await self._dispatch_strategy(raw)

    async def _dispatch_simple(self, raw: dict) -> None:
        """Legacy dispatch for simple mode."""
        state = self._fsm.state
        if state == InterviewState.INTRO:
            await self._handle_intro(raw)
        elif state == InterviewState.QA_LOOP:
            await self._handle_qa(raw)
        elif state == InterviewState.WRAPUP:
            await self._handle_wrapup(raw)

    async def _dispatch_strategy(self, raw: dict) -> None:
        """Phase-based dispatch for strategy mode."""
        state = self._fsm.state

        # Commands work in all phases
        msg_type = raw.get("type", "")
        if msg_type == "command.skip":
            await self._handle_skip()
            return
        if msg_type == "command.repeat":
            await self._handle_repeat()
            return

        # Extract content
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

        # Phase-specific handling
        if state == InterviewState.ICE_BREAK:
            await self._handle_ice_break(content)
        elif state == InterviewState.PROJECT_DEEP_DIVE:
            await self._handle_project_deep_dive(content)
        elif state == InterviewState.TECHNICAL_ASSESSMENT:
            await self._handle_technical_assessment(content)
        elif state == InterviewState.BEHAVIORAL:
            await self._handle_behavioral(content)
        elif state == InterviewState.CANDIDATE_QA:
            await self._handle_candidate_qa(content)
        elif state == InterviewState.WRAPUP:
            await self._handle_wrapup_strategy(content)

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
        """Handle messages during wrapup phase (simple mode)."""
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

    # ── Strategy Mode Phase Handlers ──────────────────────────

    async def _handle_ice_break(self, content: str) -> None:
        """Handle ice_break phase: brief exchange, then advance."""
        if self._current_question_id:
            await self._evaluate_and_continue(content)
        else:
            # Initial ice break response — advance to next phase or question
            if self._phase_router and self._phase_router.has_more_questions_in_phase():
                await self._ask_phase_question()
            else:
                await self._advance_phase()

    async def _handle_project_deep_dive(self, content: str) -> None:
        """Handle project deep dive: STAR probing with position comparison."""
        if self._current_question_id:
            await self._evaluate_and_continue(content)
        elif self._phase_router:
            if self._phase_router.has_more_questions_in_phase():
                await self._ask_phase_question()
            else:
                await self._advance_phase()

    async def _handle_technical_assessment(self, content: str) -> None:
        """Handle technical assessment with follow-up decision logic."""
        if self._current_question_id:
            await self._evaluate_and_continue(content)
        elif self._phase_router:
            if self._phase_router.has_more_questions_in_phase():
                await self._ask_phase_question()
            else:
                await self._advance_phase()

    async def _handle_behavioral(self, content: str) -> None:
        """Handle behavioral questions with level-appropriate themes."""
        if self._current_question_id:
            await self._evaluate_and_continue(content)
        elif self._phase_router:
            if self._phase_router.has_more_questions_in_phase():
                await self._ask_phase_question()
            else:
                await self._advance_phase()

    async def _handle_candidate_qa(self, content: str) -> None:
        """Handle candidate's questions about the role."""
        # Generate a response to the candidate's question
        response = await self._llm.generate(
            prompt=get_phase_prompt(
                "candidate_qa", self._lang,
                position_summary=self._strategy.position_summary if self._strategy else "",
            ),
            system_prompt=self._build_system_prompt(),
            max_tokens=300,
            temperature=0.7,
        )
        if not response or not response.strip():
            response = get_prompt("wrapup_fallback", self._lang)

        await self._send_message("interview.chat", {"content": response})

        # After a few exchanges, advance to wrapup
        if self._phase_router:
            self._phase_router.record_question_asked()
            if not self._phase_router.has_more_questions_in_phase():
                await self._advance_phase()

    async def _handle_wrapup_strategy(self, content: str) -> None:
        """Handle wrapup in strategy mode."""
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

    # ── Strategy Mode Question Flow ───────────────────────────

    async def _ask_phase_question(self) -> None:
        """Generate and ask a question for the current phase in strategy mode."""
        if not self._session or not self._phase_router or not self._strategy:
            return

        phase = self._phase_router.current_phase
        if not self._phase_router.has_more_questions_in_phase():
            await self._advance_phase()
            return

        q_number = self._phase_router.phase_question_counts.get(
            phase.phase_name, 0
        ) + 1

        # Use dynamic question generator
        q_data = None
        if self._question_generator:
            q_data = await self._question_generator.generate_next(
                phase=phase,
                strategy=self._strategy,
                position=self._position,
                profile=self._profile,
                gap=self._gap,
                language=self._lang,
                question_number=q_number,
            )

        if q_data is None:
            # Fallback to question bank
            q_data = self._questions.select_question()

        if q_data is None:
            await self._advance_phase()
            return

        # Create DB record
        idx = self._session.current_question_index
        question = Question(
            session_id=self.session_id,
            question_text=q_data.question_text,
            category=q_data.category,
            difficulty=q_data.difficulty,
            expected_keywords=q_data.expected_keywords,
            order_index=idx,
            status="asked",
            phase=phase.phase_name,
            asked_at=datetime.now(timezone.utc),
        )
        self._db.add(question)
        await self._db.flush()
        self._current_question_id = question.id
        self._current_question_text = q_data.question_text
        self._session.current_question_index = idx + 1
        self._phase_router.record_question_asked()

        # Update session phase tracking
        self._session.current_phase = phase.phase_name
        self._session.phase_question_counts = self._phase_router.phase_question_counts
        await self._db.commit()

        # Wrap question in natural language
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

        # Determine message type (follow_up vs question)
        if self._follow_up_depth > 0 and self._parent_question_id:
            await self._send_message("interview.follow_up", {
                "question_id": question.id,
                "parent_question_id": self._parent_question_id,
                "content": wrapped,
                "category": q_data.category,
                "difficulty": q_data.difficulty,
                "depth": self._follow_up_depth,
                "question_number": idx + 1,
                "total_questions": self._calculate_total_questions(),
            })
        else:
            await self._send_message("interview.question", {
                "question_id": question.id,
                "content": wrapped,
                "category": q_data.category,
                "difficulty": q_data.difficulty,
                "question_number": idx + 1,
                "total_questions": self._calculate_total_questions(),
            })

        self._start_per_question_timer()

    async def _advance_phase(self) -> None:
        """Transition to the next interview phase in strategy mode."""
        if not self._phase_router or not self._session:
            return

        from_state = self._phase_router.current_state
        next_state = self._phase_router.advance_phase()

        if next_state is None:
            # All phases complete, go to wrapup
            await self._start_wrapup()
            return

        # Persist phase tracking
        self._session.current_phase = self._phase_router.current_phase.phase_name
        self._session.phase_question_counts = self._phase_router.phase_question_counts
        self._session.status = next_state.value
        await self._db.commit()

        # FSM transition
        self._fsm.transition(InterviewEvent.PHASE_COMPLETE)

        # Reset follow-up tracking
        self._follow_up_depth = 0
        self._parent_question_id = None

        # Send phase_change message
        phase = self._phase_router.current_phase
        await self._send_message("interview.phase_change", {
            "from_phase": from_state.value if from_state else "",
            "to_phase": next_state.value,
            "phase_index": self._phase_router.current_phase_index,
            "total_phases": self._phase_router.total_phases,
            "phase_description": ", ".join(phase.focus_areas),
            "position_context": self._strategy.position_summary if self._strategy else "",
        })

        # Start new phase
        if phase.max_questions > 0:
            phase_intro = await self._generate_phase_intro()
            if phase_intro:
                self._conversation.add_message("interviewer", phase_intro)
                await self._send_message("interview.chat", {"content": phase_intro})
            await self._ask_phase_question()
        else:
            # Phase with no questions — just send intro and advance
            phase_intro = await self._generate_phase_intro()
            if phase_intro:
                self._conversation.add_message("interviewer", phase_intro)
                await self._send_message("interview.chat", {"content": phase_intro})
            await self._advance_phase()

    async def _decide_follow_up(self, answer: str, evaluation) -> bool:
        """LLM-based decision: follow up, advance, or skip?"""
        if self._follow_up_depth >= 3:
            return False

        position_skills = ""
        if self._position:
            skills = (self._position.required_skills or []) + (self._position.preferred_skills or [])
            position_skills = ", ".join(s.get("skill", "") for s in skills[:5])

        phase_name = self._phase_router.current_phase.phase_name if self._phase_router else "qa"

        try:
            prompt = get_follow_up_prompt(
                "decision", self._lang,
                question=self._current_question_text,
                answer=answer[:500],
                depth=str(self._follow_up_depth),
                position_skills=position_skills or "general",
                phase=phase_name,
            )
            raw = await self._llm.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.2,
            )
            data = self._parse_decision_json(raw)
            return data.get("decision") == "follow_up"
        except Exception:
            return False

    async def _ask_follow_up(self, last_answer: str) -> None:
        """Generate and ask a follow-up question."""
        if not self._phase_router or not self._session:
            return

        self._follow_up_depth += 1
        if self._parent_question_id is None:
            self._parent_question_id = self._current_question_id

        phase = self._phase_router.current_phase
        q_data = None
        if self._question_generator:
            q_data = await self._question_generator.generate_next(
                phase=phase,
                strategy=self._strategy,
                position=self._position,
                profile=self._profile,
                gap=self._gap,
                language=self._lang,
                parent_answer=last_answer,
                current_depth=self._follow_up_depth,
            )

        if q_data is None:
            # Fallback: generate directly via LLM
            try:
                prompt = get_follow_up_prompt(
                    "generate", self._lang,
                    question=self._current_question_text,
                    answer=last_answer[:500],
                    depth=str(self._follow_up_depth),
                    topic="the candidate's last response",
                    position_skills="general",
                )
                raw = await self._llm.generate(
                    prompt=prompt,
                    system_prompt="You are a technical interviewer. Output ONLY the follow-up question.",
                    max_tokens=200,
                    temperature=0.7,
                )
                if raw and raw.strip():
                    q_data = QuestionData(
                        question_text=raw.strip(),
                        category="follow_up",
                        difficulty="mid",
                        expected_keywords=[],
                    )
            except Exception:
                pass

        if q_data is None:
            self._follow_up_depth = 0
            self._parent_question_id = None
            await self._ask_phase_question()
            return

        # Create DB record
        idx = self._session.current_question_index
        question = Question(
            session_id=self.session_id,
            question_text=q_data.question_text,
            category=q_data.category,
            difficulty=q_data.difficulty,
            expected_keywords=q_data.expected_keywords,
            order_index=idx,
            status="asked",
            phase=phase.phase_name,
            asked_at=datetime.now(timezone.utc),
        )
        self._db.add(question)
        await self._db.flush()
        self._current_question_id = question.id
        self._current_question_text = q_data.question_text
        self._session.current_question_index = idx + 1
        self._phase_router.record_question_asked()
        self._session.phase_question_counts = self._phase_router.phase_question_counts
        await self._db.commit()

        self._conversation.add_message("interviewer", q_data.question_text)

        await self._send_message("interview.follow_up", {
            "question_id": question.id,
            "parent_question_id": self._parent_question_id,
            "content": q_data.question_text,
            "category": q_data.category,
            "difficulty": q_data.difficulty,
            "depth": self._follow_up_depth,
            "question_number": idx + 1,
            "total_questions": self._calculate_total_questions(),
        })

        self._start_per_question_timer()

    async def _generate_phase_intro(self) -> str:
        """Generate a phase introduction message."""
        if not self._phase_router:
            return ""

        phase = self._phase_router.current_phase
        phase_name = phase.phase_name

        try:
            prompt = get_phase_prompt(
                phase_name, self._lang,
                resume_summary=self._strategy.resume_summary if self._strategy else "",
                position_summary=self._strategy.position_summary if self._strategy else "",
            )
            raw = await self._llm.generate(
                prompt=prompt,
                system_prompt=self._build_system_prompt(),
                max_tokens=200,
                temperature=0.8,
            )
            return raw.strip() if raw else ""
        except Exception:
            return ""

    async def _generate_strategy(self) -> None:
        """Auto-generate interview strategy from resume + position data."""
        if not self._session:
            return

        # Parse resume if needed
        if self._session.resume_text and not self._profile:
            try:
                from app.services.resume_parser import ResumeParserService
                parser = ResumeParserService(self._llm)
                self._profile = await parser.parse(self._session.resume_text)
                self._session.resume_profile_json = self._profile.model_dump()
            except Exception as exc:
                logger.warning(f"Resume parsing failed: {exc}")

        # Load position if needed
        if self._session.position_id and not self._position:
            try:
                from app.models.job_position import JobPosition
                stmt = select(JobPosition).where(
                    JobPosition.id == self._session.position_id
                )
                result = await self._db.execute(stmt)
                self._position = result.scalar_one_or_none()
            except Exception as exc:
                logger.warning(f"Position loading failed: {exc}")

        # Run gap analysis
        if self._profile and self._position:
            try:
                from app.services.gap_analyzer import GapAnalyzerService
                analyzer = GapAnalyzerService(self._llm)
                self._gap = await analyzer.analyze(self._profile, self._position)
                self._session.gap_analysis_json = self._gap.model_dump()
            except Exception as exc:
                logger.warning(f"Gap analysis failed: {exc}")

        # Generate strategy
        try:
            from app.services.strategy_generator import StrategyGeneratorService
            generator = StrategyGeneratorService(self._llm)
            self._strategy = await generator.generate(
                session_id=self.session_id,
                profile=self._profile or ResumeProfile(
                    name=self._session.candidate_name,
                    years_of_experience=0,
                    education=[],
                    skills=[],
                    projects=[],
                    work_history=[],
                    inferred_level=self._session.experience_level,
                    key_strengths=[],
                    potential_risk_areas=[],
                ),
                position=self._position or _make_empty_position(),
                gap=self._gap,
                experience_level=self._session.experience_level,
            )
            self._session.interview_strategy_json = self._strategy.model_dump()
        except Exception as exc:
            logger.warning(f"Strategy generation failed: {exc}")
            self._strategy = None

        await self._db.commit()

    async def _load_strategy_context(self) -> None:
        """Load related data for strategy mode."""
        if not self._session:
            return

        # Load profile
        if self._session.resume_profile_json:
            try:
                self._profile = ResumeProfile(**self._session.resume_profile_json)
            except Exception:
                pass

        # Load gap analysis
        if self._session.gap_analysis_json:
            try:
                self._gap = GapAnalysis(**self._session.gap_analysis_json)
            except Exception:
                pass

        # Load position
        if self._session.position_id:
            try:
                from app.models.job_position import JobPosition
                stmt = select(JobPosition).where(
                    JobPosition.id == self._session.position_id
                )
                result = await self._db.execute(stmt)
                self._position = result.scalar_one_or_none()
            except Exception:
                pass

    def _calculate_total_questions(self) -> int:
        """Calculate total questions across all phases."""
        if self._strategy:
            return sum(p.max_questions for p in self._strategy.phases)
        if self._session:
            return self._session.total_questions
        return 5

    @staticmethod
    def _parse_decision_json(raw: str) -> dict:
        """Parse LLM follow-up decision output."""
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    # ── Evaluation & Continuation ─────────────────────────────

    async def _evaluate_and_continue(self, answer_text: str) -> None:
        """Evaluate answer, send results, and determine next step."""
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

        # Build evaluation context for strategy mode
        kwargs: dict = {}
        if self._mode == "strategy" and self._strategy:
            kwargs["weights"] = self._strategy.scoring_weights
            if self._phase_router:
                kwargs["phase"] = self._phase_router.current_phase.phase_name
            kwargs["position_context"] = self._strategy.position_summary

        evaluation = await self._evaluator.evaluate(
            q_data, answer_text, language=self._lang, **kwargs,
        )

        # Determine position requirement context for this question
        relates_to_position = None
        if self._mode == "strategy" and self._strategy:
            # Look up relevant position requirement from tech focus areas
            for area in (self._strategy.tech_focus_areas or []):
                if area.topic.lower() in question.question_text.lower():
                    relates_to_position = area.topic
                    break

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
            # P3: Behavioral dimensions
            dimension_teamwork=(
                evaluation.behavioral.teamwork if evaluation.behavioral else None
            ),
            dimension_leadership=(
                evaluation.behavioral.leadership if evaluation.behavioral else None
            ),
            dimension_ownership=(
                evaluation.behavioral.ownership if evaluation.behavioral else None
            ),
            dimension_growth_mindset=(
                evaluation.behavioral.growth_mindset if evaluation.behavioral else None
            ),
            dimension_culture_fit=(
                evaluation.behavioral.culture_fit if evaluation.behavioral else None
            ),
            # P3: Position match dimensions
            dimension_skill_coverage=(
                evaluation.position_match.skill_coverage if evaluation.position_match else None
            ),
            dimension_experience_alignment=(
                evaluation.position_match.experience_alignment if evaluation.position_match else None
            ),
            dimension_level_alignment=(
                evaluation.position_match.level_alignment if evaluation.position_match else None
            ),
            dimension_domain_fit=(
                evaluation.position_match.domain_fit if evaluation.position_match else None
            ),
            dimension_growth_potential=(
                evaluation.position_match.growth_potential if evaluation.position_match else None
            ),
            # P3: Follow-up tracking
            question_chain_depth=self._follow_up_depth,
            is_follow_up=self._follow_up_depth > 0,
            relates_to_position_requirement=relates_to_position,
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

        strength_str = "; ".join(evaluation.strengths[:2]) if evaluation.strengths else "Good effort."
        await self._send_message("interview.evaluation", {
            "feedback": strength_str,
        })

        # ── Strategy mode: follow-up decision ──────────────────
        if self._mode == "strategy" and self._phase_router:
            should_follow_up = await self._decide_follow_up(answer_text, evaluation)
            if should_follow_up:
                await self._ask_follow_up(answer_text)
                return

            # Reset follow-up tracking
            self._follow_up_depth = 0
            self._parent_question_id = None

            # Check phase completion
            if self._phase_router.has_more_questions_in_phase():
                await self._ask_phase_question()
            elif self._phase_router.is_phase_ready_to_complete():
                await self._advance_phase()
            else:
                await self._ask_phase_question()
            return

        # Simple mode: fall through to legacy flow
        self._questions.update_difficulty(evaluation.score)
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

        # Strategy mode: skip within current phase
        if self._mode == "strategy" and self._phase_router:
            self._follow_up_depth = 0
            self._parent_question_id = None
            if self._phase_router.has_more_questions_in_phase():
                await self._ask_phase_question()
            else:
                await self._advance_phase()
            return

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

        paused_state = {
            "previous_state": self._fsm.state.value,
            "current_question_id": self._current_question_id,
            "current_question_index": self._session.current_question_index,
            "skip_count": self._skip_count,
            "conversation_history": conv_data,
            "mode": self._mode,
        }

        # Strategy mode extras
        if self._mode == "strategy" and self._phase_router:
            paused_state["phase_router"] = self._phase_router.to_dict()
            paused_state["follow_up_depth"] = self._follow_up_depth
            paused_state["parent_question_id"] = self._parent_question_id

        self._session.metadata_json["paused_state"] = paused_state
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
        self._mode = paused.get("mode", "simple")

        # Restore question index
        restored_idx = paused.get("current_question_index", 0)
        if self._session:
            self._session.current_question_index = restored_idx

        # Restore FSM state
        prev_state_str = paused.get("previous_state", InterviewState.QA_LOOP.value)
        prev_state = InterviewState(prev_state_str)
        self._fsm.force_state(prev_state)

        # Strategy mode restore
        if self._mode == "strategy":
            # Reload strategy context
            await self._load_strategy_context()
            strategy_json = self._session.interview_strategy_json
            if strategy_json:
                try:
                    self._strategy = InterviewStrategy(**strategy_json)
                except Exception:
                    pass

            if self._strategy:
                # Restore phase router
                router_data = paused.get("phase_router")
                if router_data:
                    self._phase_router = PhaseRouter.from_dict(self._strategy, router_data)
                else:
                    self._phase_router = PhaseRouter(self._strategy)

                phase_order = self._phase_router.get_phase_order_for_fsm()
                self._fsm.set_phase_order(phase_order)

                # Restore follow-up state
                self._follow_up_depth = paused.get("follow_up_depth", 0)
                self._parent_question_id = paused.get("parent_question_id")

        # Update session
        if self._session:
            self._session.status = prev_state.value
            await self._db.commit()

        # Restore question bank seed (for fallback)
        self._questions.set_seed(self._generate_seed())
        self._questions.set_initial_difficulty(
            self._session.experience_level if self._session else "mid"
        )

        # Send resume notification
        conv_history = [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in self._conversation.get_full_history()
        ]
        total_q = self._calculate_total_questions()
        await self._send_message("interview.resume", {
            "session_id": self.session_id,
            "job_title": self._session.job_title if self._session else "",
            "previous_state": prev_state_str,
            "question_index": restored_idx,
            "total_questions": total_q,
            "conversation_history": conv_history,
        })

        # Restart per-question timer if there's an active question
        if self._current_question_id and prev_state not in (
            InterviewState.WRAPUP,
            InterviewState.DONE,
        ):
            self._start_per_question_timer()

        self._start_total_interview_timer()
        logger.info(f"Session {self.session_id} resumed from {prev_state_str} (mode={self._mode})")

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

        if self._mode == "strategy" and self._strategy:
            # Enhanced prompt with full strategy context
            position_skills = ""
            if self._position:
                skills = (self._position.required_skills or []) + (self._position.preferred_skills or [])
                position_skills = ", ".join(s.get("skill", "") for s in skills[:8])

            behavioral_themes = ""
            if self._strategy.behavioral_themes:
                behavioral_themes = ", ".join(
                    t.theme for t in self._strategy.behavioral_themes[:3]
                )

            return SystemPromptBuilder.build_for_phase(
                job_title=self._session.job_title,
                experience_level=self._session.experience_level,
                current_phase=self._fsm.state.value,
                key_skills=self._session.key_skills or [],
                questions_asked=self._session.current_question_index,
                total_questions=self._calculate_total_questions(),
                elapsed_minutes=elapsed,
                recent_history=self._conversation.format_window_for_llm(),
                language=self._lang,
                resume_summary=self._strategy.resume_summary,
                position_summary=self._strategy.position_summary,
                position_skills=position_skills,
                gap_summary=self._gap.experience_gap_summary if self._gap else "",
                behavioral_themes=behavioral_themes,
                difficulty_strategy=self._strategy.difficulty_strategy,
            )

        # Simple mode
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
