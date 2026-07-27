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
from app.services.categorizer import (
    llm_categorize_merchants,
    load_user_overrides,
    match_override,
    rule_category,
)

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
        # Valid category names + a name->id map. Includes the user's OWN
        # categories: they had created Rent, Health and Petrol holding a sixth of
        # all their spend, and a system-only list meant neither the rules nor the
        # LLM could ever assign them.
        cats = db.table("categories").select("id,name").or_(
            f"user_id.is.null,user_id.eq.{user_id}"
        ).execute().data or []
        name_to_id = {c["name"]: c["id"] for c in cats}
        valid_names = [c["name"] for c in cats if c["name"] != "Other"]

        # Transactions needing help: category "Other" or no category at all.
        # Keep a representative memo per merchant for the regex layer.
        rows = db.table("transactions").select(
            "raw_merchant,memo,category_id,categories(name)"
        ).eq("user_id", user_id).execute().data or []

        # Merchants the user has already decided by hand are OFF LIMITS here. Two
        # ways this used to destroy their work: `_apply` updates every row of a
        # merchant with no category filter, so a merchant with a mix of "Other" and
        # hand-corrected rows had the corrected ones overwritten; and its
        # learning_records upsert would replace the stored decision itself with a
        # machine guess, which is the only durable record of what they chose.
        decided: set[str] = set()
        try:
            decided = {
                r["raw_merchant"]
                for r in (
                    db.table("learning_records").select("raw_merchant").eq(
                        "user_id", user_id
                    ).eq("source", "user").execute().data
                    or []
                )
                if r.get("raw_merchant")
            }
        except Exception as e:
            # Fail closed: if we can't tell what the user decided, don't touch
            # anything rather than risk overwriting it.
            logger.warning("[categorizer] could not load user decisions: %s", e)
            return {
                "status": "skipped",
                "reason": "Could not read your saved corrections, so nothing was "
                          "changed. Try again in a moment.",
            }

        needy: dict[str, str | None] = {}
        for r in rows:
            cat = r.get("categories")
            if isinstance(cat, list):  # tolerate list-shaped embed
                cat = cat[0] if cat else None
            cat_name = cat.get("name") if isinstance(cat, dict) else None
            merchant = r.get("raw_merchant")
            if (cat_name in (None, "Other")) and merchant and merchant not in decided:
                needy.setdefault(merchant, r.get("memo"))

        if not needy:
            return {
                "status": "done",
                "candidates": 0,
                "updated_transactions": 0,
                "message": "Nothing to recategorize — no 'Other'/uncategorized transactions.",
            }

        other_id = name_to_id.get("Other")

        def _apply(merchant: str, category: str, confidence: float, source: str) -> int:
            category_id = name_to_id.get(category)
            if not category_id:
                return 0
            upd = db.table("transactions").update(
                {"category_id": category_id, "confidence_score": confidence}
            ).eq("user_id", user_id).eq("raw_merchant", merchant)
            # Only the rows that actually need help. Belt and braces behind the
            # `decided` exclusion above: even for a merchant we're allowed to touch,
            # never relabel a row that already carries a real category.
            if other_id:
                upd = upd.or_(f"category_id.is.null,category_id.eq.{other_id}")
            else:
                upd = upd.is_("category_id", "null")
            result = upd.execute()
            try:
                # `source` marks this as a GUESS, so it stays a cache that future
                # rule improvements can override — and can never be mistaken for
                # something the user chose.
                db.table("learning_records").upsert(
                    {
                        "user_id": user_id,
                        "raw_merchant": merchant,
                        "category_id": category_id,
                        "source": source,
                    },
                    on_conflict="user_id,raw_merchant",
                ).execute()
            except Exception as e:
                logger.warning("[categorizer] learning_record upsert failed for %s: %s", merchant, e)
            return len(result.data or [])

        # Pass 1 — deterministic (no LLM). Fast, pure, no per-merchant DB reads.
        det_updated = 0
        det_merchants = 0
        remaining: list[str] = []
        for merchant, memo in needy.items():
            hit = rule_category(merchant, memo)
            if hit and hit[0] in name_to_id:
                det_updated += _apply(merchant, hit[0], hit[1], "rule")
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
                n = _apply(merchant, category, 0.9, "llm")
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


@router.post("/learning/reapply")
async def reapply_user_corrections(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Re-assert the user's own corrections over any rows that drifted from them.

    Corrections live in ``learning_records`` with ``source='user'`` and are applied
    at ingestion (see ``categorizer.resolve_category``). But rows imported BEFORE
    that precedence existed — or any row a rule mislabelled while the rules outranked
    the user — still carry the machine's answer. ``/recategorize`` can't fix those:
    it only looks at rows that are "Other" or uncategorized.

    Idempotent, and the primitive worth running after every rule change. Only ever
    writes the category the user themselves chose.
    """
    try:
        records = (
            db.table("learning_records")
            .select("raw_merchant,category_id")
            .eq("user_id", user_id)
            .eq("source", "user")
            .execute()
            .data
            or []
        )
        if not records:
            return {
                "status": "done", "corrections": 0, "updated_transactions": 0,
                "message": "You haven't corrected any merchants yet.",
            }

        overrides = load_user_overrides(db, user_id)
        rows = (
            db.table("transactions")
            .select("id,raw_merchant,category_id")
            .eq("user_id", user_id)
            .execute()
            .data
            or []
        )

        # Group the drifted rows by the category they SHOULD have, so this is a
        # handful of updates rather than one per transaction.
        wanted: dict[str, list[str]] = {}
        for r in rows:
            want = match_override(r.get("raw_merchant") or "", overrides)
            if want and r.get("category_id") != want:
                wanted.setdefault(want, []).append(r["id"])

        updated = 0
        for category_id, ids in wanted.items():
            for start in range(0, len(ids), 100):
                chunk = ids[start:start + 100]
                res = (
                    db.table("transactions")
                    .update({"category_id": category_id, "confidence_score": 1.0})
                    .eq("user_id", user_id)
                    .in_("id", chunk)
                    .execute()
                )
                updated += len(res.data or [])

        return {
            "status": "done",
            "corrections": len(records),
            "updated_transactions": updated,
            "message": (
                f"Re-applied {len(records)} of your corrections; "
                f"{updated} transaction{'s' if updated != 1 else ''} put back."
                if updated
                else f"All {len(records)} of your corrections are already applied."
            ),
        }
    except Exception as e:
        logger.exception("reapply failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
