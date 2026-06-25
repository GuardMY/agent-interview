import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class WSMessage(BaseModel):
    """Envelope for all WebSocket messages."""

    type: str
    payload: dict
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AnswerPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def sanitize(cls, v: str) -> str:
        return re.sub(r"<[^>]*>", "", v).strip()


class CommandPayload(BaseModel):
    command: str = Field(..., pattern="^(skip|repeat)$")
