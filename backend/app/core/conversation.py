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
        Fast intent detection using bilingual keyword heuristics.
        Falls back to LLM-based detection for ambiguous cases.
        """
        msg_lower = message.strip().lower()

        # Disengage signals (EN + ZH)
        disengage_keywords = [
            "end the interview", "stop the interview", "i want to stop", "quit",
            "结束面试", "停止面试", "不想继续", "退出", "不面试了",
        ]
        for kw in disengage_keywords:
            if kw in msg_lower:
                return IntentType.DISENGAGE

        # Skip signals (EN + ZH)
        skip_keywords = [
            "skip", "next question", "pass", "move on",
            "跳过", "下一题", "下一道", "换一题", "过",
        ]
        if len(message.strip()) < 30:  # Short message, likely a command
            for kw in skip_keywords:
                if kw in msg_lower:
                    return IntentType.SKIP

        # Clarify signals (EN + ZH)
        clarify_keywords = [
            "can you repeat", "clarify", "rephrase", "don't understand",
            "not sure what you mean", "could you explain", "what do you mean",
            "重复一遍", "再说一次", "没听清", "听不懂", "不明白",
            "什么意思", "解释一下", "没理解", "再说一遍",
        ]
        for kw in clarify_keywords:
            if kw in msg_lower:
                return IntentType.CLARIFY

        # Chat / off-topic signals (very short, non-technical) (EN + ZH)
        chat_keywords = [
            "thank you", "thanks", "hello", "hi", "how are you",
            "谢谢", "感谢", "你好", "您好", "嗨",
        ]
        if len(message.strip()) < 20:
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
