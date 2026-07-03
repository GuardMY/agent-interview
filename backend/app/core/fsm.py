from enum import Enum


class InterviewState(str, Enum):
    IDLE = "idle"
    # Legacy states
    INTRO = "intro"
    QA_LOOP = "qa_loop"
    WRAPUP = "wrapup"
    PAUSED = "paused"
    DONE = "done"
    # P2: Multi-phase strategy states
    STRATEGY_GEN = "strategy_gen"
    ICE_BREAK = "ice_break"
    PROJECT_DEEP_DIVE = "project_deep_dive"
    TECHNICAL_ASSESSMENT = "technical_assessment"
    BEHAVIORAL = "behavioral"
    CANDIDATE_QA = "candidate_qa"


class InterviewEvent(str, Enum):
    START = "start"
    INTRO_COMPLETE = "intro_complete"
    ANSWER_EVALUATED = "answer_evaluated"
    QUESTION_EXHAUSTED = "question_exhausted"
    SKIP_QUESTION = "skip_question"
    TIME_UP = "time_up"
    WRAPUP_COMPLETE = "wrapup_complete"
    CANDIDATE_DISCONNECT = "candidate_disconnect"
    CONNECTION_LOST = "connection_lost"
    RECONNECT = "reconnect"
    ERROR = "error"
    # P2: Strategy/phase events
    STRATEGY_GEN_COMPLETE = "strategy_gen_complete"
    PHASE_COMPLETE = "phase_complete"


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""
    pass


class InterviewFSM:
    """Finite state machine for interview lifecycle management.

    Supports two modes:
    - Simple mode: IDLE → INTRO → QA_LOOP → WRAPUP → DONE (legacy)
    - Strategy mode: IDLE → STRATEGY_GEN → phase_1 → ... → phase_n → WRAPUP → DONE
      Phases are dynamically ordered via set_phase_order().
    """

    # Phases that represent active interviewing (not meta-states)
    INTERVIEW_PHASES = {
        InterviewState.ICE_BREAK,
        InterviewState.PROJECT_DEEP_DIVE,
        InterviewState.TECHNICAL_ASSESSMENT,
        InterviewState.BEHAVIORAL,
        InterviewState.CANDIDATE_QA,
    }

    _transitions: dict[tuple[InterviewState, InterviewEvent], InterviewState] = {
        # ── IDLE ──
        (InterviewState.IDLE, InterviewEvent.START): InterviewState.INTRO,
        (InterviewState.IDLE, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.IDLE, InterviewEvent.ERROR): InterviewState.DONE,

        # ── INTRO (legacy) ──
        (InterviewState.INTRO, InterviewEvent.INTRO_COMPLETE): InterviewState.QA_LOOP,
        (InterviewState.INTRO, InterviewEvent.TIME_UP): InterviewState.QA_LOOP,
        (InterviewState.INTRO, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.INTRO, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.INTRO, InterviewEvent.ERROR): InterviewState.DONE,

        # ── QA_LOOP (legacy) ──
        (InterviewState.QA_LOOP, InterviewEvent.ANSWER_EVALUATED): InterviewState.QA_LOOP,
        (InterviewState.QA_LOOP, InterviewEvent.SKIP_QUESTION): InterviewState.QA_LOOP,
        (InterviewState.QA_LOOP, InterviewEvent.QUESTION_EXHAUSTED): InterviewState.WRAPUP,
        (InterviewState.QA_LOOP, InterviewEvent.TIME_UP): InterviewState.WRAPUP,
        (InterviewState.QA_LOOP, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.QA_LOOP, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.QA_LOOP, InterviewEvent.ERROR): InterviewState.WRAPUP,

        # ── STRATEGY_GEN ──
        (InterviewState.STRATEGY_GEN, InterviewEvent.STRATEGY_GEN_COMPLETE): InterviewState.ICE_BREAK,  # default
        (InterviewState.STRATEGY_GEN, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.STRATEGY_GEN, InterviewEvent.ERROR): InterviewState.DONE,

        # ── WRAPUP ──
        (InterviewState.WRAPUP, InterviewEvent.WRAPUP_COMPLETE): InterviewState.DONE,
        (InterviewState.WRAPUP, InterviewEvent.TIME_UP): InterviewState.DONE,
        (InterviewState.WRAPUP, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.WRAPUP, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.WRAPUP, InterviewEvent.ERROR): InterviewState.DONE,

        # ── PAUSED ──
        (InterviewState.PAUSED, InterviewEvent.RECONNECT): InterviewState.QA_LOOP,  # default; overridden via _paused_origin
        (InterviewState.PAUSED, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.PAUSED, InterviewEvent.ERROR): InterviewState.DONE,
    }

    # Generic transitions shared by all phases (populated once for each interview phase)
    _PHASE_GENERIC_TRANSITIONS: dict[InterviewEvent, InterviewState] = {
        InterviewEvent.CONNECTION_LOST: InterviewState.PAUSED,
        InterviewEvent.CANDIDATE_DISCONNECT: InterviewState.DONE,
        InterviewEvent.ERROR: InterviewState.WRAPUP,
    }

    def __init__(self, initial_state: InterviewState = InterviewState.IDLE) -> None:
        self._state = initial_state
        self._history: list[tuple[InterviewState, InterviewEvent, InterviewState]] = []
        self._phase_order: list[InterviewState] | None = None
        self._paused_origin: InterviewState | None = None

    @property
    def state(self) -> InterviewState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state not in (InterviewState.DONE,)

    @property
    def paused_origin(self) -> InterviewState | None:
        """The state we were in before being paused (for reconnect targeting)."""
        return self._paused_origin

    def force_state(self, state: InterviewState) -> None:
        """Directly set the current state (used during resume)."""
        self._state = state

    def set_phase_order(self, phases: list[InterviewState]) -> None:
        """Configure dynamic phase ordering for strategy mode.

        Args:
            phases: Ordered list of phase states (e.g. [ICE_BREAK, PROJECT_DEEP_DIVE, ...]).
                    The FSM will transition between them on PHASE_COMPLETE events.
        """
        self._phase_order = list(phases)

    def transition(self, event: InterviewEvent) -> InterviewState:
        """Transition to next state based on event. Raises on invalid transition."""
        # Handle dynamic PHASE_COMPLETE (strategy mode)
        if event == InterviewEvent.PHASE_COMPLETE and self._phase_order:
            next_state = self._resolve_phase_complete()
            if next_state is not None:
                self._history.append((self._state, event, next_state))
                self._state = next_state
                return self._state

        # Handle CONNECTION_LOST for phase states (track origin for reconnect)
        if event == InterviewEvent.CONNECTION_LOST and self._state in self.INTERVIEW_PHASES:
            self._paused_origin = self._state
            self._history.append((self._state, event, InterviewState.PAUSED))
            self._state = InterviewState.PAUSED
            return self._state

        # Handle RECONNECT when we have a paused_origin
        if event == InterviewEvent.RECONNECT and self._paused_origin is not None:
            target = self._paused_origin
            self._paused_origin = None
            self._history.append((self._state, event, target))
            self._state = target
            return self._state

        # Handle generic phase transitions
        if self._state in self.INTERVIEW_PHASES:
            generic = self._PHASE_GENERIC_TRANSITIONS.get(event)
            if generic is not None:
                self._history.append((self._state, event, generic))
                self._state = generic
                return self._state

        # Static transition lookup
        key = (self._state, event)
        if key not in self._transitions:
            raise InvalidTransitionError(
                f"No transition from {self._state.value} with event {event.value}"
            )
        next_state = self._transitions[key]
        self._history.append((self._state, event, next_state))
        self._state = next_state
        return self._state

    def can_transition(self, event: InterviewEvent) -> bool:
        """Check if a valid transition without executing it."""
        if event == InterviewEvent.PHASE_COMPLETE and self._phase_order:
            try:
                idx = self._phase_order.index(self._state)
                return idx < len(self._phase_order) - 1
            except ValueError:
                return False
        if self._state in self.INTERVIEW_PHASES:
            if event in self._PHASE_GENERIC_TRANSITIONS:
                return True
        if event == InterviewEvent.RECONNECT and self._paused_origin is not None:
            return True
        return (self._state, event) in self._transitions

    def reset(self) -> None:
        """Reset to IDLE state (for testing)."""
        self._state = InterviewState.IDLE
        self._history.clear()
        self._phase_order = None
        self._paused_origin = None

    # ── Private helpers ─────────────────────────────────────────

    def _resolve_phase_complete(self) -> InterviewState | None:
        """Determine the next phase in the dynamic phase order."""
        if not self._phase_order:
            return None
        try:
            idx = self._phase_order.index(self._state)
        except ValueError:
            return InterviewState.WRAPUP
        if idx + 1 < len(self._phase_order):
            return self._phase_order[idx + 1]
        return InterviewState.WRAPUP
