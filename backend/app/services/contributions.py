"""Detect 'contri' / settle-up clusters (user point #8).

A large outbound spend that gets mostly repaid by many small inbound transfers has
NO explicit link in the data — the only signal is a cluster of small, similar-amount
CREDITS on a day (e.g. 11 people each sending ~Rs 62 back for a game booking). This
module finds those clusters deterministically (no LLM) and, when a nearby large debit
plausibly matches, reports the NET cost instead of the gross.

Sign convention (matches the rest of the app): amount > 0 = spent (outflow),
amount < 0 = received (inflow).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None


def _cluster_by_amount(items: list[dict], tolerance: float, min_cluster: int) -> list[list[dict]]:
    """Group same-day credits into runs of near-equal magnitude (within tolerance
    of the smallest in the run). Returns only runs of at least ``min_cluster``."""
    ordered = sorted(items, key=lambda x: x["mag"])
    clusters: list[list[dict]] = []
    run: list[dict] = []
    for it in ordered:
        if run and it["mag"] <= run[0]["mag"] * (1 + tolerance):
            run.append(it)
        else:
            if len(run) >= min_cluster:
                clusters.append(run)
            run = [it]
    if len(run) >= min_cluster:
        clusters.append(run)
    return clusters


def detect_contributions(
    transactions: list[dict],
    *,
    min_cluster: int = 3,
    amount_tolerance: float = 0.25,
    link_window_days: int = 2,
) -> list[dict]:
    """Find likely settle-up clusters and (when possible) their source spend.

    Returns one entry per cluster, biggest total first::

        {date, count, total_received, avg_amount, transaction_ids,
         source_debit: {id, amount, merchant} | None, net_cost | None}
    """
    credits_by_day: dict[date, list[dict]] = defaultdict(list)
    debits: list[dict] = []
    for t in transactions:
        d = _as_date(t.get("date"))
        if d is None:
            continue
        amt = float(t.get("amount") or 0)
        if amt < 0:
            credits_by_day[d].append({"mag": -amt, "id": t.get("id"), "t": t})
        elif amt > 0:
            debits.append({"d": d, "amount": amt, "t": t})

    results: list[dict] = []
    for d, items in credits_by_day.items():
        for cluster in _cluster_by_amount(items, amount_tolerance, min_cluster):
            total = round(sum(c["mag"] for c in cluster), 2)
            # Find a plausible source spend near this day: a debit whose amount is
            # in [total, ~2x total] (you paid, then got most of it back), closest to total.
            candidates = [
                x for x in debits
                if abs((x["d"] - d).days) <= link_window_days
                and total <= x["amount"] <= total * 2
            ]
            source = min(candidates, key=lambda x: x["amount"] - total, default=None)
            source_debit = None
            net_cost = None
            if source is not None:
                st = source["t"]
                source_debit = {
                    "id": st.get("id"),
                    "amount": round(source["amount"], 2),
                    "merchant": st.get("raw_merchant"),
                }
                net_cost = round(source["amount"] - total, 2)
            results.append({
                "date": d.isoformat(),
                "count": len(cluster),
                "total_received": total,
                "avg_amount": round(total / len(cluster), 2),
                "transaction_ids": [c["id"] for c in cluster],
                "source_debit": source_debit,
                "net_cost": net_cost,
            })

    results.sort(key=lambda r: r["total_received"], reverse=True)
    return results
