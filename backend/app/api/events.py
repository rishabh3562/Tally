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

        # Get transactions for the event
        tx_response = db.table("transactions").select(
            "id,date,amount,raw_merchant,category_id"
        ).in_("id", event.transaction_ids).execute()

        transactions = tx_response.data if tx_response.data else []

        # Generate AI summary
        summary = await _generate_event_summary(
            event.name,
            transactions,
            settings,
        )

        # Create event
        db.table("events").insert({
            "id": event_id,
            "user_id": user_id,
            "name": event.name,
            "metadata": event.metadata,
            "summary": summary,
        }).execute()

        # Add transactions to event
        for tx_id in event.transaction_ids:
            db.table("event_transactions").insert({
                "event_id": event_id,
                "transaction_id": tx_id,
            }).execute()

        return EventOut(
            id=event_id,
            user_id=user_id,
            name=event.name,
            metadata=event.metadata,
            summary=summary,
            created_at=None,
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


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get event details."""
    try:
        response = db.table("events").select("*").eq(
            "id", event_id
        ).eq("user_id", user_id).limit(1).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )

        return response.data[0]
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
