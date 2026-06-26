"""Transaction schemas."""

from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class TransactionOut(BaseModel):
    """Schema for transaction response."""
    id: str
    user_id: str
    account_id: str
    date: date
    amount: float
    currency: str
    raw_merchant: Optional[str]
    merchant_id: Optional[str]
    category_id: Optional[str]
    memo: Optional[str]
    is_transfer: bool
    confidence_score: float
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionFilters(BaseModel):
    """Schema for transaction query filters."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_id: Optional[str] = None
    merchant_id: Optional[str] = None
    page: int = 1
    limit: int = 50


class CategoryPatchRequest(BaseModel):
    """Schema for updating transaction category."""
    category_id: str
    merchant_correction: Optional[bool] = False
