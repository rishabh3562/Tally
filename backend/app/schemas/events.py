"""Event schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class EventCreate(BaseModel):
    """Schema for creating an event."""
    name: str
    transaction_ids: list[str]
    metadata: Optional[Dict[str, Any]] = None


class EventOut(BaseModel):
    """Schema for event response."""
    id: str
    user_id: str
    name: str
    metadata: Optional[Dict[str, Any]]
    summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
