"""Merchant normalization service."""

import re
from typing import Optional
from supabase import Client


# Hardcoded merchant rules (merchant name → canonical)
MERCHANT_RULES = {
    "SWIGGY": "Swiggy",
    "ZOMATO": "Zomato",
    "UBER": "Uber",
    "OLA": "Ola",
    "AMAZON": "Amazon",
    "FLIPKART": "Flipkart",
    "BIGBASKET": "BigBasket",
    "NETFLIX": "Netflix",
    "SPOTIFY": "Spotify",
    "STARBUCKS": "Starbucks",
}

# Regex patterns for normalization
REGEX_RULES = [
    (r"HDFC.*ATM", "HDFC ATM"),
    (r"ICICI.*ATM", "ICICI ATM"),
    (r"SBI.*ATM", "SBI ATM"),
    (r"HP\s+PETROL|HPCL", "HP Petrol"),
    (r"INDIAN\s+OIL|IOC", "Indian Oil"),
    (r"IRCTC", "IRCTC"),
    (r"IRAIL", "IRCTC"),
    (r"PAYPAL", "PayPal"),
    (r"GOOGLE\s+PLAY", "Google Play"),
    (r"APP\s+STORE", "Apple App Store"),
]


async def normalize_merchant(
    raw_merchant: str,
    db: Client,
) -> str:
    """
    Normalize a raw merchant string to a canonical name.

    Args:
        raw_merchant: Raw merchant string from statement
        db: Supabase client

    Returns:
        Canonical merchant name or raw string if no match
    """
    if not raw_merchant:
        return "Unknown"

    normalized = raw_merchant.strip().upper()

    # Layer 1: Exact match against hardcoded rules
    if normalized in MERCHANT_RULES:
        return MERCHANT_RULES[normalized]

    # Layer 2: Check merchant_aliases table for known patterns
    try:
        response = db.table("merchant_aliases").select("merchant_id").eq(
            "alias", normalized
        ).limit(1).execute()
        if response.data:
            # Fetch the merchant name
            merchant_id = response.data[0]["merchant_id"]
            merchant = db.table("merchants").select("name").eq(
                "id", merchant_id
            ).limit(1).execute()
            if merchant.data:
                return merchant.data[0]["name"]
    except Exception:
        pass

    # Layer 3: Regex pattern matching
    for pattern, canonical in REGEX_RULES:
        if re.search(pattern, normalized, re.IGNORECASE):
            return canonical

    # No match found
    return raw_merchant
