#!/usr/bin/env python3
"""
Seed script to initialize default categories and merchants in Supabase.
Run after tables are created but before first user interaction.
"""

import sys
import os
from supabase import create_client

# Get settings from environment
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("Error: SUPABASE_URL and SUPABASE_KEY environment variables required")
    sys.exit(1)

db = create_client(supabase_url, supabase_key)

# Default categories for Personal Finance OS
DEFAULT_CATEGORIES = [
    {"name": "Food & Dining", "icon": "🍽️", "parent_id": None},
    {"name": "Transport", "icon": "🚗", "parent_id": None},
    {"name": "Shopping", "icon": "🛍️", "parent_id": None},
    {"name": "Groceries", "icon": "🛒", "parent_id": None},
    {"name": "Subscriptions", "icon": "📱", "parent_id": None},
    {"name": "Healthcare", "icon": "⚕️", "parent_id": None},
    {"name": "Education", "icon": "📚", "parent_id": None},
    {"name": "Travel", "icon": "✈️", "parent_id": None},
    {"name": "Entertainment", "icon": "🎬", "parent_id": None},
    {"name": "Utilities", "icon": "💡", "parent_id": None},
    {"name": "Other", "icon": "📌", "parent_id": None},
]

# Default merchants
DEFAULT_MERCHANTS = [
    {"name": "Swiggy", "domain": "swiggy.com"},
    {"name": "Zomato", "domain": "zomato.com"},
    {"name": "Uber", "domain": "uber.com"},
    {"name": "Ola", "domain": "olaelectric.com"},
    {"name": "Amazon", "domain": "amazon.in"},
    {"name": "Flipkart", "domain": "flipkart.com"},
    {"name": "BigBasket", "domain": "bigbasket.com"},
    {"name": "Netflix", "domain": "netflix.com"},
    {"name": "Spotify", "domain": "spotify.com"},
    {"name": "Starbucks", "domain": "starbucks.co.in"},
    {"name": "HP Petrol", "domain": "hpcl.co.in"},
    {"name": "Indian Oil", "domain": "iocl.com"},
    {"name": "HDFC ATM", "domain": "hdfcbank.com"},
    {"name": "ICICI ATM", "domain": "icicibank.com"},
    {"name": "SBI ATM", "domain": "sbi.co.in"},
    {"name": "PayPal", "domain": "paypal.com"},
    {"name": "Google Play", "domain": "play.google.com"},
    {"name": "Apple App Store", "domain": "apple.com"},
    {"name": "IRCTC", "domain": "irctc.co.in"},
    {"name": "BookMyShow", "domain": "bookmyshow.com"},
]

# Default merchant aliases
DEFAULT_ALIASES = [
    {"merchant_name": "Swiggy", "aliases": ["SWIGGY", "SWIGGY INSTAMART"], "match_type": "exact"},
    {"merchant_name": "Zomato", "aliases": ["ZOMATO", "ZOMATO.COM"], "match_type": "exact"},
    {"merchant_name": "Uber", "aliases": ["UBER", "UBER EATS"], "match_type": "exact"},
    {"merchant_name": "Ola", "aliases": ["OLA", "OLA CABS"], "match_type": "exact"},
    {"merchant_name": "Amazon", "aliases": ["AMAZON", "AMAZON.IN"], "match_type": "exact"},
    {"merchant_name": "Flipkart", "aliases": ["FLIPKART", "FLIPKART.COM"], "match_type": "exact"},
    {"merchant_name": "BigBasket", "aliases": ["BIGBASKET", "BB NOW"], "match_type": "exact"},
    {"merchant_name": "Netflix", "aliases": ["NETFLIX", "NETFLIX SUBSCRIPTION"], "match_type": "exact"},
    {"merchant_name": "Spotify", "aliases": ["SPOTIFY", "SPOTIFY AB"], "match_type": "exact"},
    {"merchant_name": "Starbucks", "aliases": ["STARBUCKS", "SBUX"], "match_type": "exact"},
    {"merchant_name": "HP Petrol", "aliases": ["HPCL", "HP PETROL", "HP PUMP"], "match_type": "prefix"},
    {"merchant_name": "Indian Oil", "aliases": ["IOC", "INDIAN OIL"], "match_type": "prefix"},
    {"merchant_name": "HDFC ATM", "aliases": ["HDFC ATM", "HDFC BANK ATM"], "match_type": "prefix"},
    {"merchant_name": "ICICI ATM", "aliases": ["ICICI ATM", "ICICI BANK ATM"], "match_type": "prefix"},
    {"merchant_name": "SBI ATM", "aliases": ["SBI ATM", "STATE BANK ATM"], "match_type": "prefix"},
]


def seed_categories():
    """Seed default categories."""
    print("Seeding categories...")
    try:
        # Check if categories already exist
        existing = db.table("categories").select("name").eq("user_id", None).execute()
        existing_names = {cat["name"] for cat in existing.data or []}

        inserted = 0
        for cat in DEFAULT_CATEGORIES:
            if cat["name"] not in existing_names:
                db.table("categories").insert({
                    "name": cat["name"],
                    "icon": cat.get("icon", "📌"),
                    "user_id": None,  # System category
                    "parent_id": cat.get("parent_id"),
                }).execute()
                inserted += 1

        print(f"✓ Seeded {inserted} categories")
    except Exception as e:
        print(f"✗ Error seeding categories: {e}")


def seed_merchants():
    """Seed default merchants."""
    print("Seeding merchants...")
    try:
        # Check if merchants already exist
        existing = db.table("merchants").select("name").execute()
        existing_names = {merchant["name"] for merchant in existing.data or []}

        inserted = 0
        for merchant in DEFAULT_MERCHANTS:
            if merchant["name"] not in existing_names:
                db.table("merchants").insert({
                    "name": merchant["name"],
                    "domain": merchant.get("domain"),
                    "logo": None,
                }).execute()
                inserted += 1

        print(f"✓ Seeded {inserted} merchants")
    except Exception as e:
        print(f"✗ Error seeding merchants: {e}")


def seed_aliases():
    """Seed merchant aliases."""
    print("Seeding merchant aliases...")
    try:
        # Fetch all merchants to get IDs
        merchants_resp = db.table("merchants").select("id, name").execute()
        merchants_by_name = {m["name"]: m["id"] for m in (merchants_resp.data or [])}

        # Check existing aliases
        existing = db.table("merchant_aliases").select("alias").execute()
        existing_aliases = {alias["alias"] for alias in existing.data or []}

        inserted = 0
        for alias_group in DEFAULT_ALIASES:
            merchant_name = alias_group["merchant_name"]
            if merchant_name not in merchants_by_name:
                print(f"  - Skipping aliases for unknown merchant: {merchant_name}")
                continue

            merchant_id = merchants_by_name[merchant_name]
            for alias in alias_group["aliases"]:
                if alias not in existing_aliases:
                    db.table("merchant_aliases").insert({
                        "merchant_id": merchant_id,
                        "alias": alias,
                        "match_type": alias_group.get("match_type", "exact"),
                    }).execute()
                    inserted += 1

        print(f"✓ Seeded {inserted} merchant aliases")
    except Exception as e:
        print(f"✗ Error seeding aliases: {e}")


def main():
    """Run all seed functions."""
    print("=" * 50)
    print("Personal Finance OS - Database Seeding")
    print("=" * 50)

    try:
        seed_categories()
        seed_merchants()
        seed_aliases()
        print("\n✓ Seeding completed successfully!")
    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
