"""Tools the chat agent can call to work on the user's financial data.

Each tool is a plain, deterministic function that queries the user's data through
PostgREST (never raw SQL) and returns compact, JSON-serialisable structured data —
NOT prose. The agent (``chat_agent.py``) decides which tool to call; the numbers it
answers with come only from these tools, so figures are always real.

Security: ``user_id`` is injected by the server on every call and is NEVER taken
from model output. The model only supplies the non-identifying ``args`` (dates,
keywords, limits), which are additionally validated/clamped here.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Optional

from supabase import Client

from app.services.chat_service import (
    _category_name,
    _fetch_transactions,
    _period_label,
    _spend_only,
    parse_period,
)

logger = logging.getLogger("tally.chat.tools")

# Hard cap on rows we ever feed back to a (weak, small-context) model.
_MAX_ROWS = 15


def _clamp_limit(value: Any, default: int, hard_max: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, hard_max))


def _resolve_period(start: Optional[str], end: Optional[str], question: str) -> tuple[Optional[str], Optional[str]]:
    """Prefer explicit dates the model supplied; otherwise parse from the question."""
    if start or end:
        return start, end
    return parse_period(question)


# --- tools ------------------------------------------------------------------

def get_spending_summary(
    db: Client, user_id: str, *, start: Optional[str] = None, end: Optional[str] = None,
    question: str = "", **_: Any,
) -> dict[str, Any]:
    """Totals (spent / received / net) and transaction count for a date range."""
    start, end = _resolve_period(start, end, question)
    txns = _fetch_transactions(db, user_id, start, end)
    total_spent = sum(float(t["amount"]) for t in _spend_only(txns))
    total_received = sum(-float(t["amount"]) for t in txns if float(t.get("amount") or 0) < 0)
    return {
        "period": _period_label(start, end),
        "total_spent": round(total_spent, 2),
        "total_received": round(total_received, 2),
        "net": round(total_received - total_spent, 2),
        "txn_count": len(txns),
    }


def get_spending_by_category(
    db: Client, user_id: str, *, start: Optional[str] = None, end: Optional[str] = None,
    category: Optional[str] = None, question: str = "", **_: Any,
) -> dict[str, Any]:
    """Spending grouped by category for a date range (optionally one category)."""
    start, end = _resolve_period(start, end, question)
    spend = _spend_only(_fetch_transactions(db, user_id, start, end))
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in spend:
        name = _category_name(t)
        totals[name]["total"] += float(t["amount"])
        totals[name]["count"] += 1

    rows = sorted(
        ({"name": k, "total": round(v["total"], 2), "count": int(v["count"])}
         for k, v in totals.items()),
        key=lambda r: r["total"], reverse=True,
    )
    if category:
        cl = category.lower()
        rows = [r for r in rows if cl in r["name"].lower()]
    return {
        "period": _period_label(start, end),
        "categories": rows[:_MAX_ROWS],
        "total_spent": round(sum(r["total"] for r in rows), 2),
    }


def get_top_merchants(
    db: Client, user_id: str, *, start: Optional[str] = None, end: Optional[str] = None,
    limit: int = 10, question: str = "", **_: Any,
) -> dict[str, Any]:
    """The biggest merchants by total spend for a date range."""
    start, end = _resolve_period(start, end, question)
    limit = _clamp_limit(limit, 10, _MAX_ROWS)
    spend = _spend_only(_fetch_transactions(db, user_id, start, end))
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in spend:
        m = t.get("raw_merchant") or "Unknown"
        totals[m]["total"] += float(t["amount"])
        totals[m]["count"] += 1
    rows = sorted(
        ({"name": k, "total": round(v["total"], 2), "count": int(v["count"])}
         for k, v in totals.items()),
        key=lambda r: r["total"], reverse=True,
    )
    return {"period": _period_label(start, end), "merchants": rows[:limit]}


def search_transactions(
    db: Client, user_id: str, *, keyword: str = "", start: Optional[str] = None,
    end: Optional[str] = None, limit: int = 10, question: str = "", **_: Any,
) -> dict[str, Any]:
    """Find transactions whose merchant matches a keyword (capped, most recent first)."""
    start, end = _resolve_period(start, end, question)
    limit = _clamp_limit(limit, 10, _MAX_ROWS)
    kw = (keyword or "").strip()
    if not kw:
        return {"keyword": kw, "count": 0, "transactions": [], "note": "no keyword provided"}

    q = (
        db.table("transactions")
        .select("date,amount,raw_merchant,counterparty,categories(name)")
        .eq("user_id", user_id)
        .ilike("raw_merchant", f"%{kw}%")
        .order("date", desc=True)
        .limit(limit)
    )
    if start:
        q = q.gte("date", start)
    if end:
        q = q.lte("date", end)
    rows = q.execute().data or []
    out = [
        {
            "date": r.get("date"),
            "merchant": r.get("raw_merchant") or r.get("counterparty") or "Unknown",
            "amount": round(float(r.get("amount") or 0), 2),
            "category": _category_name(r),
        }
        for r in rows
    ]
    return {"keyword": kw, "count": len(out), "transactions": out}


def list_events(db: Client, user_id: str, *, question: str = "", **_: Any) -> dict[str, Any]:
    """List the user's events (trips/occasions) with their totals."""
    rows = (
        db.table("events")
        .select("name,summary,total_amount")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(_MAX_ROWS)
        .execute()
        .data
        or []
    )
    events = [
        {
            "name": e.get("name", "Untitled"),
            "total_amount": round(float(e.get("total_amount") or 0), 2),
            "summary": e.get("summary"),
        }
        for e in rows
    ]
    return {"events": events}


def compare_periods(
    db: Client, user_id: str, *, period_a_start: Optional[str] = None,
    period_a_end: Optional[str] = None, period_b_start: Optional[str] = None,
    period_b_end: Optional[str] = None, question: str = "", **_: Any,
) -> dict[str, Any]:
    """Compare spending totals between two date ranges in a single call."""
    a = get_spending_summary(db, user_id, start=period_a_start, end=period_a_end)
    b = get_spending_summary(db, user_id, start=period_b_start, end=period_b_end)
    return {
        "period_a": a,
        "period_b": b,
        "spent_difference": round(a["total_spent"] - b["total_spent"], 2),
    }


# --- registry & schema (fed to the model) -----------------------------------

TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_spending_summary": get_spending_summary,
    "get_spending_by_category": get_spending_by_category,
    "get_top_merchants": get_top_merchants,
    "search_transactions": search_transactions,
    "list_events": list_events,
    "compare_periods": compare_periods,
}

# Human-readable schema injected into the selection prompt. Kept terse on purpose:
# weak free-tier models handle short, example-driven specs best.
TOOL_SPECS = """\
- get_spending_summary(start?, end?): totals spent/received/net and count for a date range.
- get_spending_by_category(start?, end?, category?): spending grouped by category; pass `category` to focus one.
- get_top_merchants(start?, end?, limit?): biggest merchants by spend for a date range.
- search_transactions(keyword, start?, end?, limit?): find transactions whose merchant matches a keyword.
- list_events(): list the user's trips/events with totals.
- compare_periods(period_a_start, period_a_end, period_b_start, period_b_end): compare two date ranges.
Dates are YYYY-MM-DD. Fields marked ? are optional; omit them if the user gave no range."""
