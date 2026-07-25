"""Event schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class EventCreate(BaseModel):
    """Schema for creating an event (a 'case study' for a big/thematic spend)."""
    name: str
    transaction_ids: list[str]
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EventUpdate(BaseModel):
    """Edit an event: rename, re-describe, and/or add/remove member transactions.

    A wedding's 'bits and pieces' are found over time, so events must be editable
    after creation. All fields optional — only what's provided is applied.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    add_transaction_ids: Optional[list[str]] = None
    remove_transaction_ids: Optional[list[str]] = None


class EventOut(BaseModel):
    """Schema for event response."""
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "INR"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
