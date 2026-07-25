"""Events API routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from uuid import uuid4
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.schemas.events import EventCreate, EventOut
from app.services import llm_client

logger = logging.getLogger("tally.events")

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", response_model=EventOut)
@router.post("/", response_model=EventOut, include_in_schema=False)
async def create_event(
    event: EventCreate,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
    settings: object = Depends(get_settings),
):
    """Create an event and generate AI summary."""
    try:
        event_id = str(uuid4())

        # Only the caller's OWN transactions (never trust the id list blindly —
        # service-role bypasses RLS, so scope by user_id).
        transactions = (
            db.table("transactions")
            .select("id,date,amount,raw_merchant,category_id")
            .eq("user_id", user_id)
            .in_("id", event.transaction_ids)
            .execute().data
            or []
        )
        owned_ids = [t["id"] for t in transactions]
        total_amount = round(sum(float(t.get("amount") or 0) for t in transactions), 2)

        summary = await _generate_event_summary(event.name, transactions, settings)

        inserted = (
            db.table("events").insert({
                "id": event_id,
                "user_id": user_id,
                "name": event.name,
                "description": event.description,
                "metadata": event.metadata,
                "summary": summary,
                "total_amount": total_amount,
            }).execute().data
        )
        row = (inserted or [{}])[0]

        # Link only the owned transactions.
        for tx_id in owned_ids:
            db.table("event_transactions").insert({
                "event_id": event_id,
                "transaction_id": tx_id,
            }).execute()

        return EventOut(
            id=event_id,
            user_id=user_id,
            name=event.name,
            description=event.description,
            metadata=event.metadata,
            summary=summary,
            total_amount=total_amount,
            currency=row.get("currency", "INR"),
            created_at=row.get("created_at"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("", response_model=list[EventOut])
@router.get("/", response_model=list[EventOut], include_in_schema=False)
async def list_events(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """List user's events."""
    try:
        response = db.table("events").select("*").eq("user_id", user_id).order(
            "created_at", desc=True
        ).execute()
        return response.data if response.data else []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get an event with its member transactions (which keep their own category)."""
    try:
        ev = db.table("events").select("*").eq(
            "id", event_id
        ).eq("user_id", user_id).limit(1).execute().data
        if not ev:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
            )

        links = db.table("event_transactions").select(
            "transaction_id"
        ).eq("event_id", event_id).execute().data or []
        tx_ids = [l["transaction_id"] for l in links]

        txns = []
        if tx_ids:
            txns = db.table("transactions").select(
                "id,date,amount,raw_merchant,memo,category_id,categories(name)"
            ).eq("user_id", user_id).in_("id", tx_ids).order(
                "date", desc=True
            ).execute().data or []

        return {**ev[0], "transactions": txns}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Delete an event (its transactions are untouched — only the grouping goes)."""
    try:
        ev = db.table("events").select("id").eq(
            "id", event_id
        ).eq("user_id", user_id).limit(1).execute().data
        if not ev:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
            )
        db.table("event_transactions").delete().eq("event_id", event_id).execute()
        db.table("events").delete().eq("id", event_id).eq("user_id", user_id).execute()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


async def _generate_event_summary(
    event_name: str,
    transactions: list,
    settings: object = None,
) -> str:
    """Generate an AI summary for an event, with a deterministic fallback.

    Routes through the shared async ``llm_client`` (Gemini key rotation +
    OpenRouter fallback) rather than a blocking direct HTTP call, and always
    degrades to a computed one-liner when no LLM provider is available.
    """
    if not transactions:
        return f"Event '{event_name}' with no transactions."

    total_amount = sum(t["amount"] for t in transactions)
    count = len(transactions)
    fallback = f"{event_name}: Spent ₹{total_amount:,.2f} across {count} transactions."

    if not llm_client.is_available():
        return fallback

    prompt = (
        "Provide a brief 1-2 sentence summary of this event based on the "
        "transaction data. Do not invent figures; the totals are given.\n"
        f'Format: "[Event Name]: Spent Rs [amount] across [count] transactions. '
        'Breakdown: [categories]"\n\n'
        f"Event: {event_name}\n"
        f"Number of transactions: {count}\n"
        f"Total amount: Rs {total_amount:,.2f}\n"
        f"Sample transactions: {str(transactions[:5])[:500]}"
    )

    try:
        out = (await llm_client.acomplete(prompt, max_tokens=120)).strip()
        return out or fallback
    except Exception as e:
        logger.warning("event summary fell back to deterministic text: %s", e)
        return fallback
