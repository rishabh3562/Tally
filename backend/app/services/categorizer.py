"""Transaction categorization service."""

import logging
import re
from typing import Tuple, Optional
from supabase import Client

from app.services import llm_client

logger = logging.getLogger("tally.categorizer")

# Batch size for LLM categorization: how many unique merchants per call.
_LLM_BATCH = 40


# Distinctive brand tokens → category, matched as a SUBSTRING of the uppercased
# merchant (confidence 1.0). Raw statement strings vary a lot ("AmazonIndia",
# "AmazonPay", "BundlTechnologiespvtLtd"), so exact match misses almost
# everything — substring on a distinctive token (>=5 chars) is both robust and
# low false-positive. Short/ambiguous tokens (OLA, UBER, KFC, OYO) live in the
# regex layer with word boundaries instead.
MERCHANT_CATEGORY_RULES = {
    # Shopping
    "AMAZON": "Shopping",
    "FLIPKART": "Shopping",
    "MYNTRA": "Shopping",
    "MEESHO": "Shopping",
    "SNAPDEAL": "Shopping",
    "RELIANCEDIGITAL": "Shopping",
    # Food & Dining
    "SWIGGY": "Food & Dining",
    "BUNDL": "Food & Dining",          # Bundl Technologies = Swiggy
    "ZOMATO": "Food & Dining",
    "HUNGERBOX": "Food & Dining",
    "STARBUCKS": "Food & Dining",
    "DOMINO": "Food & Dining",
    "MCDONALD": "Food & Dining",
    "FAASOS": "Food & Dining",
    "BEHROUZ": "Food & Dining",
    # Groceries / quick-commerce
    "BIGBASKET": "Groceries",
    "BLINKIT": "Groceries",
    "ZEPTO": "Groceries",
    "INSTAMART": "Groceries",
    "JIOMART": "Groceries",
    "RELIANCEFRESH": "Groceries",
    # Subscriptions
    "NETFLIX": "Subscriptions",
    "SPOTIFY": "Subscriptions",
    "HOTSTAR": "Subscriptions",
    "YOUTUBE": "Subscriptions",
    "PRIMEVIDEO": "Subscriptions",
    # Travel
    "IRCTC": "Travel",
    "MAKEMYTRIP": "Travel",
    "GOIBIBO": "Travel",
    "REDBUS": "Travel",
    "CLEARTRIP": "Travel",
    # Transport
    "RAPIDO": "Transport",
    "OLACABS": "Transport",
    "PARIVAHAN": "Transport",          # state transport (e.g. PMPML)
    "MAHAMANDAL": "Transport",
}

# Regex patterns for categorization (confidence 0.85). Tuned for Indian UPI /
# bank merchant strings; word boundaries (\b) keep short tokens from matching
# inside unrelated words (names, ids).
REGEX_CATEGORY_RULES = [
    (r"\bOLA\b|\bUBER\b|\bRAPIDO\b|PARIVAHAN|MAHAMANDAL|\bMETRO\b|\bBUS\b|\bCAB\b|TRANSPORT", "Transport"),
    (r"FUEL|PETROL|DIESEL|\bCNG\b|\bPUMP\b|PETROLEUM|HPCL|IOCL|BHARATPETRO", "Transport"),
    (r"GROCERY|KIRANA|SUPERMARKET|\bMART\b|PROVISION", "Groceries"),
    (r"HOSPITAL|MEDIC|PHARMAC|CHEMIST|CLINIC|DIAGNOSTIC|\bDR\b|DOCTOR|HEALTH|DENTAL", "Healthcare"),
    (r"SCHOOL|COLLEGE|UNIVERSITY|EDUCATION|COURSE|TUITION|ACADEMY|CLASSES|COACHING", "Education"),
    (r"FLIGHT|AIRLINE|INDIGO|HOTEL|RESORT|BOOKING|\bTRIP\b|TRAVEL|AIRWAYS", "Travel"),
    (r"CINEMA|MOVIE|\bPVR\b|INOX|BOOKMYSHOW|ENTERTAIN|GAMING|SPORT|\bKHELO\b|MATCHPOINT|\bTURF\b", "Entertainment"),
    (r"ELECTRICITY|WATERBILL|GASBILL|RECHARGE|\bJIO\b|AIRTEL|\bVI\b|BROADBAND|\bDTH\b|\bATM\b|BILLPAY", "Utilities"),
    (r"RESTAURANT|CAFE|COFFEE|\bFOOD\b|DINING|SNACK|BAKERY|SWEET|MITHAI|\bTEA\b|CHAAP|DHABA|BIRYANI|PIZZA|BURGER|CANTEEN|KITCHEN", "Food & Dining"),
    (r"SHOPPING|\bMALL\b|\bSTORE\b|RETAIL|APPAREL|FASHION|LIFESTYLE|\bTRENDS\b|GARMENT|FOOTWEAR", "Shopping"),
]


def rule_category(
    raw_merchant: str, memo: Optional[str] = None
) -> Optional[Tuple[str, float]]:
    """Deterministic category from brand tokens + regex — NO DB, NO LLM.

    Returns ``(category, confidence)`` or ``None`` when nothing matched. Kept
    pure so it can be reused for a fast bulk backfill (no per-merchant DB round
    trips) as well as inside the full ``categorize_transaction`` pipeline.
    """
    if not raw_merchant:
        return None

    merchant_upper = raw_merchant.upper()

    # Layer 1: distinctive brand tokens as a substring (confidence 1.0).
    for token, category in MERCHANT_CATEGORY_RULES.items():
        if token in merchant_upper:
            return category, 1.0

    # Layer 2: Regex rules on merchant + memo (confidence 0.85).
    search_text = f"{raw_merchant} {memo or ''}".upper()
    for pattern, category in REGEX_CATEGORY_RULES:
        if re.search(pattern, search_text):
            return category, 0.85

    return None


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
    # Layers 1 & 2: deterministic rules (brand tokens + regex).
    hit = rule_category(raw_merchant, memo)
    if hit:
        return hit

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
