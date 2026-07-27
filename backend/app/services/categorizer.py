"""Transaction categorization service."""

import logging
import re
from typing import Tuple, Optional
from supabase import Client

from app.services import llm_client
from app.services.merchant import canonical_merchant

logger = logging.getLogger("tally.categorizer")

# Batch size for LLM categorization: how many unique merchants per call.
_LLM_BATCH = 40


# Canonical brand → category. One line per brand in `merchant._CANONICAL_TOKENS`,
# which already collapses every variant string a statement can carry
# ("AVENUESUPERMARTSLTD" and "DMART" both → "DMart"), so this covers all of those
# variants without repeating their tokens here. Found by measuring the real
# uncategorised pile: DMart was Rs 3,138 of "Other" purely because the token list
# below has no entry that matches "AVENUESUPERMARTSLTD".
BRAND_CATEGORY = {
    "Swiggy": "Food & Dining",
    "Zomato": "Food & Dining",
    "HungerBox": "Food & Dining",
    "Amazon": "Shopping",
    "Flipkart": "Shopping",
    "DMart": "Groceries",
    "BigBasket": "Groceries",
    "Blinkit": "Groceries",
    "Zepto": "Groceries",
    "Netflix": "Subscriptions",
    "Spotify": "Subscriptions",
    "Hotstar": "Subscriptions",
    "Hostinger": "Subscriptions",
    "RedBus": "Travel",
    "KheloMore": "Entertainment",
}

# Sub-brands whose category differs from the parent brand's, checked first.
SUB_BRAND_CATEGORY = {
    "INSTAMART": "Groceries",     # Swiggy Instamart is a grocery run, not a meal
}


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
    # INDIANOIL: real statements spell it out ("INDIANOILCORPORATIONLTDLPGCRM…"),
    # which the IOCL abbreviation never matches.
    (r"FUEL|PETROL|DIESEL|\bCNG\b|\bPUMP\b|PETROLEUM|HPCL|IOCL|INDIANOIL|BHARATPETRO", "Transport"),
    # SUPERMART without a word boundary: "AVENUESUPERMARTSLTD" has none.
    (r"GROCERY|KIRANA|SUPERMARKET|SUPERMART|\bMART\b|PROVISION", "Groceries"),
    (r"HOSPITAL|MEDIC|PHARMAC|CHEMIST|CLINIC|DIAGNOSTIC|\bDR\b|DOCTOR|HEALTH|DENTAL", "Healthcare"),
    (r"SCHOOL|COLLEGE|UNIVERSITY|EDUCATION|COURSE|TUITION|ACADEMY|CLASSES|COACHING", "Education"),
    (r"FLIGHT|AIRLINE|INDIGO|HOTEL|RESORT|BOOKING|\bTRIP\b|TRAVEL|AIRWAYS", "Travel"),
    (r"CINEMA|MOVIE|\bPVR\b|INOX|BOOKMYSHOW|ENTERTAIN|GAMING|SPORT|\bKHELO\b|MATCHPOINT|\bTURF\b", "Entertainment"),
    (r"ELECTRICITY|WATERBILL|GASBILL|RECHARGE|\bJIO\b|AIRTEL|\bVI\b|BROADBAND|\bDTH\b|\bATM\b|BILLPAY", "Utilities"),
    (r"RESTAURANT|CAFE|COFFEE|\bFOOD\b|DINING|SNACK|BAKERY|SWEET|MITHAI|\bTEA\b|CHAAP|DHABA|BIRYANI|PIZZA|BURGER|CANTEEN|KITCHEN", "Food & Dining"),
    # EKART is Flipkart's courier arm — it only ever shows up on a delivery.
    (r"SHOPPING|\bMALL\b|\bSTORE\b|RETAIL|APPAREL|FASHION|LIFESTYLE|\bTRENDS\b|GARMENT|FOOTWEAR|\bEKART\b", "Shopping"),
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

    merchant_key = re.sub(r"[^A-Z0-9]", "", raw_merchant.upper())

    # Layer 0a: a sub-brand that belongs to a DIFFERENT category than its parent
    # beats the brand map — Swiggy Instamart is groceries, not a restaurant meal.
    for token, category in SUB_BRAND_CATEGORY.items():
        if token in merchant_key:
            return category, 1.0

    # Layer 0b: the shared brand canonicalizer (confidence 1.0). Reusing it means
    # every merchant-string variant a brand appears under is already handled.
    brand = canonical_merchant(raw_merchant)
    if brand in BRAND_CATEGORY:
        return BRAND_CATEGORY[brand], 1.0

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


def _merchant_key(raw: str) -> str:
    """Punctuation- and case-insensitive form, the same normalisation
    `rule_category` uses. `AmazonPay` and `Amazon Pay` are one key."""
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


# A correction has to be at least this specific before it's applied to merchant
# strings the user never saw. `chat_tools` uses 4 for an action the user confirms
# on the spot; auto-application to future imports deserves more.
_MIN_OVERRIDE_KEY = 6


def load_user_overrides(db: Client, user_id: Optional[str]) -> dict[str, str]:
    """{normalised_merchant_key: category_id} for what THIS user decided by hand.

    One query per import/request. Fails closed: with no `user_id` we return
    nothing rather than reading another user's corrections — the read used to have
    no user filter at all, so with two users A's private label drove B's imports.
    """
    if not user_id:
        logger.warning(
            "load_user_overrides called without user_id — skipping (fail closed)"
        )
        return {}
    try:
        rows = (
            db.table("learning_records")
            .select("raw_merchant,category_id")
            .eq("user_id", user_id)
            .eq("source", "user")
            .execute()
            .data
            or []
        )
    except Exception as e:  # pragma: no cover - overrides are best-effort
        logger.warning("could not load user overrides: %s", e)
        return {}
    return {
        _merchant_key(r["raw_merchant"]): r["category_id"]
        for r in rows
        if r.get("raw_merchant") and r.get("category_id")
    }


def match_override(raw_merchant: str, overrides: dict[str, str]) -> Optional[str]:
    """The category_id the user chose for this merchant, or None.

    Exact key first, then the LONGEST matching substring key — real data needs
    both: a correction saved as `SWIGGYINSTAMART` must cover
    `SWIGGYINSTAMARTPRIVATELIMITED`, while `AmazonPayGroceries` must beat the
    shorter `AmazonPay` that also matches it.
    """
    if not raw_merchant or not overrides:
        return None
    key = _merchant_key(raw_merchant)
    if key in overrides:
        return overrides[key]
    best: Optional[str] = None
    best_len = 0
    for candidate, category_id in overrides.items():
        if len(candidate) < _MIN_OVERRIDE_KEY or len(candidate) <= best_len:
            continue
        if candidate in key:
            best, best_len = category_id, len(candidate)
    return best


def resolve_category(
    raw_merchant: str,
    memo: Optional[str],
    overrides: dict[str, str],
) -> Tuple[Optional[str], Optional[str], float]:
    """`(category_id, category_name, confidence)` — the full deterministic decision.

    Layer 0 is what the user decided, and it beats the rules: they had already
    corrected `SWIGGYINSTAMART` to Food & Dining, `KHELOMORE…` to Health and
    `REDBUS` to Transport, and the rule engine was quietly contradicting all three
    on every new import. Returns an **id** for an override (the user's own
    categories don't exist in the system-only name lookups) and a **name** for a
    rule hit.
    """
    override_id = match_override(raw_merchant, overrides)
    if override_id:
        return override_id, None, 1.0
    hit = rule_category(raw_merchant, memo)
    if hit:
        return None, hit[0], hit[1]
    return None, None, 0.0


async def categorize_transaction(
    raw_merchant: str,
    amount: float,
    memo: Optional[str] = None,
    db: Optional[Client] = None,
    user_id: Optional[str] = None,
) -> Tuple[str, float]:
    """Categorize one transaction, by NAME (see `resolve_category` for ids).

    Args:
        raw_merchant: Canonical or raw merchant name
        amount: Transaction amount
        memo: Optional transaction memo
        db: Optional Supabase client (for learning records)
        user_id: REQUIRED alongside `db` — learning_records are per-user. Without
            it the learning lookup is skipped entirely rather than reading every
            user's corrections.

    Returns:
        Tuple of (category_name, confidence_score)

    Prefer `load_user_overrides` + `resolve_category` for bulk work: this does a
    per-call query, and it can only return a category NAME, which system-only name
    lookups cannot resolve for a user's own category.
    """
    # Layer 0: what the user decided, ahead of the rules.
    if db and user_id:
        overrides = load_user_overrides(db, user_id)
        category_id = match_override(raw_merchant, overrides)
        if category_id:
            try:
                cat = db.table("categories").select("name").eq(
                    "id", category_id
                ).limit(1).execute()
                if cat.data:
                    return cat.data[0]["name"], 1.0
            except Exception as e:  # pragma: no cover - fall through to rules
                logger.warning("override category lookup failed: %s", e)
    elif db and not user_id:
        logger.warning(
            "categorize_transaction got a db but no user_id — learning records "
            "skipped (they are per-user; an unscoped read would apply one user's "
            "corrections to another's transactions)"
        )

    # Layers 1 & 2: deterministic rules (brand tokens + regex).
    hit = rule_category(raw_merchant, memo)
    if hit:
        return hit

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
