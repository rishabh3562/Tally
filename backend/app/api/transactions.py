"""Transactions API routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.transactions import TransactionOut, CategoryPatchRequest
from app.services import llm_client
from app.services.categorizer import categorize_transaction

logger = logging.getLogger("tally.transactions")

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_transactions(
    start_date: date = Query(None),
    end_date: date = Query(None),
    category_id: str = Query(None),
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
