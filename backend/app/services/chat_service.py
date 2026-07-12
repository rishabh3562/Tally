"""Chat service: answers finance questions from the user's own transactions.

No raw SQL and no ``sql_exec`` RPC (that RPC does not exist in this project).
Following the same approach as ``app/api/insights.py``, we fetch the user's
transactions through PostgREST (parameterized, so no SQL injection is possible)
and compute the answer in Python. Answers are deterministic and number-driven;
an LLM only ever *rephrases* pre-computed figures (wired in a later iteration),
never invents them.
"""

from __future__ import annotations

import calendar
import re
from collections import defaultdict
from datetime import date, timedelta
from enum import Enum
from typing import Any, Optional

from supabase import Client


class IntentType(str, Enum):
    """Chat query intent types."""
    TOTAL_BY_CATEGORY = "total_by_category"
    MERCHANT_BREAKDOWN = "merchant_breakdown"
    PERIOD_COMPARISON = "period_comparison"
    EVENT_QUERY = "event_query"
    OPEN_ENDED = "open_ended"


# Category keywords the user might name in a question -> canonical label used for
# matching against stored category names (case-insensitive ``in`` check).
_CATEGORY_KEYWORDS = [
    "food", "grocery", "groceries", "transport", "travel", "shopping",
    "entertainment", "bills", "utilities", "rent", "health", "medical",
    "fuel", "petrol", "education", "subscription", "dining", "restaurant",
]

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})


def classify_intent(question: str) -> IntentType:
    """Classify a natural-language finance question into a query intent."""
    q = question.lower()

    if any(kw in q for kw in ["trip", "vacation", "event", "holiday"]):
        return IntentType.EVENT_QUERY

    if any(kw in q for kw in ["merchant", "store", "vendor", "shop", "where", "who"]):
        return IntentType.MERCHANT_BREAKDOWN

    if any(kw in q for kw in ["compare", "compared", "comparison", "vs", "versus", "difference"]):
        return IntentType.PERIOD_COMPARISON

    if any(kw in q for kw in ["total", "spent", "spend", "spending", "amount", "how much"]):
        return IntentType.TOTAL_BY_CATEGORY

    return IntentType.OPEN_ENDED


def extract_category(question: str) -> Optional[str]:
    """Return the first category keyword named in the question, if any."""
    q = question.lower()
    for kw in _CATEGORY_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", q):
            return kw
    return None


def parse_period(question: str, today: Optional[date] = None) -> tuple[Optional[str], Optional[str]]:
    """Parse a date range from the question.

    Returns ``(start_iso, end_iso)`` as ``YYYY-MM-DD`` strings, or ``(None, None)``
    when the question names no period (meaning "all time"). Inclusive of both ends.
    """
    today = today or date.today()
    q = question.lower()

    # "last N days" / "past N days"
    m = re.search(r"\b(?:last|past)\s+(\d+)\s+days?\b", q)
    if m:
        n = int(m.group(1))
        return (today - timedelta(days=n)).isoformat(), today.isoformat()

    if "this month" in q:
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()

    if "last month" in q or "previous month" in q:
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start = last_prev.replace(day=1)
        return start.isoformat(), last_prev.isoformat()

    if "this year" in q:
        return date(today.year, 1, 1).isoformat(), today.isoformat()

    if "last year" in q or "previous year" in q:
        y = today.year - 1
        return date(y, 1, 1).isoformat(), date(y, 12, 31).isoformat()

    # "in <month>" / "<month> <year>" / bare month name.
    for name, month_num in _MONTHS.items():
        if re.search(rf"\b{name}\b", q):
            ym = re.search(rf"\b{name}\s+(\d{{4}})\b", q)
            year = int(ym.group(1)) if ym else today.year
            # If the named month is in the future for the current year, assume last year.
            if not ym and month_num > today.month:
                year -= 1
            last_day = calendar.monthrange(year, month_num)[1]
            return date(year, month_num, 1).isoformat(), date(year, month_num, last_day).isoformat()

    return None, None


def _period_label(start: Optional[str], end: Optional[str]) -> str:
    """Human phrase for the resolved date range, for use in answer text."""
    if not start and not end:
        return "all time"
    if start and end:
        return f"{start} to {end}"
    if start:
        return f"since {start}"
    return f"up to {end}"


def _fetch_transactions(
    db: Client, user_id: str, start: Optional[str], end: Optional[str]
) -> list[dict]:
    """Fetch the user's non-transfer transactions in the period via PostgREST."""
    q = (
        db.table("transactions")
        .select("amount,date,raw_merchant,categories(name)")
        .eq("user_id", user_id)
        .eq("is_transfer", False)
    )
    if start:
        q = q.gte("date", start)
    if end:
        q = q.lte("date", end)
    return q.execute().data or []


def _category_name(txn: dict) -> str:
    cat_obj = txn.get("categories")
    if isinstance(cat_obj, list):  # tolerate list-shaped embed
        cat_obj = cat_obj[0] if cat_obj else None
    return cat_obj.get("name") if isinstance(cat_obj, dict) else "Uncategorized"


def _spend_only(txns: list[dict]) -> list[dict]:
    """Keep spending rows (app convention: positive amount = money out)."""
    return [t for t in txns if float(t.get("amount") or 0) >= 0]


def _rupees(amount: float) -> str:
    return f"Rs {amount:,.0f}"


def _answer_total_by_category(txns: list[dict], question: str, period: str) -> str:
    spend = _spend_only(txns)
    if not spend:
        return f"I found no spending for {period}."

    category = extract_category(question)
    if category:
        matched = [t for t in spend if category in _category_name(t).lower()]
        total = sum(float(t["amount"]) for t in matched)
        if not matched:
            return f"I found no spending tagged '{category}' for {period}."
        return (
            f"You spent {_rupees(total)} on {category} across {len(matched)} "
            f"transactions ({period})."
        )

    totals: dict[str, float] = defaultdict(float)
    for t in spend:
        totals[_category_name(t)] += float(t["amount"])
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    grand = sum(totals.values())
    breakdown = ", ".join(f"{name} ({_rupees(amt)})" for name, amt in top)
    return (
        f"For {period} you spent {_rupees(grand)} across {len(spend)} transactions. "
        f"Top categories: {breakdown}."
    )


def _answer_merchant_breakdown(txns: list[dict], period: str) -> str:
    spend = _spend_only(txns)
    if not spend:
        return f"I found no spending for {period}."

    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in spend:
        m = t.get("raw_merchant") or "Unknown"
        totals[m]["total"] += float(t["amount"])
        totals[m]["count"] += 1
    top = sorted(totals.items(), key=lambda kv: kv[1]["total"], reverse=True)[:5]
    breakdown = ", ".join(
        f"{name} ({_rupees(v['total'])}, {int(v['count'])} txns)" for name, v in top
    )
    return f"Your top merchants for {period}: {breakdown}."


def _answer_open_ended(txns: list[dict], period: str) -> str:
    total_spent = sum(float(t["amount"]) for t in _spend_only(txns))
    total_received = sum(-float(t["amount"]) for t in txns if float(t.get("amount") or 0) < 0)
    net = total_received - total_spent
    return (
        f"For {period}: you spent {_rupees(total_spent)} and received "
        f"{_rupees(total_received)} across {len(txns)} transactions "
        f"(net {_rupees(net)})."
    )


def _answer_events(db: Client, user_id: str) -> str:
    rows = (
        db.table("events")
        .select("name,summary,total_amount")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    if not rows:
        return "You don't have any events (trips/occasions) yet. Create one from a group of transactions to track it here."
    parts = []
    for e in rows:
        total = float(e.get("total_amount") or 0)
        parts.append(f"{e.get('name', 'Untitled')} ({_rupees(total)})")
    return "Your recent events: " + ", ".join(parts) + "."


def answer_question(question: str, user_id: str, db: Client) -> str:
    """Produce a deterministic, number-driven answer to a finance question."""
    intent = classify_intent(question)

    if intent == IntentType.EVENT_QUERY:
        return _answer_events(db, user_id)

    start, end = parse_period(question)
    period = _period_label(start, end)
    txns = _fetch_transactions(db, user_id, start, end)

    if intent == IntentType.MERCHANT_BREAKDOWN:
        return _answer_merchant_breakdown(txns, period)
    if intent == IntentType.TOTAL_BY_CATEGORY:
        return _answer_total_by_category(txns, question, period)
    return _answer_open_ended(txns, period)


def _sse_pack(text: str):
    """Yield ``text`` as SSE ``data:`` events, one whitespace-delimited token at a
    time. Splitting on tokens keeps each event single-line so the frontend's
    line-based parser stays correct; a trailing space rejoins them on the client.
    """
    for token in text.split(" "):
        yield f"data: {token} \n\n"


async def stream_chat_response(question: str, user_id: str, db: Client):
    """Stream a chat answer as Server-Sent Events."""
    try:
        answer = answer_question(question, user_id, db)
    except Exception as e:  # pragma: no cover - defensive, surfaced to the user
        answer = f"Sorry, I couldn't answer that right now ({e})."

    for event in _sse_pack(answer):
        yield event
