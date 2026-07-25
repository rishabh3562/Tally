"""Category schemas."""

from pydantic import BaseModel
from typing import Optional


class CategoryCreate(BaseModel):
    """Create a user-scoped custom category (e.g. 'Rent', 'Loan given')."""
    name: str
    icon: Optional[str] = "🏷️"
