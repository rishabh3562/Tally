"""AI (re)categorization endpoint.

Upgrades transactions the rule engine couldn't confidently place (category
"Other" / uncategorized) using a few batched LLM calls over the *unique*
merchants, then caches each decision to ``learning_records`` so subsequent
ingestion categorizes the same merchant for free (no LLM call).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.auth import get_current_user
from app.core.database import get_supabase
from app.services import llm_client
from app.services.categorizer import llm_categorize_merchants

logger = logging.getLogger("tally.categorizer")

router = APIRouter(prefix="/api", tags=["categorization"])

# Bound the work (and cost) per invocation.
_MAX_UNIQUE_MERCHANTS = 300


@router.post("/recategorize")
async def recategorize(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Re-categorize the user's 'Other'/uncategorized transactions with the LLM."""
    if not llm_client.is_available():
        return {
            "status": "skipped",
            "reason": "No LLM provider configured. Set GEMINI_API_KEYS or "
                      "OPENROUTER_API_KEY to enable AI categorization.",
            "updated_transactions": 0,
        }

    try:
        # Valid category names + a name->id map (system categories).
        cats = db.table("categories").select("id,name").is_(
            "user_id", "null"
        ).execute().data or []
        name_to_id = {c["name"]: c["id"] for c in cats}
        valid_names = [c["name"] for c in cats if c["name"] != "Other"]

        # Transactions needing help: category "Other" or no category at all.
        rows = db.table("transactions").select(
            "raw_merchant,category_id,categories(name)"
        ).eq("user_id", user_id).execute().data or []

        needy = set()
        for r in rows:
            cat = r.get("categories")
            cat_name = cat.get("name") if isinstance(cat, dict) else None
            if (cat_name in (None, "Other")) and r.get("raw_merchant"):
                needy.add(r["raw_merchant"])

        unique_merchants = list(needy)[:_MAX_UNIQUE_MERCHANTS]
        if not unique_merchants:
            return {
                "status": "done",
                "candidates": 0,
                "categorized_merchants": 0,
                "updated_transactions": 0,
                "message": "Nothing to recategorize — no 'Other'/uncategorized transactions.",
            }

        mapping = await llm_categorize_merchants(unique_merchants, valid_names)

        updated = 0
        for merchant, category in mapping.items():
            category_id = name_to_id.get(category)
            if not category_id:
                continue
            # Update all of this user's transactions for that merchant.
            upd = db.table("transactions").update(
                {"category_id": category_id, "confidence_score": 0.9}
            ).eq("user_id", user_id).eq("raw_merchant", merchant).execute()
            updated += len(upd.data or [])

            # Cache so future ingestion (learning_records layer) reuses it.
            try:
                db.table("learning_records").upsert(
                    {"user_id": user_id, "raw_merchant": merchant, "category_id": category_id},
                    on_conflict="user_id,raw_merchant",
                ).execute()
            except Exception as e:
                logger.warning("[categorizer] learning_record upsert failed for %s: %s", merchant, e)

        return {
            "status": "done",
            "candidates": len(unique_merchants),
            "categorized_merchants": len(mapping),
            "updated_transactions": updated,
            "message": f"AI categorized {len(mapping)} merchants, updated {updated} transactions.",
        }
    except Exception as e:
        logger.exception("recategorize failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
