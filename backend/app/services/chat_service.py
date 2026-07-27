"""Chat service: answers finance questions from the user's own transactions.

No raw SQL and no ``sql_exec`` RPC (that RPC does not exist in this project).
Following the same approach as ``app/api/insights.py``, we fetch the user's
transactions through PostgREST (parameterized, so no SQL injection is possible)
and compute the answer in Python. Answers are deterministic and number-driven;
an LLM only ever *rephrases* pre-computed figures (wired in a later iteration),
never invents them.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import re
import time
from collections import defaultdict
from datetime import date, timedelta
from enum import Enum
from typing import Any, Optional

from supabase import Client

from app.services import llm_client
from app.services.merchant import canonical_merchant

logger = logging.getLogger("tally.chat")


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
    "transfer", "transfers", "subscriptions",
]

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})


def classify_intent(question: str) -> IntentType:
    """Classify a natural-language finance question into a query intent."""
    q = question.lower()

    if any(kw in q for kw in ["trip", "vacation", "event", "holiday"]):
        return IntentType.EVENT_QUERY

    # Comparison only when the question genuinely names two periods (the
    # discriminating condition) — keyword-guessing hijacked amount-threshold
    # questions like "more than 500 on food" and lost the category filter.
    if any(kw in q for kw in ["compare", "compared", "comparison", "vs", "versus",
                              "difference"]) or parse_two_periods(question) is not None:
        return IntentType.PERIOD_COMPARISON

    # An explicitly named category wins over the merchant heuristic — otherwise
    # "how much on shopping" matches "shop" and returns merchants, not shopping.
    if extract_category(question):
        return IntentType.TOTAL_BY_CATEGORY

    # "top categories" / "spending by category" — the word itself is the intent,
    # even though it isn't one of the category NAMES in _CATEGORY_KEYWORDS.
    if "categor" in q:
        return IntentType.TOTAL_BY_CATEGORY

    if any(kw in q for kw in ["merchant", "store", "vendor", "shop", "where", "who"]):
        return IntentType.MERCHANT_BREAKDOWN

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


def extract_categories(question: str) -> list[str]:
    """Every category keyword named, in the order they appear — so "more on food
    than shopping" can be answered as the comparison it actually is."""
    q = question.lower()
    found: list[tuple[int, str]] = []
    for kw in _CATEGORY_KEYWORDS:
        m = re.search(rf"\b{re.escape(kw)}\b", q)
        if m:
            found.append((m.start(), kw))
    out: list[str] = []
    for _, kw in sorted(found):
        # "groceries" also matches "grocery"; keep one entry per distinct spend area.
        if not any(kw.startswith(seen) or seen.startswith(kw) for seen in out):
            out.append(kw)
    return out


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

    # "last N weeks/months" — same shape as days, in the other units.
    m = re.search(r"\b(?:last|past)\s+(\d+)\s+weeks?\b", q)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).isoformat(), today.isoformat()
    m = re.search(r"\b(?:last|past)\s+(\d+)\s+months?\b", q)
    if m:
        return (today - timedelta(days=30 * int(m.group(1)))).isoformat(), today.isoformat()

    if re.search(r"\byesterday\b", q):
        y = today - timedelta(days=1)
        return y.isoformat(), y.isoformat()

    # "today" means one day only when it IS the period. In "up to today" / "as of
    # today" it's the END of an open range, so scoping to a single day would
    # answer the opposite of the question.
    if re.search(r"\btoday\b", q) and not re.search(
        r"\b(?:to|until|till|through|thru|as of|up to|so far)\s+today\b", q
    ):
        return today.isoformat(), today.isoformat()

    # Weeks run Monday–Sunday. "last week" was previously unparsed, which silently
    # answered ALL TIME for a question about seven days — the worst kind of wrong.
    this_monday = today - timedelta(days=today.weekday())
    if "this week" in q:
        return this_monday.isoformat(), today.isoformat()
    if "last week" in q or "previous week" in q or "past week" in q:
        prev_monday = this_monday - timedelta(days=7)
        return prev_monday.isoformat(), (this_monday - timedelta(days=1)).isoformat()

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


_COMPARE_CONNECTIVES = [" versus ", " vs. ", " vs ", " compared to ", " compared with ", " than ", " and "]


def parse_two_periods(
    question: str, today: Optional[date] = None
) -> Optional[tuple[tuple, tuple]]:
    """Parse a comparison like 'this month vs last month' or 'June and July' into
    two ``(start, end)`` ranges. Returns None if two periods can't be resolved."""
    q = question.lower()
    for conn in _COMPARE_CONNECTIVES:
        if conn in q:
            left, right = q.split(conn, 1)
            a = parse_period(left, today)
            b = parse_period(right, today)
            if a != (None, None) and b != (None, None):
                return a, b
    # Fallback: both relative terms present without an explicit connective.
    if "this month" in q and ("last month" in q or "previous month" in q):
        return parse_period("this month", today), parse_period("last month", today)
    return None


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


def _pretty_date(iso: str) -> str:
    """'2025-12-07' -> '7 Dec 2025' (falls back to the raw string if unparseable).

    Built by hand rather than with strftime because the no-zero-pad day directive
    differs by platform ('%-d' glibc vs '%#d' Windows).
    """
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def _pretty_month(ym: str) -> str:
    """'2026-04' -> 'April 2026' (month keys are what the detectors emit)."""
    try:
        return date.fromisoformat(f"{ym}-01").strftime("%B %Y")
    except ValueError:
        return ym


def _pretty_period(start: Optional[str], end: Optional[str]) -> str:
    """Readable phrase for a range: 'June 2026', '7 Dec 2025 – 3 Jan 2026'.

    `_period_label` stays ISO because other answers (and their tests) quote it;
    this is the friendlier form used where the phrase carries the whole message.
    """
    if not start or not end:
        return _period_label(start, end)
    try:
        s, e = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return _period_label(start, end)
    whole_months = s.day == 1 and e.day == calendar.monthrange(e.year, e.month)[1]
    if whole_months:
        if (s.year, s.month) == (e.year, e.month):
            return s.strftime("%B %Y")
        return f"{s.strftime('%B %Y')} to {e.strftime('%B %Y')}"
    # "this month" resolves to the 1st..today — a partial month, not a date range.
    if s.day == 1 and (s.year, s.month) == (e.year, e.month):
        return f"{s.strftime('%B %Y')} so far"
    return f"{_pretty_date(start)} to {_pretty_date(end)}"


def data_coverage(db: Client, user_id: str) -> dict[str, Optional[str]]:
    """The first and last transaction date the user actually has.

    Used to answer honestly when a question lands outside the imported range:
    "no transactions in June 2026" is far more useful than "you spent Rs 0".
    Selects only the date column (one small round-trip, no ordering) so any
    PostgREST-shaped client can serve it.
    """
    rows = (
        db.table("transactions")
        .select("date")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    dates = sorted(str(r["date"])[:10] for r in rows if r.get("date"))
    if not dates:
        return {"first": None, "last": None, "count": 0}
    return {"first": dates[0], "last": dates[-1], "count": len(dates)}


def empty_period_sentence(
    period: str, first: Optional[str], last: Optional[str]
) -> str:
    """The one wording for "that period is empty", shared by both chat paths
    (the deterministic answer and the agent's server-composed answer)."""
    if not first:
        return (
            "You have no transactions imported yet. Upload a bank or UPI statement "
            "and I'll show you exactly where your money went."
        )
    return (
        f"You have no transactions in {period} — nothing was imported for those "
        f"dates. Your data covers {_pretty_date(first)} to {_pretty_date(last)}, "
        "so ask me about a date in that range."
    )


def empty_period_answer(
    db: Client, user_id: str, start: Optional[str], end: Optional[str]
) -> str:
    """Honest answer for a period the user simply has no data in."""
    cov = data_coverage(db, user_id)
    return empty_period_sentence(_pretty_period(start, end), cov["first"], cov["last"])


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


def _wants_share(question: str) -> bool:
    """The question asks for a proportion, not just an amount."""
    q = question.lower()
    return any(w in q for w in ["percent", "percentage", "%", "share of", "proportion",
                                "what fraction", "how much of my"])


def _listing(headline: str, items: list[str], footer: str = "") -> str:
    """A headline, then one item per line, then an optional closing line.

    Line breaks survive the wire now (see ``_sse_pack``), so a breakdown reads as
    a scannable list instead of a run-on sentence. Multi-line answers skip
    ``rephrase`` — the structure IS the answer.
    """
    out = "\n".join([headline] + [f"• {i}" for i in items])
    return f"{out}\n{footer}" if footer else out


def _share(amount: float, total: float) -> str:
    """' (34%)' — the share of the total, omitted when it isn't meaningful."""
    if total <= 0:
        return ""
    pct = round(amount / total * 100)
    return f" · {pct}%" if pct >= 1 else ""


_COMPARE_WORDS = ["more", "less", "bigger", "higher", "lower", "than", "compare",
                  "versus", " vs ", "which"]


def _try_category_comparison(
    txns: list[dict], question: str, period: str
) -> Optional[str]:
    """"am I spending more on food than shopping" — compare two named categories.

    Returns None unless the question really names two of them AND asks to compare,
    so ordinary single-category questions are untouched.
    """
    q = question.lower()
    if not any(w in q for w in _COMPARE_WORDS):
        return None
    names = extract_categories(question)
    if len(names) < 2:
        return None
    a, b = names[0], names[1]
    spend = _spend_only(txns)

    def total_for(kw: str) -> tuple[float, int]:
        rows = [t for t in spend if kw in _category_name(t).lower()]
        return sum(float(t["amount"]) for t in rows), len(rows)

    a_total, a_n = total_for(a)
    b_total, b_n = total_for(b)
    if a_n == 0 and b_n == 0:
        return None  # neither is a real category here — let the normal path answer
    diff = abs(a_total - b_total)
    if a_total > b_total:
        verdict = f"{a} is higher, by {_rupees(diff)}"
    elif b_total > a_total:
        verdict = f"{b} is higher, by {_rupees(diff)}"
    else:
        verdict = "they're level"
    return (
        f"For {period}: {a} {_rupees(a_total)} ({a_n} "
        f"transaction{'s' if a_n != 1 else ''}) vs {b} {_rupees(b_total)} "
        f"({b_n}) — {verdict}."
    )


def _answer_total_by_category(txns: list[dict], question: str, period: str) -> str:
    spend = _spend_only(txns)
    if not spend:
        return f"I found no spending for {period}."

    # Two categories and a comparison word: answer the comparison, not just the first.
    comparison = _try_category_comparison(txns, question, period)
    if comparison:
        return comparison

    category = extract_category(question)
    if category:
        matched = [t for t in spend if category in _category_name(t).lower()]
        total = sum(float(t["amount"]) for t in matched)
        if not matched:
            return f"I found no spending tagged '{category}' for {period}."
        answer = (
            f"You spent {_rupees(total)} on {category} across {len(matched)} "
            f"transactions ({period})."
        )
        # "what percentage of my money goes to food" asks for a share, so give one
        # (the plain amount alone reads as a non-answer to that question).
        if _wants_share(question):
            grand = sum(float(t["amount"]) for t in spend)
            if grand > 0:
                answer += (
                    f" That's {round(total / grand * 100)}% of the "
                    f"{_rupees(grand)} you spent."
                )
        return answer

    totals: dict[str, float] = defaultdict(float)
    for t in spend:
        totals[_category_name(t)] += float(t["amount"])
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    grand = sum(totals.values())
    return _listing(
        f"For {period} you spent {_rupees(grand)} across {len(spend)} transactions. "
        "Top categories:",
        [f"{name} — {_rupees(amt)}{_share(amt, grand)}" for name, amt in top],
    )


def _answer_merchant_breakdown(txns: list[dict], period: str) -> str:
    spend = _spend_only(txns)
    if not spend:
        return f"I found no spending for {period}."

    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in spend:
        m = canonical_merchant(t.get("raw_merchant") or "Unknown")
        totals[m]["total"] += float(t["amount"])
        totals[m]["count"] += 1
    top = sorted(totals.items(), key=lambda kv: kv[1]["total"], reverse=True)[:5]
    grand = sum(v["total"] for v in totals.values())
    return _listing(
        f"Your top merchants for {period}:",
        [
            f"{name} — {_rupees(v['total'])}{_share(v['total'], grand)} "
            f"({int(v['count'])} payment{'s' if int(v['count']) != 1 else ''})"
            for name, v in top
        ],
    )


_MERCHANT_CONNECTORS = [" paid to ", " at ", " to ", " pay ", " paid ", " from ", " on ", " with "]


def _extract_merchant_target(question: str) -> Optional[str]:
    """Pull a merchant/person name out of 'spend at X' / 'pay X' / 'to X'."""
    q = question.lower().strip(" ?.!")
    for c in _MERCHANT_CONNECTORS:
        if c in q:
            cand = q.split(c, 1)[1].strip()
            cand = re.split(r"\b(last|this|in|during|for|over|between|month|year)\b", cand)[0]
            cand = cand.strip(" ?.!")
            if len(cand) >= 3:
                return cand
    return None


def _try_merchant_spend(
    db: Client, user_id: str, question: str, start: Optional[str], end: Optional[str]
) -> Optional[str]:
    """Answer 'how much did I spend at/pay <merchant>' by matching raw_merchant.
    Returns None if no merchant is named or nothing matches (let other handlers try)."""
    from app.services.merchant import BRAND_NAMES

    target = _extract_merchant_target(question)
    if not target:
        return None
    # Fetch the period's rows and match by literal substring OR — when the target
    # is a known brand — by its canonical name, so "swiggy" also catches
    # BundlTechnologies/SwiggyInstamart, not just the strings containing "swiggy".
    q = (
        db.table("transactions").select("amount,raw_merchant")
        .eq("user_id", user_id).eq("is_transfer", False)
    )
    if start:
        q = q.gte("date", start)
    if end:
        q = q.lte("date", end)
    all_rows = q.execute().data or []

    tl = target.lower()
    canon = canonical_merchant(target)
    brand = canon if canon in BRAND_NAMES else None
    rows = [
        r for r in all_rows
        if tl in (r.get("raw_merchant") or "").lower()
        or (brand and canonical_merchant(r.get("raw_merchant") or "") == brand)
    ]
    if not rows:
        return None
    spend = [r for r in rows if float(r.get("amount") or 0) >= 0]
    total = sum(float(r["amount"]) for r in spend)
    display = brand or (
        sorted({r["raw_merchant"] for r in rows if r.get("raw_merchant")})[0]
        if len({r.get("raw_merchant") for r in rows}) == 1
        else f"merchants matching '{target}'"
    )
    return f"You spent {_rupees(total)} at {display} across {len(spend)} transactions."


def _is_biggest_query(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in ["biggest", "largest", "highest", "most expensive",
                                "top transaction", "biggest expense", "biggest purchase"])


def _answer_biggest(txns: list[dict], period: str) -> str:
    spend = sorted(_spend_only(txns), key=lambda t: float(t["amount"]), reverse=True)
    if not spend:
        return f"I found no spending for {period}."
    return _listing(
        f"Your biggest expenses for {period}:",
        [
            f"{_rupees(float(t['amount']))} — {t.get('raw_merchant') or 'Unknown'}"
            f"{' on ' + _pretty_date(str(t['date'])) if t.get('date') else ''}"
            for t in spend[:3]
        ],
    )


def _is_received_query(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in ["get back", "got back", "received", "refund",
                                "money back", "paid me", "sent me", "come in", "came in"])


def _answer_received(txns: list[dict], period: str) -> str:
    total = sum(-float(t["amount"]) for t in txns if float(t.get("amount") or 0) < 0)
    n = sum(1 for t in txns if float(t.get("amount") or 0) < 0)
    if n == 0:
        return f"You didn't receive anything for {period}."
    return f"You received {_rupees(total)} across {n} transactions ({period})."


def _is_average_query(question: str) -> bool:
    """A request for the typical monthly spend / run-rate."""
    q = question.lower()
    return any(w in q for w in ["average", "avg", "run rate", "run-rate", "on average"])


def _is_capability_query(question: str) -> bool:
    """"help" / "what can you do" — a request for the menu, not for a figure."""
    q = question.lower().strip(" ?.!")
    if q in {"help", "?", "what can you do", "what can i ask", "menu", "commands"}:
        return True
    return any(w in q for w in ["what can you do", "what can i ask", "how do i use you",
                                "what do you know", "who are you", "what are you"])


def _answer_capabilities() -> str:
    """The menu. Cheap to keep honest: every line here is a real handler above."""
    return _listing(
        "I answer from your imported statements, and I can change things too. Try:",
        [
            "\"how much did I spend on food in May?\" — any category, any period",
            "\"where did my money go?\" — top categories or merchants",
            "\"what do I buy most often?\" — your habits",
            "\"what was my biggest expense?\"",
            "\"did I spend more this month than last?\"",
            "\"what jumped this month?\" · \"what's my average monthly spend?\"",
            "\"how much did I pay Priya?\" — any merchant or person",
            "\"put all my Amazon purchases under Shopping\" — I'll relabel them",
            "\"rename Rnt to Rent\" · \"merge Rnt into Rent\" · \"set Rent's icon to 🏠\"",
        ],
    )


def _is_coverage_query(question: str) -> bool:
    """Questions about the DATA rather than the money — how much is loaded, since
    when. Previously answered with an unrelated spend summary."""
    q = question.lower()
    return any(w in q for w in [
        "how many transactions", "how much data", "what data do you have",
        "when did i start", "how far back", "what period do you have",
        "what dates", "date range", "how many payments do i have",
    ])


def _answer_coverage(db: Client, user_id: str) -> str:
    cov = data_coverage(db, user_id)
    if not cov["first"]:
        return (
            "You have no transactions imported yet. Upload a bank or UPI statement "
            "and I'll show you exactly where your money went."
        )
    return (
        f"I have {cov['count']} transactions, from {_pretty_date(cov['first'])} to "
        f"{_pretty_date(cov['last'])}. Ask me about anything in that range."
    )


def _is_daily_average_query(question: str) -> bool:
    """'how much do I spend a day' — the same question in a different unit, which
    used to be answered with a monthly figure."""
    q = question.lower()
    return any(w in q for w in ["per day", "a day", "each day", "daily", "every day"])


def _answer_daily_average(db: Client, user_id: str) -> str:
    """Average spend per day across the days the statements actually cover."""
    txns = _fetch_transactions(db, user_id, None, None)
    spend = _spend_only(txns)
    dates = sorted({str(t.get("date") or "")[:10] for t in spend if t.get("date")})
    if not dates:
        return "I don't have any spending yet to work out a daily average."
    total = sum(float(t["amount"]) for t in spend)
    try:
        days = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1
    except ValueError:
        days = len(dates)
    days = max(days, 1)
    return (
        f"You spend about {_rupees(total / days)} a day — {_rupees(total)} over the "
        f"{days} days from {_pretty_date(dates[0])} to {_pretty_date(dates[-1])}."
    )


def _answer_average(db: Client, user_id: str) -> str:
    """Average monthly spend across the user's whole history, with the peak month."""
    txns = _fetch_transactions(db, user_id, None, None)
    monthly: dict[str, float] = defaultdict(float)
    for t in txns:
        amt = float(t.get("amount") or 0)
        if amt <= 0:  # spends only
            continue
        ym = str(t.get("date") or "")[:7]  # YYYY-MM
        if len(ym) == 7:
            monthly[ym] += amt
    if not monthly:
        return "I don't have enough spending history yet to work out a monthly average."
    avg = sum(monthly.values()) / len(monthly)
    hi_month, hi_val = max(monthly.items(), key=lambda kv: kv[1])
    n = len(monthly)
    return (
        f"You spend about {_rupees(avg)}/month on average across {n} "
        f"month{'s' if n != 1 else ''} (highest was {_rupees(hi_val)} in "
        f"{_pretty_month(hi_month)})."
    )


def _is_monthly_breakdown_query(question: str) -> bool:
    """A request for spend PER MONTH, month by month.

    From a real trace: "so what does my spending month wise look like" took the
    agent 78 seconds and came back with the average and the peak month — no tool
    could answer the actual question, so the model picked the nearest thing.
    "average"/"run rate" wording means they want the single figure instead.
    """
    q = question.lower()
    if any(w in q for w in ["average", "avg", "run rate", "run-rate"]):
        return False
    return any(w in q for w in [
        "month wise", "month-wise", "monthwise", "month by month", "by month",
        "each month", "every month", "per month", "monthly breakdown",
        "monthly spending", "monthly spend", "spending by month", "months",
    ])


def monthly_spending(txns: list[dict]) -> list[tuple[str, float]]:
    """Spend per calendar month, oldest first. Shared by the chat answer and the
    agent tool so both report the same figures."""
    monthly: dict[str, float] = defaultdict(float)
    for t in _spend_only(txns):
        ym = str(t.get("date") or "")[:7]
        if len(ym) == 7:
            monthly[ym] += float(t.get("amount") or 0)
    return sorted(monthly.items())


def _answer_monthly_breakdown(db: Client, user_id: str) -> str:
    """Every month with its total — the shape of the year, not one average."""
    months = monthly_spending(_fetch_transactions(db, user_id, None, None))
    if not months:
        return "You have no spending imported yet, so there's nothing to break down."
    peak = max(months, key=lambda kv: kv[1])
    total = sum(v for _, v in months)
    return _listing(
        f"Your spending month by month ({_rupees(total)} in total):",
        [f"{_pretty_month(ym)} — {_rupees(amt)}" for ym, amt in months],
        footer=(
            f"Biggest month: {_pretty_month(peak[0])} at {_rupees(peak[1])}."
            if len(months) > 1
            else ""
        ),
    )


def _is_change_query(question: str) -> bool:
    """A request for what rose the most vs last month."""
    q = question.lower()
    return any(w in q for w in [
        "what jumped", "what went up", "what increased", "what rose", "what spiked",
        "what grew", "biggest change", "changed the most", "spending jump",
        "went up this month", "jumped this month",
    ])


def _answer_what_jumped(db: Client, user_id: str) -> str:
    """The category whose spend rose the most between the two most recent months."""
    from app.services.movers import compute_category_movers

    result = compute_category_movers(_fetch_transactions(db, user_id, None, None))
    if result is None:
        return "I need at least two months of spending to compare — not enough history yet."
    prev, latest = _pretty_month(result["prev"]), _pretty_month(result["latest"])
    top = result["movers"][0]
    if top["delta"] <= 0:
        return (
            f"Nothing rose from {prev} to {latest} — your spending was flat or down "
            "across every category."
        )
    return (
        f"Your biggest increase from {prev} to {latest} was {top['category']}: up "
        f"{_rupees(top['delta'])} (from {_rupees(top['from_amount'])} to {_rupees(top['to_amount'])})."
    )


def _is_recurring_query(question: str) -> bool:
    """A request to LIST recurring/subscription payments (not 'how much on
    subscriptions', which is a category-spend question)."""
    q = question.lower()
    if "recurring" in q or "regular payment" in q:
        return True
    if "subscription" in q:
        return not any(w in q for w in ["how much", "how many", "total"])
    return False


def _answer_recurring(db: Client, user_id: str) -> str:
    """List the merchants charged on a regular monthly cadence (subscriptions,
    rent, memberships) across the user's whole history."""
    from app.services.recurring import detect_recurring

    txns = _fetch_transactions(db, user_id, None, None)  # whole history
    items = detect_recurring(txns)
    if not items:
        return (
            "I couldn't spot any clearly recurring payments yet — I look for the "
            "same merchant charged at a regular monthly cadence for a similar amount."
        )
    total = sum(i["monthly"] for i in items)
    return _listing(
        f"You have {len(items)} recurring payment"
        f"{'s' if len(items) != 1 else ''}, about {_rupees(total)} a month:",
        [
            f"{i['merchant']} — ~{_rupees(i['monthly'])}/mo ({i['count']} charges)"
            for i in items[:8]
        ],
    )


def _is_habit_query(question: str) -> bool:
    """A request for what you buy OFTEN (frequency), not what cost the most."""
    q = question.lower()
    return any(w in q for w in [
        "habit", "most often", "most frequent", "frequently", "how often",
        "buy the most", "small purchases", "little purchases", "adds up",
        "add up", "regularly buy", "keep buying", "keep spending",
    ])


def _answer_habits(db: Client, user_id: str) -> str:
    """The merchants paid most often — small spends that quietly add up."""
    from app.services.habits import detect_habits

    items = detect_habits(_fetch_transactions(db, user_id, None, None))
    if not items:
        return (
            "No merchant shows up often enough yet to call it a habit — I look for "
            "the same place paid at least five times."
        )
    # No combined total in the headline: on real data one big-ticket merchant can
    # dominate the sum, which would make an "it all adds up in small amounts"
    # claim false. Frequency is the finding; each row carries its own money.
    return _listing(
        "The places you pay most often:",
        [
            f"{i['merchant']} — {i['count']} payments, {_rupees(i['total'])} "
            f"(~{_rupees(i['avg'])} each, about {i['per_month']:g}/month)"
            for i in items
        ],
    )


def _answer_open_ended(txns: list[dict], period: str) -> str:
    total_spent = sum(float(t["amount"]) for t in _spend_only(txns))
    total_received = sum(-float(t["amount"]) for t in txns if float(t.get("amount") or 0) < 0)
    net = total_received - total_spent
    # "net Rs -275,388" makes a reader do the sign in their head; say it in words.
    verdict = (
        f"you're down {_rupees(-net)}" if net < 0
        else f"you're up {_rupees(net)}" if net > 0
        else "you broke even"
    )
    return (
        f"For {period}: you spent {_rupees(total_spent)} and received "
        f"{_rupees(total_received)} across {len(txns)} transactions — "
        f"{verdict}."
    )


def _answer_comparison(db: Client, user_id: str, question: str) -> str:
    """Compare spending between two periods named in the question."""
    parsed = parse_two_periods(question)
    if not parsed:
        # Couldn't resolve two periods — degrade to the normal, CATEGORY-AWARE
        # single-period answer (not a bare summary, which would drop a named
        # category like "food").
        start, end = parse_period(question)
        return _answer_total_by_category(
            _fetch_transactions(db, user_id, start, end), question,
            _period_label(start, end),
        )
    (a_start, a_end), (b_start, b_end) = parsed
    a_txns = _fetch_transactions(db, user_id, a_start, a_end)
    b_txns = _fetch_transactions(db, user_id, b_start, b_end)
    a_spend = sum(float(t["amount"]) for t in _spend_only(a_txns))
    b_spend = sum(float(t["amount"]) for t in _spend_only(b_txns))
    a_label, b_label = _pretty_period(a_start, a_end), _pretty_period(b_start, b_end)

    # Empty periods: say so plainly rather than "Rs 0, same in both", which reads
    # as broken when the user simply has no data imported for those dates.
    if not a_txns and not b_txns:
        cov = data_coverage(db, user_id)
        both = f"{_pretty_period(a_start, a_end)} or {_pretty_period(b_start, b_end)}"
        return empty_period_sentence(both, cov["first"], cov["last"])
    if not a_txns:
        return f"No transactions for {a_label}. {b_label}: you spent {_rupees(b_spend)}."
    if not b_txns:
        return f"{a_label}: you spent {_rupees(a_spend)}. No transactions for {b_label}."

    diff = a_spend - b_spend
    if diff > 0:
        verdict = f"{_rupees(diff)} more in the first"
    elif diff < 0:
        verdict = f"{_rupees(-diff)} more in the second"
    else:
        verdict = "the same in both"
    return (
        f"{a_label}: {_rupees(a_spend)}. {b_label}: {_rupees(b_spend)}. "
        f"You spent {verdict}."
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

    if _is_recurring_query(question):
        return _answer_recurring(db, user_id)

    if _is_habit_query(question):
        return _answer_habits(db, user_id)

    if _is_capability_query(question):
        return _answer_capabilities()

    if _is_coverage_query(question):
        return _answer_coverage(db, user_id)

    if _is_average_query(question):
        # "per day" and "per month" are different questions, same keyword.
        if _is_daily_average_query(question):
            return _answer_daily_average(db, user_id)
        return _answer_average(db, user_id)

    if _is_monthly_breakdown_query(question):
        return _answer_monthly_breakdown(db, user_id)

    if _is_daily_average_query(question) and "spend" in question.lower():
        return _answer_daily_average(db, user_id)

    if _is_change_query(question):
        return _answer_what_jumped(db, user_id)

    if intent == IntentType.PERIOD_COMPARISON:
        return _answer_comparison(db, user_id, question)

    start, end = parse_period(question)
    period = _pretty_period(start, end)  # "March 2026", not "2026-03-01 to 2026-03-31"
    txns = _fetch_transactions(db, user_id, start, end)

    # A bounded period with nothing in it: say the period is empty and name the
    # range that isn't, instead of reporting "Rs 0" as if it were the answer.
    if not txns and (start or end):
        return empty_period_answer(db, user_id, start, end)

    if _is_biggest_query(question):
        return _answer_biggest(txns, period)

    if intent == IntentType.MERCHANT_BREAKDOWN:
        return _answer_merchant_breakdown(txns, period)
    if intent == IntentType.TOTAL_BY_CATEGORY:
        if _is_received_query(question):
            return _answer_received(txns, period)
        # "spend at/to/pay <merchant>" when no category was named.
        if not extract_category(question):
            merchant_ans = _try_merchant_spend(db, user_id, question, start, end)
            if merchant_ans:
                return merchant_ans
        return _answer_total_by_category(txns, question, period)
    return _answer_open_ended(txns, period)


async def rephrase(question: str, deterministic_answer: str) -> str:
    """Rephrase a computed answer conversationally via the shared LLM client.

    The numbers are already computed and correct; the LLM only reshapes tone. If
    no provider is configured or the call fails/looks unsafe, we return the
    deterministic answer unchanged so the feature never regresses.
    """
    if not deterministic_answer or not llm_client.is_available():
        return deterministic_answer

    # A multi-line answer is a deliberately structured listing (headline + one
    # item per line). Asking the model for "one or two natural sentences" would
    # flatten exactly the shape that makes it readable — so return it verbatim.
    if "\n" in deterministic_answer:
        return deterministic_answer

    prompt = (
        "You are a friendly personal-finance assistant. Rephrase the answer below "
        "in one or two natural sentences. You MUST keep every number, currency "
        "figure and name EXACTLY as given — do not do any arithmetic, do not add "
        "or invent figures. Reply with only the rephrased answer.\n\n"
        f"User asked: {question}\n"
        f"Answer to rephrase: {deterministic_answer}"
    )
    try:
        out = (await llm_client.acomplete(prompt, max_tokens=200)).strip()
    except Exception as e:  # LLMUnavailable or transport error -> safe fallback
        logger.warning("chat rephrase fell back to deterministic answer: %s", e)
        return deterministic_answer

    # Guardrail: every rupee figure in the computed answer must survive verbatim,
    # otherwise the model altered the numbers — reject and keep the safe version.
    figures = re.findall(r"Rs\s-?[\d,]+", deterministic_answer)
    if not out or any(f not in out for f in figures):
        logger.warning("chat rephrase dropped/altered figures; using deterministic answer")
        return deterministic_answer
    return out


def _sse_pack(text: str):
    """Yield ``text`` as SSE ``data:`` events, one whitespace-delimited token at a
    time. Splitting on tokens keeps each event single-line so the frontend's
    line-based parser stays correct; a trailing space rejoins them on the client.

    A raw newline would break SSE line framing, so line breaks travel as the
    two-character escape ``\\n`` in their own event; the client turns that back
    into a real line break. That's what lets an answer be a list instead of one
    run-on sentence.
    """
    for i, line in enumerate(text.split("\n")):
        if i:
            yield "data: \\n\n\n"
        for token in line.split():
            yield f"data: {token} \n\n"


def _record_trace(
    db: Client, user_id: str, question: str, steps: list[dict[str, Any]],
    answer: str, source: str, error: str | None, duration_ms: int,
) -> None:
    """Persist one chat turn to ``chat_traces`` for observability. Best-effort:
    tracing must never break the chat, so failures are swallowed (logged)."""
    action_taken = any(
        isinstance(s.get("result"), dict) and "action" in s["result"] for s in steps
    )
    # Bound what we persist per turn (tool results are already row-capped at
    # _MAX_ROWS; this caps the number of steps so one turn can't bloat the table).
    stored_steps = steps[:8]
    try:
        db.table("chat_traces").insert({
            "user_id": user_id,
            "question": question,
            "steps": stored_steps,
            "answer": answer,
            "source": source,
            "action_taken": action_taken,
            "error": error,
            "duration_ms": duration_ms,
        }).execute()
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("failed to record chat trace: %s", e)


# Deterministic action parsing — so "categorize my amazon as shopping" WORKS even
# with no LLM configured (the action executors are deterministic; only intent
# parsing needed the model). Keeps the Palantir "tell it and it does it" promise
# on the keyless path.
_CATEGORIZE_RE = re.compile(
    r"\b(?:put|move|categori[sz]e|label|classif|mark|tag|file)\w*\s+"
    r"(?:all\s+)?(?:my\s+|the\s+)?(?P<merchant>.+?)\s+"
    r"(?:as|under|in|into|to)\s+(?P<category>.+?)[.!?]*\s*$",
    re.IGNORECASE,
)
_CREATE_CAT_RE = re.compile(
    r"\bcreate\s+(?:a\s+)?(?:new\s+)?categor(?:y|ies)\s+"
    r"(?:called\s+|named\s+)?(?P<name>.+?)[.!?]*\s*$",
    re.IGNORECASE,
)
# "rename Rnt to Rent", "rename the category Food to Groceries", "rename my
# Petrol category to Fuel". `rename` isn't a word normal finance questions use,
# so gating on it + a trailing `to` keeps mis-parse risk low.
_RENAME_CAT_RE = re.compile(
    r"\brename\s+(?:the\s+|my\s+)?(?:categor(?:y|ies)\s+)?"
    r"(?P<old>.+?)\s+(?:categor(?:y|ies)\s+)?to\s+(?P<new>.+?)[.!?]*\s*$",
    re.IGNORECASE,
)
# "set the icon for Rent to 🏠", "change Rent's emoji to 🏠", "set Rent icon to 🏠".
# Gated on the icon/emoji keyword so it can't swallow other commands.
_SET_ICON_RE = re.compile(
    r"\b(?:set|change|update)\s+(?:the\s+)?(?:icon|emoji)\s+(?:for\s+|of\s+|on\s+)?"
    r"(?P<name>.+?)\s+to\s+(?P<icon>\S+)[.!?]*\s*$",
    re.IGNORECASE,
)
_SET_ICON_POSSESSIVE_RE = re.compile(
    r"\b(?:set|change|update)\s+(?:the\s+)?(?P<name>.+?)(?:'s|s')?\s+"
    r"(?:icon|emoji)\s+to\s+(?P<icon>\S+)[.!?]*\s*$",
    re.IGNORECASE,
)
# "delete the Rent category" / "remove my Rent category". Requires the word
# "category", so "remove my food spending" won't match.
_DELETE_CAT_RE = re.compile(
    r"\b(?:delete|remove)\s+(?:the\s+|my\s+)?(?P<name>.+?)\s+categor(?:y|ies)[.!?]*\s*$",
    re.IGNORECASE,
)
# "delete category Rent" / "remove the category called Rent".
_DELETE_CAT_RE2 = re.compile(
    r"\b(?:delete|remove)\s+(?:the\s+|my\s+)?categor(?:y|ies)\s+"
    r"(?:called\s+|named\s+)?(?P<name>.+?)[.!?]*\s*$",
    re.IGNORECASE,
)
# "merge Rnt into Rent" / "merge the Misc category into Other". Gated on both
# "merge" and "into", so it can't swallow other commands.
_MERGE_CAT_RE = re.compile(
    r"\bmerge\s+(?:the\s+|my\s+)?(?P<source>.+?)\s+(?:categor(?:y|ies)\s+)?"
    r"into\s+(?P<target>.+?)[.!?]*\s*$",
    re.IGNORECASE,
)


def try_action(
    question: str, user_id: str, db: Client,
    trace: Optional[list[dict[str, Any]]] = None,
) -> Optional[str]:
    """If the question is a data-change request, execute it deterministically and
    return a server-composed confirmation. Returns None if it isn't an action.

    Reuses the same executors and confirmation text as the LLM agent, so keyless
    and AI paths behave identically. Category names are matched against the user's
    real categories to avoid acting on a misread token. When ``trace`` is given,
    the executed step is appended (so ``/chat/traces`` records the mutation).
    """
    from app.services import chat_tools
    from app.services.chat_agent import _action_confirmation

    q = question.strip()

    def _run(tool: str, args: dict, result: dict) -> str:
        if trace is not None:
            trace.append({"tool": tool, "args": args, "result": result})
        return _action_confirmation([{"tool": tool, "result": result}])

    m = _RENAME_CAT_RE.search(q)
    if m:
        old_name = m.group("old").strip().strip("\"'")
        new_name = m.group("new").strip().strip("\"'")
        res = chat_tools.rename_category(
            db, user_id, old_name=old_name, new_name=new_name
        )
        return _run(
            "rename_category", {"old_name": old_name, "new_name": new_name}, res
        )

    m = _SET_ICON_RE.search(q) or _SET_ICON_POSSESSIVE_RE.search(q)
    if m:
        name = m.group("name").strip().strip("\"'")
        icon = m.group("icon").strip()
        res = chat_tools.set_category_icon(db, user_id, name=name, icon=icon)
        return _run("set_category_icon", {"name": name, "icon": icon}, res)

    m = _MERGE_CAT_RE.search(q)
    if m:
        source = m.group("source").strip().strip("\"'")
        target = m.group("target").strip().strip("\"'")
        res = chat_tools.merge_categories(db, user_id, source=source, target=target)
        return _run("merge_categories", {"source": source, "target": target}, res)

    m = _DELETE_CAT_RE.search(q) or _DELETE_CAT_RE2.search(q)
    if m:
        name = m.group("name").strip().strip("\"'")
        res = chat_tools.delete_category(db, user_id, name=name)
        return _run("delete_category", {"name": name}, res)

    m = _CREATE_CAT_RE.search(q)
    if m:
        name = m.group("name").strip().strip("\"'")
        res = chat_tools.create_category(db, user_id, name=name)
        return _run("create_category", {"name": name}, res)

    m = _CATEGORIZE_RE.search(q)
    if m:
        merchant = m.group("merchant").strip().strip("\"'")
        category = m.group("category").strip().strip("\"'")
        # Only treat as an action when the stated category actually exists AND is
        # assignable — else it's probably a normal question, not a command.
        # "Other" is the bucket we empty, never a target (would poison learning).
        cats = chat_tools._visible_categories(db, user_id)
        match = next(
            (c for c in cats
             if c["name"].lower() == category.lower() and c["name"] != "Other"),
            None,
        )
        if not match:
            return None
        res = chat_tools.categorize_merchant(
            db, user_id, merchant=merchant, category=match["name"]
        )
        return _run(
            "categorize_merchant",
            {"merchant": merchant, "category": match["name"]}, res,
        )

    return None


# Question shapes answered deterministically even when an LLM IS available.
#
# Everything in this tuple has a dedicated handler that is strictly better than
# asking the model: it returns a verified structured answer in ~200ms instead of
# ~6s, and in two cases the agent has no tool that could answer at all — nothing
# exposes data coverage ("how many transactions do I have"), and the only average
# tool is monthly, so "per day" would come back in the wrong unit. General
# "how much did I spend on X in Y" questions are NOT here: the model handles
# arbitrary phrasing and typos better, and its figures are tool-verified.
_DETERMINISTIC_FIRST = (
    _is_capability_query,
    _is_coverage_query,
    _is_habit_query,
    _is_recurring_query,
    _is_change_query,
    _is_average_query,        # includes the per-day variant
    _is_daily_average_query,
    _is_monthly_breakdown_query,
    _is_biggest_query,
    _is_received_query,
)


def _is_merchant_ranking(question: str) -> bool:
    """"which merchants did I spend the most at" / "where did my money go" — the
    tool does all the work and our listing (with % share) beats model prose."""
    return classify_intent(question) == IntentType.MERCHANT_BREAKDOWN


def prefers_deterministic(question: str) -> bool:
    """True when a dedicated handler beats the model for this question shape.

    Measured against the live model, not assumed: "which merchants did I spend the
    most at" took 68s through the agent and came back as a comma-run of the same
    tool output; "what was my biggest expense" 4.9s. The deterministic answers are
    listings with shares, computed in ~200ms.
    """
    if any(matches(question) for matches in _DETERMINISTIC_FIRST):
        return True
    if _is_merchant_ranking(question):
        return True
    # "how much did I spend at dmart" — the deterministic lookup is brand-aware
    # (DMart is stored as AVENUESUPERMARTS), which is exactly where the model's
    # keyword search answered "Rs 0".
    #
    # Gated tightly on purpose: _extract_merchant_target splits on connectives as
    # loose as " to " and " on ", so without a spend verb "what happened to my
    # money" would be captured as a merchant lookup for "my money". A named
    # category also disqualifies it, so "how much on food at restaurants" stays a
    # category question.
    if (
        re.search(r"\b(?:spend|spent|spending|pay|paid|cost|costs)\b", question.lower())
        and _extract_merchant_target(question)
        and not extract_category(question)
    ):
        return True
    return False


async def _resolve_answer(question: str, user_id: str, db: Client) -> str:
    """Answer a question: try the agentic path, fall back to the deterministic one.

    The agent (``chat_agent.run_agent``) lets the LLM plan tool calls over the
    user's real data. If no LLM is configured or the loop can't produce an answer,
    we fall back to the keyword-based deterministic ``answer_question`` (optionally
    rephrased) so the feature never regresses to an error.

    A narrow set of question shapes (``prefers_deterministic``) skips the model
    entirely — see the note on ``_DETERMINISTIC_FIRST``.

    Every turn is recorded to ``chat_traces`` (question, tool steps, answer, how it
    was produced) so we can inspect *why* the chat said what it did.
    """
    # Imported lazily to avoid a circular import (chat_tools imports from here).
    from app.services import chat_agent

    steps: list[dict[str, Any]] = []
    source = "agent"
    error: str | None = None
    started = time.monotonic()

    def _instant(answer: str) -> str:
        # No rephrase: these answers are menus and structured listings, and the
        # model's job here would only be to make them worse.
        _record_trace(
            db, user_id, question, steps, answer, "instant", None,
            int((time.monotonic() - started) * 1000),
        )
        return answer

    if prefers_deterministic(question):
        return _instant(answer_question(question, user_id, db))

    # A question about a period with NO data needs no model: the answer is "that
    # period is empty, here's the range that isn't". A real trace shows the user
    # waiting 26 seconds for exactly that ("what is the current spending last
    # month?" — the data ends May 2026), and the model can only get it wrong.
    p_start, p_end = parse_period(question)
    if (p_start or p_end) and not _fetch_transactions(db, user_id, p_start, p_end):
        return _instant(empty_period_answer(db, user_id, p_start, p_end))

    async def _fallback() -> str:
        # Actions work deterministically even with no LLM. Their confirmation is
        # server-composed from the real result, so it's returned VERBATIM (never
        # through rephrase, whose figure-guard is vacuous for count-only text and
        # could let the model restate the count). Records the step for the trace.
        act = try_action(question, user_id, db, trace=steps)
        if act is not None:
            return act
        return await rephrase(question, answer_question(question, user_id, db))

    try:
        answer = await chat_agent.run_agent(question, user_id, db, trace=steps)
    except chat_agent.AgentUnavailable as e:
        logger.info("chat agent unavailable, using deterministic path: %s", e)
        source, error = "deterministic", str(e)
        answer = await _fallback()
    except Exception as e:
        logger.warning("chat agent errored, using deterministic path: %s", e)
        source, error = "error-fallback", str(e)
        try:
            answer = await _fallback()
        except Exception as e2:
            # The turn failed outright. Record it — this is the failure we most
            # want to see in /chat/traces, and it used to leave no trace at all.
            logger.exception("chat fallback failed")
            answer = (
                "Sorry, I couldn't work that out just now. Try asking a slightly "
                "different way."
            )
            _record_trace(
                db, user_id, question, steps, answer, "failed",
                f"{e} | fallback: {e2}",
                int((time.monotonic() - started) * 1000),
            )
            return answer

    _record_trace(
        db, user_id, question, steps, answer, source, error,
        int((time.monotonic() - started) * 1000),
    )
    return answer


def _save_messages(db: Client, user_id: str, question: str, answer: str) -> None:
    """Persist the turn (user question + assistant answer) so history survives a
    reload. Best-effort and user-scoped; two inserts to keep them ordered."""
    try:
        db.table("chat_messages").insert(
            {"user_id": user_id, "role": "user", "content": question}
        ).execute()
        db.table("chat_messages").insert(
            {"user_id": user_id, "role": "assistant", "content": answer}
        ).execute()
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("failed to save chat messages: %s", e)


def _sse_status(text: str) -> str:
    """A named SSE event, so the client can show progress without it landing in
    the answer text. Single-line payload, same framing rules as ``_sse_pack``."""
    return f"event: status\ndata: {text}\n\n"


# What to say while the model is working, and how long to wait before saying the
# next thing. Measured against the live free model: ~5s typical, 68s worst — long
# enough that three bouncing dots read as "broken" rather than "thinking".
_PROGRESS_STEPS: list[tuple[float, str]] = [
    (0.0, "Reading your transactions…"),
    (2.5, "Working out the numbers…"),
    (7.0, "Double-checking the figures…"),
    (18.0, "Still going — the free model is slow today…"),
]


async def stream_chat_response(question: str, user_id: str, db: Client):
    """Stream a chat answer as Server-Sent Events.

    Progress is streamed as ``event: status`` while the answer is being resolved;
    the answer itself streams as plain ``data:`` events exactly as before, so the
    two can't be confused. An instant answer (see ``prefers_deterministic``)
    resolves before the first status is due and simply never sends one.
    """
    task = asyncio.create_task(_resolve_answer(question, user_id, db))

    def _drain(t: "asyncio.Task[str]") -> None:
        """If the client disconnects, nobody awaits this task — retrieve any
        exception so asyncio doesn't log it as never-retrieved. The turn is left
        to finish rather than cancelled, so a write action the user already asked
        for still completes and still lands in chat_traces."""
        if not t.cancelled() and t.exception() is not None:
            logger.warning("chat turn failed after the client went away: %s", t.exception())

    task.add_done_callback(_drain)

    for delay, text in _PROGRESS_STEPS:
        done, _ = await asyncio.wait({task}, timeout=delay)
        if done:
            break
        yield _sse_status(text)

    try:
        answer = await task
    except Exception as e:  # pragma: no cover - defensive, surfaced to the user
        answer = f"Sorry, I couldn't answer that right now ({e})."

    _save_messages(db, user_id, question, answer)

    for event in _sse_pack(answer):
        yield event
