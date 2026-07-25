"""Category schemas."""

from pydantic import BaseModel
from typing import Optional


class CategoryCreate(BaseModel):
    """Create a user-scoped custom category (e.g. 'Rent', 'Loan given').

    ``parent_id`` makes it a sub-category (Food → Swiggy → Pizza) — the schema's
    ``categories.parent_id`` self-reference. Omit for a top-level category.
    """
    name: str
    icon: Optional[str] = "🏷️"
    parent_id: Optional[str] = None
