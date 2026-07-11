"""Spending insights & AI analysis endpoints.

Aggregates are computed in Python over the user's transactions (a few hundred
rows), which avoids depending on a Postgres ``sql_exec`` RPC and keeps the math
auditable. The AI narrative routes through the multi-provider ``llm_client`` and
degrades to a deterministic, number-driven summary when no LLM is available.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.auth import get_current_user
from app.core.database import get_supabase
from app.services import llm_client

logger = logging.getLogger("tally.insights")

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _fetch_transactions(
    db: Client, user_id: str, start: Optional[str], end: Optional[str]
) -> list[dict]:
    q = db.table("transactions").select(
        "amount,date,raw_merchant,categories(name)"
    ).eq("user_id", user_id).eq("is_transfer", False)
    if start:
        q = q.gte("date", start)
    if end:
        q = q.lte("date", end)
    return q.execute().data or []


def _compute_summary(txns: list[dict]) -> dict[str, Any]:
    total_spent = 0.0
    total_received = 0.0
    cat_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    merch_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"spent": 0.0, "received": 0.0})

    for t in txns:
        amount = float(t.get("amount") or 0)
        date_str = str(t.get("date") or "")[:7]  # YYYY-MM
        cat_obj = t.get("categories")
        if isinstance(cat_obj, list):  # tolerate list-shaped embed
            cat_obj = cat_obj[0] if cat_obj else None
        cat_name = cat_obj.get("name") if isinstance(cat_obj, dict) else "Uncategorized"
        merchant = t.get("raw_merchant") or "Unknown"

        if amount >= 0:  # spending (app convention: positive = money out)
            total_spent += amount
            cat_totals[cat_name]["total"] += amount
            cat_totals[cat_name]["count"] += 1
            merch_totals[merchant]["total"] += amount
            merch_totals[merchant]["count"] += 1
            if date_str:
                monthly[date_str]["spent"] += amount
        else:
            total_received += -amount
            if date_str:
                monthly[date_str]["received"] += -amount

    top_categories = sorted(
        ({"name": k, "total": round(v["total"], 2), "count": int(v["count"])}
         for k, v in cat_totals.items()),
        key=lambda x: x["total"], reverse=True,
    )[:10]
    top_merchants = sorted(
        ({"name": k, "total": round(v["total"], 2), "count": int(v["count"])}
         for k, v in merch_totals.items()),
        key=lambda x: x["total"], reverse=True,
    )[:10]
    monthly_list = [
        {"month": m, "spent": round(v["spent"], 2), "received": round(v["received"], 2)}
        for m, v in sorted(monthly.items())
    ]

    return {
        "total_spent": round(total_spent, 2),
        "total_received": round(total_received, 2),
        "net": round(total_received - total_spent, 2),
        "txn_count": len(txns),
        "top_categories": top_categories,
        "top_merchants": top_merchants,
        "monthly": monthly_list,
    }


@router.get("/summary")
async def insights_summary(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Deterministic spending aggregates for the given date range."""
    try:
        txns = _fetch_transactions(db, user_id, start, end)
        return _compute_summary(txns)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


def _deterministic_narrative(summary: dict) -> dict[str, Any]:
    """Fallback used when no LLM provider is configured/available."""
    highlights = []
    if summary["top_categories"]:
        c = summary["top_categories"][0]
        highlights.append(
            f"Top category: {c['name']} (Rs {c['total']:,.0f} across {c['count']} txns)."
        )
    if summary["top_merchants"]:
        m = summary["top_merchants"][0]
        highlights.append(
            f"Most spent at: {m['name']} (Rs {m['total']:,.0f})."
        )
    highlights.append(
        f"Net for the period: Rs {summary['net']:,.0f} "
        f"(spent Rs {summary['total_spent']:,.0f}, received Rs {summary['total_received']:,.0f})."
    )
    return {
        "summary": (
            f"Across {summary['txn_count']} transactions you spent "
            f"Rs {summary['total_spent']:,.0f} and received Rs {summary['total_received']:,.0f}."
        ),
        "highlights": highlights,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ai")
async def insights_ai(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """AI-written narrative over the spending aggregates (with safe fallback)."""
    try:
        txns = _fetch_transactions(db, user_id, start, end)
        summary = _compute_summary(txns)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    if not llm_client.is_available():
        return _deterministic_narrative(summary)

    prompt = (
        "You are a concise personal-finance analyst. Based ONLY on the aggregated "
        "spending data below (amounts already computed, in INR), write a short "
        "analysis. Do NOT do arithmetic yourself. Respond as strict JSON: "
        '{"summary": "2-3 sentence overview", "highlights": ["bullet", "bullet", "bullet"]}.\n\n'
        f"Data: {summary}"
    )
    try:
        result = await llm_client.acomplete_json(prompt, max_tokens=600)
        return {
            "summary": str(result.get("summary", "")).strip() or _deterministic_narrative(summary)["summary"],
            "highlights": [str(h) for h in (result.get("highlights") or [])][:6],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"AI insights fell back to deterministic summary: {e}")
        return _deterministic_narrative(summary)
