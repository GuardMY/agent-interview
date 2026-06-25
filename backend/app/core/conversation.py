from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.config import settings


class IntentType(str, Enum):
    ANSWER = "answer"
    CLARIFY = "clarify"
    SKIP = "skip"
    CHAT = "chat"
    DISENGAGE = "disengage"


@dataclass
class Message:
    role: str  # "interviewer" | "candidate" | "system"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ConversationManager:
    """Manages sliding-window conversation history and intent detection."""

    def __init__(self, max_window: int | None = None) -> None:
        self._messages: list[Message] = []
        self._max_window = max_window or settings.sliding_window_size

    def add_message(self, role: str, content: str) -> None:
        self._messages.append(Message(role=role, content=content))

    def get_window(self) -> list[Message]:
        """Return the sliding window (most recent N messages)."""
        if len(self._messages) <= self._max_window:
            return list(self._messages)
        return list(self._messages[-self._max_window:])

    def get_full_history(self) -> list[Message]:
        """Return all messages ever recorded."""
        return list(self._messages)

    def format_window_for_llm(self) -> str:
        """Format recent messages for inclusion in a system prompt."""
        lines: list[str] = []
        for msg in self.get_window():
            role_label = "Interviewer" if msg.role == "interviewer" else "Candidate"
            lines.append(f"[{role_label}]: {msg.content}")
        return "\n".join(lines)

    def detect_intent(self, message: str) -> IntentType:
        """
        Fast intent detection using keyword heuristics.
        Falls back to LLM-based detection for ambiguous cases.
        """
        msg_lower = message.strip().lower()

        # Disengage signals
        disengage_keywords = ["end the interview", "stop the interview", "i want to stop", "quit"]
        for kw in disengage_keywords:
            if kw in msg_lower:
                return IntentType.DISENGAGE

        # Skip signals
        skip_keywords = ["skip", "next question", "pass", "move on"]
        if len(msg_lower) < 30:  # Short message, likely a command
            for kw in skip_keywords:
                if kw in msg_lower:
                    return IntentType.SKIP

        # Clarify signals
        clarify_keywords = [
            "can you repeat", "clarify", "rephrase", "don't understand",
            "not sure what you mean", "could you explain", "what do you mean",
        ]
        for kw in clarify_keywords:
            if kw in msg_lower:
                return IntentType.CLARIFY

        # Chat / off-topic signals (very short, non-technical)
        chat_keywords = ["thank you", "thanks", "hello", "hi", "how are you"]
        if len(msg_lower) < 20:
            for kw in chat_keywords:
                if kw in msg_lower:
                    return IntentType.CHAT

        # Default: treat as answer
        return IntentType.ANSWER

    @property
    def last_message(self) -> Message | None:
        return self._messages[-1] if self._messages else None

    @property
    def message_count(self) -> int:
        return len(self._messages)
