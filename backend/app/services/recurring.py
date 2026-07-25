"""Recurring-payment (subscription) detection.

Read-only, deterministic — finds merchants charged on a regular ~monthly cadence
with similar amounts (Netflix, rent, a gym), independent of category. Conservative
on purpose: it would rather miss a subscription than wrongly claim one, so it
requires both a regular monthly gap AND consistent amounts.

Not just the known-brand "Subscriptions" category — this catches ANY merchant the
user is quietly paying every month.
"""

import datetime
from collections import defaultdict
from statistics import median
from typing import Any

from app.services.merchant import canonical_merchant

# A monthly cadence, with slack for short/long months and a few days' drift.
_MIN_GAP_DAYS = 24
_MAX_GAP_DAYS = 35


def _parse_date(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def detect_recurring(txns: list[dict], *, min_occurrences: int = 3) -> list[dict]:
    """Return recurring monthly payments, biggest monthly cost first.

    Each item: {merchant, avg_amount, monthly, count, cadence_days}. A merchant
    qualifies when it has >= ``min_occurrences`` spends whose consecutive gaps are
    all close to a ~monthly median and whose amounts sit within ~25% of the median.
    """
    by_merchant: dict[str, list[tuple[datetime.date, float]]] = defaultdict(list)
    for t in txns:
        amt = float(t.get("amount") or 0)
        if amt <= 0:  # spends only (positive = outflow in this app)
            continue
        d = _parse_date(t.get("date"))
        if d is None:
            continue
        by_merchant[canonical_merchant(t.get("raw_merchant") or "Unknown")].append((d, amt))

    results: list[dict] = []
    for merchant, entries in by_merchant.items():
        if len(entries) < min_occurrences:
            continue
        entries.sort(key=lambda e: e[0])
        dates = [d for d, _ in entries]
        amounts = [a for _, a in entries]
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        if not gaps:
            continue
        med_gap = median(gaps)
        if not (_MIN_GAP_DAYS <= med_gap <= _MAX_GAP_DAYS):
            continue
        # Every gap must be reasonably close to the median cadence (no big skips).
        if any(g < med_gap * 0.5 or g > med_gap * 1.8 for g in gaps):
            continue
        med_amt = median(amounts)
        if med_amt <= 0 or any(abs(a - med_amt) > 0.25 * med_amt for a in amounts):
            continue
        results.append({
            "merchant": merchant,
            "avg_amount": round(med_amt, 2),
            "monthly": round(med_amt, 2),  # monthly cadence => monthly cost ~= amount
            "count": len(entries),
            "cadence_days": int(med_gap),
        })

    results.sort(key=lambda r: r["monthly"], reverse=True)
    return results
