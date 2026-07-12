"""Transaction groups (clubbing collective payments).

Supports MANUAL clubbing (user selects transactions and names a group) and
AUTO clubbing (deterministically cluster same-merchant, same-day payments, which
are usually one logical purchase split into several UPI transfers).
"""

import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.core.auth import get_current_user
from app.core.database import get_supabase

logger = logging.getLogger("tally.groups")

router = APIRouter(prefix="/api/groups", tags=["groups"])


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    transaction_ids: list[str] = Field(..., min_length=1)


def _embed_category_name(row: dict) -> Optional[str]:
    cat = row.get("categories")
    if isinstance(cat, list):
        cat = cat[0] if cat else None
    return cat.get("name") if isinstance(cat, dict) else None


@router.post("")
async def create_group(
    request: CreateGroupRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Manually club the given transactions into a named group."""
    try:
        # Only club transactions that actually belong to the user.
        owned = db.table("transactions").select("id,amount").eq(
            "user_id", user_id
        ).in_("id", request.transaction_ids).execute().data or []
        if not owned:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="None of the given transactions were found for this user.",
            )

        grp = db.table("transaction_groups").insert(
            {"user_id": user_id, "name": request.name, "kind": "manual"}
        ).execute()
        group_id = grp.data[0]["id"]

        ids = [t["id"] for t in owned]
        db.table("transactions").update({"group_id": group_id}).eq(
            "user_id", user_id
        ).in_("id", ids).execute()

        total = round(sum(float(t.get("amount") or 0) for t in owned), 2)
        return {"id": group_id, "name": request.name, "kind": "manual",
                "count": len(ids), "total": total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("")
async def list_groups(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """List the user's groups with per-group count and total."""
    try:
        groups = db.table("transaction_groups").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).execute().data or []

        # Aggregate counts/totals in one pass over grouped transactions.
        txns = db.table("transactions").select("group_id,amount").eq(
            "user_id", user_id
        ).not_.is_("group_id", "null").execute().data or []
        agg: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0})
        for t in txns:
            gid = t.get("group_id")
            if gid:
                agg[gid]["count"] += 1
                agg[gid]["total"] += float(t.get("amount") or 0)

        return [
            {
                "id": g["id"], "name": g["name"], "kind": g.get("kind", "manual"),
                "created_at": g["created_at"],
                "count": agg[g["id"]]["count"],
                "total": round(agg[g["id"]]["total"], 2),
            }
            for g in groups
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Group detail with its member transactions."""
    try:
        g = db.table("transaction_groups").select("*").eq(
            "id", group_id
        ).eq("user_id", user_id).limit(1).execute().data
        if not g:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        rows = db.table("transactions").select(
            "id,date,amount,raw_merchant,memo,upi_transaction_id,direction,categories(name)"
        ).eq("user_id", user_id).eq("group_id", group_id).order("date", desc=True).execute().data or []

        items = [{
            "id": r["id"], "date": r["date"], "amount": r["amount"],
            "raw_merchant": r.get("raw_merchant"), "memo": r.get("memo"),
            "upi_transaction_id": r.get("upi_transaction_id"),
            "direction": r.get("direction"), "category": _embed_category_name(r),
        } for r in rows]
        total = round(sum(float(r.get("amount") or 0) for r in rows), 2)
        return {**g[0], "count": len(items), "total": total, "transactions": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Ungroup: detach member transactions and delete the group."""
    try:
        g = db.table("transaction_groups").select("id").eq(
            "id", group_id
        ).eq("user_id", user_id).limit(1).execute().data
        if not g:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        db.table("transactions").update({"group_id": None}).eq(
            "user_id", user_id
        ).eq("group_id", group_id).execute()
        db.table("transaction_groups").delete().eq(
            "id", group_id
        ).eq("user_id", user_id).execute()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/auto")
async def auto_group(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Auto-club: cluster ungrouped same-merchant, same-day payments (>=2).

    These are typically one logical spend split across several UPI transfers.
    Deterministic — no LLM needed, so it's fast and reliable.
    """
    try:
        rows = db.table("transactions").select(
            "id,date,raw_merchant,amount,group_id"
        ).eq("user_id", user_id).is_("group_id", "null").execute().data or []

        clusters: dict[tuple, list[dict]] = defaultdict(list)
        for r in rows:
            if r.get("raw_merchant") and r.get("date"):
                clusters[(r["date"], r["raw_merchant"])].append(r)

        created = []
        for (day, merchant), txns in clusters.items():
            if len(txns) < 2:
                continue
            total = round(sum(float(t.get("amount") or 0) for t in txns), 2)
            name = f"{merchant} x{len(txns)} on {day}"
            grp = db.table("transaction_groups").insert(
                {"user_id": user_id, "name": name, "kind": "auto"}
            ).execute()
            gid = grp.data[0]["id"]
            db.table("transactions").update({"group_id": gid}).eq(
                "user_id", user_id
            ).in_("id", [t["id"] for t in txns]).execute()
            created.append({"id": gid, "name": name, "count": len(txns), "total": total})

        return {
            "status": "done",
            "groups_created": len(created),
            "transactions_clubbed": sum(g["count"] for g in created),
            "groups": created,
            "message": (
                f"Auto-clubbed {sum(g['count'] for g in created)} transactions into "
                f"{len(created)} group(s)." if created else
                "No same-merchant same-day clusters of 2+ found to club."
            ),
        }
    except Exception as e:
        logger.exception("auto_group failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
