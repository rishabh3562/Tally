"""Transaction categorization service."""

import logging
import re
from typing import Tuple, Optional
from supabase import Client

from app.services import llm_client

logger = logging.getLogger("tally.categorizer")

# Batch size for LLM categorization: how many unique merchants per call.
_LLM_BATCH = 40


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
                    return category.data[0]["name"], 0.95
        except Exception:
            pass

    # Default fallback
    return "Other", 0.5


async def llm_categorize_merchants(
    merchants: list[str],
    valid_categories: list[str],
) -> dict[str, str]:
    """Categorize many unique merchants with the LLM in a few batched calls.

    Rather than one LLM call per transaction (hundreds, slow, costly), we send
    the *unique* merchant strings in chunks of ``_LLM_BATCH`` and ask for a JSON
    ``{merchant: category}`` map. Any merchant the model omits or maps to an
    unknown category is left out (caller keeps its existing category).

    Returns an empty dict if no LLM provider is available.
    """
    if not merchants or not llm_client.is_available():
        return {}

    allowed = set(valid_categories)
    result: dict[str, str] = {}

    for i in range(0, len(merchants), _LLM_BATCH):
        chunk = merchants[i : i + _LLM_BATCH]
        prompt = (
            "You categorize bank/UPI transaction merchants for a personal finance "
            "app. Choose the single best category for each merchant strictly from "
            "this list:\n"
            f"{', '.join(valid_categories)}\n\n"
            "Respond as strict JSON: an object mapping each merchant name exactly "
            'as given to one category from the list. Example: {"Swiggy": "Food & '
            'Dining"}. Merchants:\n'
            f"{chr(10).join('- ' + m for m in chunk)}"
        )
        try:
            data = await llm_client.acomplete_json(prompt, max_tokens=1500)
        except Exception as e:
            logger.warning("[categorizer] LLM batch failed: %s", e)
            continue
        if not isinstance(data, dict):
            continue
        for merchant in chunk:
            cat = data.get(merchant)
            if isinstance(cat, str) and cat in allowed:
                result[merchant] = cat

    logger.info(
        "[categorizer] LLM categorized %d/%d unique merchants",
        len(result), len(merchants),
    )
    return result


async def get_category_id(
    category_name: str,
    user_id: str,
    db: Client,
) -> Optional[str]:
    """Get or create category by name."""
    try:
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

        # Create default category if needed
        insert_resp = db.table("categories").insert({
            "name": category_name,
            "user_id": None,
            "icon": "📌",
        }).execute()

        if insert_resp.data:
            return insert_resp.data[0]["id"]
    except Exception:
        pass

    return None
