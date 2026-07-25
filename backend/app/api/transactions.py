"""Transactions API routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.transactions import TransactionOut, CategoryPatchRequest, AssignMerchantRequest
from app.services import llm_client
from app.services.categorizer import categorize_transaction, rule_category

logger = logging.getLogger("tally.transactions")

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_transactions(
    start_date: date = Query(None),
    end_date: date = Query(None),
    category_id: str = Query(None),
    merchant: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """List user's transactions with optional filters."""
    try:
        query = db.table("transactions").select("*").eq("user_id", user_id)

        if start_date:
            query = query.gte("date", start_date.isoformat())
        if end_date:
            query = query.lte("date", end_date.isoformat())
        if category_id:
            query = query.eq("category_id", category_id)
        if merchant:
            # Exact raw-merchant match — used by the triage drill-in to override
            # individual rows of one merchant.
            query = query.eq("raw_merchant", merchant)

        # Get total count
        count_response = query.execute()
        total = len(count_response.data) if count_response.data else 0

        # Paginate
        offset = (page - 1) * limit
        response = query.order("date", desc=True).range(offset, offset + limit - 1).execute()

        return {
            "data": response.data,
            "total": total,
            "page": page,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.patch("/{transaction_id}/category")
async def update_transaction_category(
    transaction_id: str,
    request: CategoryPatchRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Update transaction category and optionally save merchant correction."""
    try:
        # Verify transaction belongs to user
        tx_response = db.table("transactions").select("*").eq(
            "id", transaction_id
        ).eq("user_id", user_id).limit(1).execute()

        if not tx_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found",
            )

        transaction = tx_response.data[0]

        # Update category
        db.table("transactions").update(
            {"category_id": request.category_id}
        ).eq("id", transaction_id).execute()

        # If merchant correction, save learning record
        if request.merchant_correction and transaction["raw_merchant"]:
            db.table("learning_records").upsert({
                "user_id": user_id,
                "raw_merchant": transaction["raw_merchant"],
                "category_id": request.category_id,
            }).execute()

        return {"updated": True}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{transaction_id}/suggest-category")
async def suggest_category(
    transaction_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Suggest a category for one transaction (AI when available, else rules).

    Does NOT apply the change — the client shows the suggestion and the user
    confirms via PATCH /{id}/category.
    """
    try:
        tx = db.table("transactions").select(
            "id,raw_merchant,memo,amount"
        ).eq("id", transaction_id).eq("user_id", user_id).limit(1).execute().data
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        tx = tx[0]

        cats = db.table("categories").select("id,name").is_(
            "user_id", "null"
        ).execute().data or []
        name_to_id = {c["name"]: c["id"] for c in cats}
        valid_names = [c["name"] for c in cats]

        merchant = tx.get("raw_merchant") or ""
        memo = tx.get("memo") or ""
        amount = float(tx.get("amount") or 0)

        # Try AI first for a smarter, explained suggestion.
        if llm_client.is_available() and valid_names:
            prompt = (
                "Pick the single best category for this transaction, strictly from "
                f"this list: {', '.join(valid_names)}.\n"
                f"Merchant: {merchant}\nMemo: {memo}\nAmount (INR): {amount}\n"
                'Respond as strict JSON: {"category": "<one from the list>", '
                '"reason": "<short why>"}.'
            )
            try:
                data = await llm_client.acomplete_json(prompt, max_tokens=200)
                cat = data.get("category") if isinstance(data, dict) else None
                if isinstance(cat, str) and cat in name_to_id:
                    return {
                        "suggested_category": cat,
                        "suggested_category_id": name_to_id[cat],
                        "confidence": 0.9,
                        "reasoning": str(data.get("reason", "")).strip() or None,
                        "source": "ai",
                    }
            except Exception as e:
                logger.warning("suggest-category AI fell back to rules: %s", e)

        # Deterministic fallback.
        category, confidence = await categorize_transaction(merchant, amount, memo, db)
        return {
            "suggested_category": category,
            "suggested_category_id": name_to_id.get(category),
            "confidence": confidence,
            "reasoning": None,
            "source": "rule",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/review-queue")
async def get_review_queue(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get low-confidence transactions for user review."""
    try:
        response = db.table("transactions").select("*").eq(
            "user_id", user_id
        ).lt("confidence_score", 0.5).order("confidence_score").execute()

        return {
            "data": response.data,
            "count": len(response.data) if response.data else 0,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def aggregate_triage(rows: list[dict], name_to_id: dict[str, str]) -> list[dict]:
    """Group needy transactions (category 'Other'/none) by raw merchant.

    Pure and DB-free so it's directly unit-testable. Returns one entry per
    merchant with count, absolute ₹ total, a sample memo, and a deterministic
    ``rule_category`` suggestion, sorted by total descending (biggest first).
    """
    groups: dict[str, dict] = {}
    for r in rows:
        cat = r.get("categories")
        if isinstance(cat, list):
            cat = cat[0] if cat else None
        cat_name = cat.get("name") if isinstance(cat, dict) else None
        merchant = r.get("raw_merchant")
        if cat_name not in (None, "Other") or not merchant:
            continue
        g = groups.setdefault(
            merchant,
            {"raw_merchant": merchant, "count": 0, "total": 0.0, "net": 0.0,
             "sample_memo": r.get("memo")},
        )
        amt = float(r.get("amount") or 0)
        g["count"] += 1
        g["total"] += abs(amt)
        g["net"] += amt   # signed: positive = spent, negative = received

    out = []
    for merchant, g in groups.items():
        hit = rule_category(merchant, g.get("sample_memo"))
        suggestion = None
        if hit and hit[0] in name_to_id:
            suggestion = {
                "category": hit[0],
                "category_id": name_to_id[hit[0]],
                "confidence": hit[1],
            }
        out.append(
            {**g, "total": round(g["total"], 2), "net": round(g["net"], 2),
             "suggestion": suggestion}
        )

    out.sort(key=lambda x: x["total"], reverse=True)
    return out


@router.get("/triage")
async def get_triage_queue(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Merchants that still need a category, grouped and ranked by ₹ impact.

    The "Other" pile is many rows but far fewer merchants, so triage works per
    *merchant*: labelling one clears all its rows. Each entry carries a cheap,
    deterministic ``rule_category`` suggestion (no LLM) that the client can
    accept in one keystroke, or upgrade to an AI suggestion on demand via
    ``POST /{id}/suggest-category``. Sorted by absolute total so the biggest
    wins come first.
    """
    try:
        cats = db.table("categories").select("id,name").or_(
            f"user_id.is.null,user_id.eq.{user_id}"
        ).execute().data or []
        name_to_id = {c["name"]: c["id"] for c in cats}

        rows = db.table("transactions").select(
            "raw_merchant,amount,memo,category_id,categories(name)"
        ).eq("user_id", user_id).execute().data or []

        out = aggregate_triage(rows, name_to_id)
        return {
            "data": out,
            "merchants": len(out),
            "total_amount": round(sum(x["total"] for x in out), 2),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/assign-merchant")
async def assign_merchant_category(
    request: AssignMerchantRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Assign a category to **all** of the user's rows for one raw merchant.

    This is the triage bulk action: it updates every existing transaction of
    ``raw_merchant`` and records the choice in ``learning_records`` so future
    imports of the same merchant categorize for free. Single-row exceptions are
    handled afterwards via ``PATCH /{id}/category``.
    """
    try:
        # The category must be visible to this user (system or their own).
        cat = db.table("categories").select("id").or_(
            f"user_id.is.null,user_id.eq.{user_id}"
        ).eq("id", request.category_id).limit(1).execute().data
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

        upd = db.table("transactions").update(
            {"category_id": request.category_id, "confidence_score": 1.0}
        ).eq("user_id", user_id).eq("raw_merchant", request.raw_merchant).execute()

        db.table("learning_records").upsert(
            {
                "user_id": user_id,
                "raw_merchant": request.raw_merchant,
                "category_id": request.category_id,
            },
            on_conflict="user_id,raw_merchant",
        ).execute()

        return {"updated": len(upd.data or [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
