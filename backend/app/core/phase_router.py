"""Phase router — manages phase sequencing from InterviewStrategy data."""

import logging

from app.core.fsm import InterviewState
from app.schemas.session import InterviewStrategy, PhaseConfig

logger = logging.getLogger(__name__)


class PhaseRouter:
    """Manages phase sequencing from InterviewStrategy data.

    Maps phase_name strings from strategy config to InterviewState enum values,
    handles per-phase question tracking, and determines phase transitions.
    """

    PHASE_STATE_MAP: dict[str, InterviewState] = {
        "ice_break": InterviewState.ICE_BREAK,
        "project_deep_dive": InterviewState.PROJECT_DEEP_DIVE,
        "technical_assessment": InterviewState.TECHNICAL_ASSESSMENT,
        "behavioral": InterviewState.BEHAVIORAL,
        "candidate_qa": InterviewState.CANDIDATE_QA,
        "wrapup": InterviewState.WRAPUP,
    }

    def __init__(self, strategy: InterviewStrategy) -> None:
        self._phases: list[PhaseConfig] = list(strategy.phases)
        self._current_phase_index: int = 0
        self._phase_question_counts: dict[str, int] = {
            p.phase_name: 0 for p in strategy.phases
        }
        # Build ordered state list
        self._state_order: list[InterviewState] = [
            self.PHASE_STATE_MAP[p.phase_name]
            for p in strategy.phases
            if p.phase_name in self.PHASE_STATE_MAP
        ]
        if not self._state_order:
            # Fallback: at least have wrapup
            self._state_order = [InterviewState.WRAPUP]

    # ── Properties ────────────────────────────────────────────

    @property
    def current_phase(self) -> PhaseConfig:
        return self._phases[self._current_phase_index]

    @property
    def current_state(self) -> InterviewState:
        if self._current_phase_index < len(self._state_order):
            return self._state_order[self._current_phase_index]
        return InterviewState.WRAPUP

    @property
    def current_phase_index(self) -> int:
        return self._current_phase_index

    @property
    def total_phases(self) -> int:
        return len(self._phases)

    @property
    def phase_question_counts(self) -> dict[str, int]:
        return dict(self._phase_question_counts)

    @property
    def is_last_phase(self) -> bool:
        return self._current_phase_index >= len(self._phases) - 1

    # ── Phase navigation ───────────────────────────────────────

    def advance_phase(self) -> InterviewState | None:
        """Move to next phase. Returns new state or None if at end."""
        if self.is_last_phase:
            return None
        self._current_phase_index += 1
        logger.info(
            f"Phase advanced to {self.current_phase.phase_name} "
            f"({self._current_phase_index + 1}/{len(self._phases)})"
        )
        return self.current_state

    def jump_to_phase(self, phase_name: str) -> InterviewState | None:
        """Jump to a specific phase by name. Used for resume."""
        for i, phase in enumerate(self._phases):
            if phase.phase_name == phase_name:
                self._current_phase_index = i
                return self.current_state
        return None

    # ── Question tracking ──────────────────────────────────────

    def record_question_asked(self) -> None:
        """Increment the question counter for the current phase."""
        phase_name = self.current_phase.phase_name
        self._phase_question_counts[phase_name] = (
            self._phase_question_counts.get(phase_name, 0) + 1
        )

    def has_more_questions_in_phase(self) -> bool:
        """Check if current phase can accept more questions."""
        phase = self.current_phase
        count = self._phase_question_counts.get(phase.phase_name, 0)
        return count < phase.max_questions

    def is_phase_ready_to_complete(self) -> bool:
        """Check if current phase has met minimum question count."""
        phase = self.current_phase
        count = self._phase_question_counts.get(phase.phase_name, 0)
        return count >= phase.min_questions

    def questions_remaining_in_phase(self) -> int:
        """How many more questions can be asked in current phase."""
        phase = self.current_phase
        count = self._phase_question_counts.get(phase.phase_name, 0)
        return max(0, phase.max_questions - count)

    # ── FSM integration ────────────────────────────────────────

    def get_phase_order_for_fsm(self) -> list[InterviewState]:
        """Returns the state list for injection into the FSM."""
        return list(self._state_order)

    def get_first_phase_state(self) -> InterviewState:
        """Returns the first interview phase state."""
        if self._state_order:
            return self._state_order[0]
        return InterviewState.WRAPUP

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize router state for persistence."""
        return {
            "current_phase_index": self._current_phase_index,
            "phase_question_counts": self._phase_question_counts,
        }

    @classmethod
    def from_dict(
        cls, strategy: InterviewStrategy, data: dict
    ) -> "PhaseRouter":
        """Restore router state from persisted data."""
        router = cls(strategy)
        router._current_phase_index = data.get("current_phase_index", 0)
        router._phase_question_counts = data.get("phase_question_counts", {})
        return router
