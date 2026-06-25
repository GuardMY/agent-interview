import pytest

from app.core.fsm import InterviewEvent, InterviewFSM, InterviewState, InvalidTransitionError


class TestInterviewFSM:
    def test_initial_state_is_idle(self) -> None:
        fsm = InterviewFSM()
        assert fsm.state == InterviewState.IDLE

    def test_idle_to_intro(self) -> None:
        fsm = InterviewFSM()
        new_state = fsm.transition(InterviewEvent.START)
        assert new_state == InterviewState.INTRO

    def test_intro_to_qa_loop(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        new_state = fsm.transition(InterviewEvent.INTRO_COMPLETE)
        assert new_state == InterviewState.QA_LOOP

    def test_qa_loop_stays_in_loop(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        fsm.transition(InterviewEvent.INTRO_COMPLETE)
        new_state = fsm.transition(InterviewEvent.ANSWER_EVALUATED)
        assert new_state == InterviewState.QA_LOOP

    def test_skip_stays_in_loop(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        fsm.transition(InterviewEvent.INTRO_COMPLETE)
        new_state = fsm.transition(InterviewEvent.SKIP_QUESTION)
        assert new_state == InterviewState.QA_LOOP

    def test_question_exhausted_to_wrapup(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        fsm.transition(InterviewEvent.INTRO_COMPLETE)
        new_state = fsm.transition(InterviewEvent.QUESTION_EXHAUSTED)
        assert new_state == InterviewState.WRAPUP

    def test_time_up_from_qa_loop(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        fsm.transition(InterviewEvent.INTRO_COMPLETE)
        new_state = fsm.transition(InterviewEvent.TIME_UP)
        assert new_state == InterviewState.WRAPUP

    def test_wrapup_to_done(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        fsm.transition(InterviewEvent.INTRO_COMPLETE)
        fsm.transition(InterviewEvent.QUESTION_EXHAUSTED)
        new_state = fsm.transition(InterviewEvent.WRAPUP_COMPLETE)
        assert new_state == InterviewState.DONE

    def test_full_happy_path(self) -> None:
        fsm = InterviewFSM()
        assert fsm.transition(InterviewEvent.START) == InterviewState.INTRO
        assert fsm.transition(InterviewEvent.INTRO_COMPLETE) == InterviewState.QA_LOOP
        # Loop N times
        for _ in range(3):
            assert fsm.transition(InterviewEvent.ANSWER_EVALUATED) == InterviewState.QA_LOOP
        assert fsm.transition(InterviewEvent.QUESTION_EXHAUSTED) == InterviewState.WRAPUP
        assert fsm.transition(InterviewEvent.WRAPUP_COMPLETE) == InterviewState.DONE

    def test_invalid_transition_raises_error(self) -> None:
        fsm = InterviewFSM()
        with pytest.raises(InvalidTransitionError):
            fsm.transition(InterviewEvent.ANSWER_EVALUATED)  # Not valid from IDLE

    def test_can_transition(self) -> None:
        fsm = InterviewFSM()
        assert fsm.can_transition(InterviewEvent.START) is True
        assert fsm.can_transition(InterviewEvent.ANSWER_EVALUATED) is False

    def test_candidate_disconnect_from_any_state(self) -> None:
        for state in [InterviewState.IDLE, InterviewState.INTRO, InterviewState.QA_LOOP]:
            fsm = InterviewFSM()
            if state == InterviewState.INTRO:
                fsm.transition(InterviewEvent.START)
            elif state == InterviewState.QA_LOOP:
                fsm.transition(InterviewEvent.START)
                fsm.transition(InterviewEvent.INTRO_COMPLETE)
            assert fsm.transition(InterviewEvent.CANDIDATE_DISCONNECT) == InterviewState.DONE

    def test_is_active(self) -> None:
        fsm = InterviewFSM()
        assert fsm.is_active is True
        fsm.transition(InterviewEvent.START)
        assert fsm.is_active is True
        fsm.transition(InterviewEvent.CANDIDATE_DISCONNECT)
        assert fsm.is_active is False

    def test_reset(self) -> None:
        fsm = InterviewFSM()
        fsm.transition(InterviewEvent.START)
        fsm.reset()
        assert fsm.state == InterviewState.IDLE
