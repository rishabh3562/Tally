"""Spending habits: the merchants you pay OFTEN.

Complements two existing detectors that miss this shape of spending entirely:
``recurring.py`` wants a steady monthly cadence with consistent amounts (a
subscription), and top-merchants ranks by total (one big purchase wins). Neither
surfaces "you tapped the office canteen 28 times for Rs 2,268" — small, frequent,
invisible, and exactly what "where did my money go" is really asking.

Read-only and deterministic: it counts, it doesn't guess.
"""

import datetime
from collections import defaultdict
from typing import Any

from app.services.merchant import canonical_merchant

_DAYS_PER_MONTH = 30.44


def _parse_date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def detect_habits(
    txns: list[dict], *, min_count: int = 5, limit: int = 8
) -> list[dict]:
    """Merchants paid at least ``min_count`` times, most frequent first.

    Each item: {merchant, count, total, avg, per_month, first, last}. ``per_month``
    is the rate over the span the payments actually cover (not the whole history),
    so a habit that started last month isn't diluted by older statements.
    """
    by_merchant: dict[str, list[tuple[datetime.date, float]]] = defaultdict(list)
    for t in txns:
        amt = float(t.get("amount") or 0)
        if amt <= 0:  # spends only (positive = outflow in this app)
            continue
        d = _parse_date(t.get("date"))
        if d is None:
            continue
        by_merchant[canonical_merchant(t.get("raw_merchant") or "Unknown")].append(
            (d, amt)
        )

    out: list[dict] = []
    for merchant, entries in by_merchant.items():
        if len(entries) < min_count:
            continue
        entries.sort(key=lambda e: e[0])
        dates = [d for d, _ in entries]
        total = sum(a for _, a in entries)
        span_days = (dates[-1] - dates[0]).days
        # A burst inside one month is still "many times a month", so floor the
        # span at a month rather than dividing by ~0 and claiming 100/month.
        months = max(span_days / _DAYS_PER_MONTH, 1.0)
        out.append({
            "merchant": merchant,
            "count": len(entries),
            "total": round(total, 2),
            "avg": round(total / len(entries), 2),
            "per_month": round(len(entries) / months, 1),
            "first": dates[0].isoformat(),
            "last": dates[-1].isoformat(),
        })

    # Most frequent first — frequency IS the finding; total breaks ties.
    out.sort(key=lambda r: (r["count"], r["total"]), reverse=True)
    return out[:limit]
