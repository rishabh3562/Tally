"""AI (re)categorization endpoint.

Upgrades transactions the rule engine couldn't confidently place (category
"Other" / uncategorized) using a few batched LLM calls over the *unique*
merchants, then caches each decision to ``learning_records`` so subsequent
ingestion categorizes the same merchant for free (no LLM call).
"""

import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.auth import get_current_user
from app.core.database import get_supabase
from app.schemas.categories import CategoryCreate
from app.services import llm_client
from app.services.categorizer import llm_categorize_merchants, rule_category

logger = logging.getLogger("tally.categorizer")

router = APIRouter(prefix="/api", tags=["categorization"])


def _split_leading_emoji(name: str) -> tuple[str | None, str]:
    """If a name starts with an emoji ('🏠 Rent'), split it off as the icon so the
    UI doesn't show a double icon. Returns (emoji_or_None, cleaned_name)."""
    s = name.strip()
    m = re.match(r"^(\S+)\s+(\S.*)$", s)
    if m and any(ord(ch) >= 0x2190 for ch in m.group(1)):  # symbols/emoji range
        return m.group(1), m.group(2).strip()
    return None, s

# Bound the work (and cost) per invocation.
_MAX_UNIQUE_MERCHANTS = 300


@router.get("/categories")
async def list_categories(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """List selectable categories (id + name + icon) for category pickers.

    Returns the **system** categories (``user_id IS NULL``) **plus the caller's
    own custom ones** — so a picker can send a real ``category_id`` to
    ``PATCH /transactions/{id}/category`` or ``POST /transactions/assign-merchant``.
    """
    try:
        cats = db.table("categories").select("id,name,icon,user_id,parent_id").or_(
            f"user_id.is.null,user_id.eq.{user_id}"
        ).order("name").execute().data or []
        return {"data": cats}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Create a user-scoped custom category (e.g. 'Rent', 'Loan given').

    Idempotent by name: if a system or user category with the same name (case-
    insensitive) already exists it is returned instead of creating a duplicate,
    so the picker's "create new" action is safe to call optimistically.
    """
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name is required.",
        )
    # If the user typed an emoji into the name ("🏠 Rent"), use it as the icon so
    # the UI doesn't render a double icon.
    emoji, cleaned = _split_leading_emoji(name)
    icon = body.icon
    if emoji and (not icon or icon == "🏷️"):
        icon, name = emoji, cleaned
    parent_id = (body.parent_id or None)
    try:
        # A parent, if given, must be a category visible to this user.
        if parent_id:
            parent = db.table("categories").select("id").or_(
                f"user_id.is.null,user_id.eq.{user_id}"
            ).eq("id", parent_id).limit(1).execute().data
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent category not found.",
                )

        # Reuse an existing visible category with the same name. Names are kept
        # GLOBALLY UNIQUE (not per-parent) because name->id lookups elsewhere
        # (triage, recategorize, chat categorize_merchant) key on name — allowing
        # duplicate names there would silently resolve to an arbitrary one.
        existing = db.table("categories").select("id,name,icon,user_id,parent_id").or_(
            f"user_id.is.null,user_id.eq.{user_id}"
        ).ilike("name", name).execute().data or []
        if existing:
            return {"data": existing[0], "created": False}

        row = db.table("categories").insert({
            "name": name,
            "icon": icon or "🏷️",
            "user_id": user_id,
            "parent_id": parent_id,
        }).execute().data
        return {"data": (row or [{}])[0], "created": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/recategorize")
async def recategorize(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Re-categorize the user's 'Other'/uncategorized transactions.

    Two passes over the *unique* needy merchants:
      1. **Deterministic** (always, no API key needed): brand tokens + regex via
         ``rule_category``. Reclaims obvious merchants (Amazon, Swiggy, chemists,
         transport, …) instantly.
      2. **LLM** (only if a provider is configured): whatever pass 1 couldn't
         place — the long tail (people's names, small vendors).
    Both passes cache decisions to ``learning_records`` so future ingestion of
    the same merchant is categorized for free.
    """
    try:
        # Valid category names + a name->id map (system categories).
        cats = db.table("categories").select("id,name").is_(
            "user_id", "null"
        ).execute().data or []
        name_to_id = {c["name"]: c["id"] for c in cats}
        valid_names = [c["name"] for c in cats if c["name"] != "Other"]

        # Transactions needing help: category "Other" or no category at all.
        # Keep a representative memo per merchant for the regex layer.
        rows = db.table("transactions").select(
            "raw_merchant,memo,category_id,categories(name)"
        ).eq("user_id", user_id).execute().data or []

        needy: dict[str, str | None] = {}
        for r in rows:
            cat = r.get("categories")
            if isinstance(cat, list):  # tolerate list-shaped embed
                cat = cat[0] if cat else None
            cat_name = cat.get("name") if isinstance(cat, dict) else None
            merchant = r.get("raw_merchant")
            if (cat_name in (None, "Other")) and merchant:
                needy.setdefault(merchant, r.get("memo"))

        if not needy:
            return {
                "status": "done",
                "candidates": 0,
                "updated_transactions": 0,
                "message": "Nothing to recategorize — no 'Other'/uncategorized transactions.",
            }

        def _apply(merchant: str, category: str, confidence: float) -> int:
            category_id = name_to_id.get(category)
            if not category_id:
                return 0
            upd = db.table("transactions").update(
                {"category_id": category_id, "confidence_score": confidence}
            ).eq("user_id", user_id).eq("raw_merchant", merchant).execute()
            try:
                db.table("learning_records").upsert(
                    {"user_id": user_id, "raw_merchant": merchant, "category_id": category_id},
                    on_conflict="user_id,raw_merchant",
                ).execute()
            except Exception as e:
                logger.warning("[categorizer] learning_record upsert failed for %s: %s", merchant, e)
            return len(upd.data or [])

        # Pass 1 — deterministic (no LLM). Fast, pure, no per-merchant DB reads.
        det_updated = 0
        det_merchants = 0
        remaining: list[str] = []
        for merchant, memo in needy.items():
            hit = rule_category(merchant, memo)
            if hit and hit[0] in name_to_id:
                det_updated += _apply(merchant, hit[0], hit[1])
                det_merchants += 1
            else:
                remaining.append(merchant)

        # Pass 2 — LLM for the long tail (only if a provider is configured).
        llm_updated = 0
        llm_merchants = 0
        llm_available = llm_client.is_available()
        if llm_available and remaining:
            unique = remaining[:_MAX_UNIQUE_MERCHANTS]
            mapping = await llm_categorize_merchants(unique, valid_names)
            for merchant, category in mapping.items():
                n = _apply(merchant, category, 0.9)
                if n:
                    llm_updated += n
                    llm_merchants += 1

        total = det_updated + llm_updated
        parts = [f"Rules categorized {det_merchants} merchants ({det_updated} txns)"]
        if llm_available:
            parts.append(f"AI categorized {llm_merchants} more ({llm_updated} txns)")
        else:
            parts.append(
                f"{len(remaining)} merchants still need AI — set GEMINI_API_KEYS to enable it"
            )
        return {
            "status": "done",
            "candidates": len(needy),
            "deterministic": {"merchants": det_merchants, "updated": det_updated},
            "llm": {
                "available": llm_available,
                "merchants": llm_merchants,
                "updated": llm_updated,
                "remaining": len(remaining),
            },
            "updated_transactions": total,
            "message": ". ".join(parts) + ".",
        }
    except Exception as e:
        logger.exception("recategorize failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
