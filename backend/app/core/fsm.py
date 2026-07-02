from enum import Enum


class InterviewState(str, Enum):
    IDLE = "idle"
    INTRO = "intro"
    QA_LOOP = "qa_loop"
    WRAPUP = "wrapup"
    PAUSED = "paused"
    DONE = "done"


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


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""
    pass


class InterviewFSM:
    """Finite state machine for interview lifecycle management."""

    _transitions: dict[tuple[InterviewState, InterviewEvent], InterviewState] = {
        (InterviewState.IDLE, InterviewEvent.START): InterviewState.INTRO,
        (InterviewState.IDLE, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.IDLE, InterviewEvent.ERROR): InterviewState.DONE,

        (InterviewState.INTRO, InterviewEvent.INTRO_COMPLETE): InterviewState.QA_LOOP,
        (InterviewState.INTRO, InterviewEvent.TIME_UP): InterviewState.QA_LOOP,
        (InterviewState.INTRO, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.INTRO, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.INTRO, InterviewEvent.ERROR): InterviewState.DONE,

        (InterviewState.QA_LOOP, InterviewEvent.ANSWER_EVALUATED): InterviewState.QA_LOOP,
        (InterviewState.QA_LOOP, InterviewEvent.SKIP_QUESTION): InterviewState.QA_LOOP,
        (InterviewState.QA_LOOP, InterviewEvent.QUESTION_EXHAUSTED): InterviewState.WRAPUP,
        (InterviewState.QA_LOOP, InterviewEvent.TIME_UP): InterviewState.WRAPUP,
        (InterviewState.QA_LOOP, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.QA_LOOP, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.QA_LOOP, InterviewEvent.ERROR): InterviewState.WRAPUP,

        (InterviewState.WRAPUP, InterviewEvent.WRAPUP_COMPLETE): InterviewState.DONE,
        (InterviewState.WRAPUP, InterviewEvent.TIME_UP): InterviewState.DONE,
        (InterviewState.WRAPUP, InterviewEvent.CONNECTION_LOST): InterviewState.PAUSED,
        (InterviewState.WRAPUP, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.WRAPUP, InterviewEvent.ERROR): InterviewState.DONE,

        (InterviewState.PAUSED, InterviewEvent.RECONNECT): InterviewState.QA_LOOP,  # placeholder
        (InterviewState.PAUSED, InterviewEvent.CANDIDATE_DISCONNECT): InterviewState.DONE,
        (InterviewState.PAUSED, InterviewEvent.ERROR): InterviewState.DONE,
    }

    def __init__(self, initial_state: InterviewState = InterviewState.IDLE) -> None:
        self._state = initial_state
        self._history: list[tuple[InterviewState, InterviewEvent, InterviewState]] = []

    @property
    def state(self) -> InterviewState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state not in (InterviewState.DONE,)

    def force_state(self, state: InterviewState) -> None:
        """Directly set the current state (used during resume)."""
        self._state = state

    def transition(self, event: InterviewEvent) -> InterviewState:
        """Transition to next state based on event. Raises on invalid transition."""
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
        return (self._state, event) in self._transitions

    def reset(self) -> None:
        """Reset to IDLE state (for testing)."""
        self._state = InterviewState.IDLE
        self._history.clear()
