"""Transaction categorization service."""

import re
from typing import Tuple, Optional
from supabase import Client


# Hardcoded merchant-to-category rules (confidence 1.0)
MERCHANT_CATEGORY_RULES = {
    "Swiggy": "Food & Dining",
    "Zomato": "Food & Dining",
    "Uber": "Transport",
    "Ola": "Transport",
    "Amazon": "Shopping",
    "Flipkart": "Shopping",
    "BigBasket": "Groceries",
    "Netflix": "Subscriptions",
    "Spotify": "Subscriptions",
    "Starbucks": "Food & Dining",
    "HP Petrol": "Transport",
    "Indian Oil": "Transport",
    "HDFC ATM": "Utilities",
    "ICICI ATM": "Utilities",
    "SBI ATM": "Utilities",
}

# Regex patterns for categorization (confidence 0.85)
REGEX_CATEGORY_RULES = [
    (r"GROCERY|KIRANA|SUPERMARKET|BIGBASKET", "Groceries"),
    (r"FUEL|PETROL|DIESEL|CNG|PUMP", "Transport"),
    (r"HOSPITAL|MEDICAL|PHARMACY|DOCTOR", "Healthcare"),
    (r"SCHOOL|COLLEGE|UNIVERSITY|EDUCATION|COURSE", "Education"),
    (r"FLIGHT|AIRLINE|HOTEL|BOOKING", "Travel"),
    (r"CINEMA|MOVIE|ENTERTAINMENT|TICKET", "Entertainment"),
    (r"ELECTRICITY|WATER|GAS|PHONE|INTERNET", "Utilities"),
    (r"RESTAURANT|CAFE|FOOD|DINING|QUICK|SERVICE", "Food & Dining"),
    (r"SHOPPING|MALL|STORE|RETAIL|APPAREL", "Shopping"),
]


async def categorize_transaction(
    raw_merchant: str,
    amount: float,
    memo: Optional[str] = None,
    db: Optional[Client] = None,
) -> Tuple[str, float]:
    """
    Categorize a transaction based on merchant and amount.

    Args:
        raw_merchant: Canonical or raw merchant name
        amount: Transaction amount
        memo: Optional transaction memo
        db: Optional Supabase client (for learning records)

    Returns:
        Tuple of (category_name, confidence_score)
    """
    merchant_upper = raw_merchant.upper()

    # Layer 1: Exact merchant rules (confidence 1.0)
    for merchant, category in MERCHANT_CATEGORY_RULES.items():
        if merchant.upper() == merchant_upper:
            return category, 1.0

    # Layer 2: Regex rules (confidence 0.85)
    search_text = f"{raw_merchant} {memo or ''}".upper()
    for pattern, category in REGEX_CATEGORY_RULES:
        if re.search(pattern, search_text):
            return category, 0.85

    # Layer 3: Check learning records if db provided
    if db:
        try:
            response = db.table("learning_records").select("category_id").eq(
                "raw_merchant", raw_merchant
            ).limit(1).execute()
            if response.data and response.data[0]["category_id"]:
                category_id = response.data[0]["category_id"]
                category = db.table("categories").select("name").eq(
                    "id", category_id
                ).limit(1).execute()
                if category.data:
                    return category.data[0]["name"], 1.0
        except Exception:
            pass

    # Default: Other category with low confidence
    return "Other", 0.3


async def get_category_id(
    category_name: str, user_id: str, db: Client
) -> Optional[str]:
    """
    Get category ID by name (system or user-created).

    Args:
        category_name: Category name
        user_id: User UUID
        db: Supabase client

    Returns:
        Category ID or None if not found
    """
    try:
        # Check system categories first
        response = db.table("categories").select("id").eq(
            "name", category_name
        ).eq("user_id", None).limit(1).execute()

        if response.data:
            return response.data[0]["id"]

        # Then check user categories
        response = db.table("categories").select("id").eq(
            "name", category_name
        ).eq("user_id", user_id).limit(1).execute()

        if response.data:
            return response.data[0]["id"]

    except Exception:
        pass

    return None
