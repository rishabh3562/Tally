"""Chat schemas."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Schema for chat request."""
    question: str
    conversation_id: str = None
