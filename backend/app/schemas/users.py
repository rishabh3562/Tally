"""User schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class UserPreferences(BaseModel):
    """User preference settings."""
    default_currency: Optional[str] = "INR"
    theme: Optional[str] = "light"

    class Config:
        extra = "allow"


class UserOut(BaseModel):
    """User response schema."""
    id: str
    email: str
    preferences: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True
