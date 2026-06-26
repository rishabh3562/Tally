"""Account schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AccountCreate(BaseModel):
    """Schema for creating an account."""
    name: str
    type: str  # 'Bank' | 'CreditCard' | 'UPI' | 'Investment'
    bank_code: Optional[str] = None


class AccountOut(BaseModel):
    """Schema for account response."""
    id: str
    user_id: str
    name: str
    type: str
    bank_code: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
