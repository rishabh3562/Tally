"""Transactions API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.transactions import TransactionOut, CategoryPatchRequest

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_transactions(
    start_date: date = Query(None),
    end_date: date = Query(None),
    category_id: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
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
