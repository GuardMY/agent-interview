from datetime import datetime, timezone

from pydantic import BaseModel, Field


class WSMessage(BaseModel):
    """Envelope for all WebSocket messages."""

    type: str
    payload: dict
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AnswerPayload(BaseModel):
    content: str = Field(..., min_length=1)


class CommandPayload(BaseModel):
    command: str = Field(..., pattern="^(skip|repeat)$")
