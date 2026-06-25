from app.core.conversation import ConversationManager, IntentType


class TestConversationManager:
    def test_add_message(self) -> None:
        cm = ConversationManager(max_window=10)
        cm.add_message("interviewer", "Tell me about yourself.")
        assert cm.message_count == 1
        assert cm.last_message.role == "interviewer"

    def test_sliding_window_truncation(self) -> None:
        cm = ConversationManager(max_window=5)
        for i in range(10):
            cm.add_message("interviewer" if i % 2 == 0 else "candidate", f"Message {i}")
        window = cm.get_window()
        assert len(window) == 5
        assert window[0].content == "Message 5"
        assert window[-1].content == "Message 9"

    def test_get_full_history(self) -> None:
        cm = ConversationManager(max_window=5)
        for i in range(10):
            cm.add_message("candidate", f"Msg {i}")
        full = cm.get_full_history()
        assert len(full) == 10

    def test_window_smaller_than_history(self) -> None:
        cm = ConversationManager(max_window=20)
        for i in range(3):
            cm.add_message("candidate", f"Msg {i}")
        assert len(cm.get_window()) == 3

    def test_format_window_for_llm(self) -> None:
        cm = ConversationManager(max_window=5)
        cm.add_message("interviewer", "Question?")
        cm.add_message("candidate", "Answer!")
        formatted = cm.format_window_for_llm()
        assert "[Interviewer]: Question?" in formatted
        assert "[Candidate]: Answer!" in formatted

    def test_intent_skip_keyword(self) -> None:
        cm = ConversationManager()
        assert cm.detect_intent("skip this question please") == IntentType.SKIP
        assert cm.detect_intent("next question") == IntentType.SKIP
        assert cm.detect_intent("pass") == IntentType.SKIP

    def test_intent_clarify_keyword(self) -> None:
        cm = ConversationManager()
        assert cm.detect_intent("Can you rephrase that?") == IntentType.CLARIFY
        assert cm.detect_intent("I don't understand what you mean") == IntentType.CLARIFY

    def test_intent_disengage_keyword(self) -> None:
        cm = ConversationManager()
        assert cm.detect_intent("I want to stop the interview") == IntentType.DISENGAGE
        assert cm.detect_intent("end the interview please") == IntentType.DISENGAGE

    def test_intent_chat_keyword(self) -> None:
        cm = ConversationManager()
        assert cm.detect_intent("thank you") == IntentType.CHAT
        assert cm.detect_intent("hello") == IntentType.CHAT

    def test_intent_defaults_to_answer(self) -> None:
        cm = ConversationManager()
        result = cm.detect_intent("REST is an architectural style for designing networked applications")
        assert result == IntentType.ANSWER
