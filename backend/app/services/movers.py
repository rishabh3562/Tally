"""Month-over-month category movers.

Which categories rose or fell the most between the two most recent months. Shared
by the chat ('what jumped this month') and the Insights 'movers' card, so the two
never drift.
"""

from collections import defaultdict
from typing import Any, Optional


def _cat_name(t: dict) -> str:
    obj = t.get("categories")
    if isinstance(obj, list):
        obj = obj[0] if obj else None
    return obj.get("name") if isinstance(obj, dict) else "Uncategorized"


def compute_category_movers(txns: list[dict]) -> Optional[dict[str, Any]]:
    """Return {latest, prev, movers: [{category, from_amount, to_amount, delta}]}
    sorted by delta (largest increase first), or None if there aren't two months
    of spending to compare. Spends only (positive amounts)."""
    monthly_cat: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in txns:
        amt = float(t.get("amount") or 0)
        if amt <= 0:
            continue
        ym = str(t.get("date") or "")[:7]  # YYYY-MM
        if len(ym) != 7:
            continue
        monthly_cat[ym][_cat_name(t)] += amt

    months = sorted(monthly_cat)
    if len(months) < 2:
        return None
    latest, prev = months[-1], months[-2]
    cats = set(monthly_cat[latest]) | set(monthly_cat[prev])
    movers = [
        {
            "category": c,
            "from_amount": round(monthly_cat[prev].get(c, 0.0), 2),
            "to_amount": round(monthly_cat[latest].get(c, 0.0), 2),
            "delta": round(monthly_cat[latest].get(c, 0.0) - monthly_cat[prev].get(c, 0.0), 2),
        }
        for c in cats
    ]
    movers.sort(key=lambda m: m["delta"], reverse=True)
    return {"latest": latest, "prev": prev, "movers": movers}
