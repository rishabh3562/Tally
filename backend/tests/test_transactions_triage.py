"""Tests for the triage aggregation + merchant assignment (fake DB, no network).

Covers:
- ``aggregate_triage`` pure grouping/suggestion/sort logic.
- ``assign_merchant_category`` scoping to the token user + learning-record write.
- ``create_category`` user-scoped create + idempotent reuse.
"""

import pytest
from fastapi import HTTPException

from app.api import transactions as tx
from app.api import categorization
from app.schemas.transactions import AssignMerchantRequest
from app.schemas.categories import CategoryCreate


# --- triage aggregation (pure) ---------------------------------------------

def _row(merchant, amount, category=None, memo=None):
    cat = {"name": category} if category is not None else None
    return {"raw_merchant": merchant, "amount": amount, "memo": memo, "categories": cat}


def test_aggregate_groups_needy_by_merchant_and_sums_abs(monkeypatch):
    monkeypatch.setattr(tx, "rule_category", lambda m, memo: None)
    rows = [
        _row("Amazon", 100), _row("Amazon", -50),   # abs sum = 150
        _row("Zomato", 40),
        _row("Swiggy", 10, category="Food"),          # already categorized -> skip
        _row(None, 999),                               # null merchant -> skip
        _row("PaidPerson", 20, category="Other"),     # "Other" -> needy
    ]
    out = tx.aggregate_triage(rows, {})
    by = {g["raw_merchant"]: g for g in out}
    assert by["Amazon"]["count"] == 2
    assert by["Amazon"]["total"] == 150        # abs magnitude (100 + 50)
    assert by["Amazon"]["net"] == 50           # signed (100 + -50): net spent
    assert by["Zomato"]["total"] == 40
    assert "Swiggy" not in by
    assert all(g["raw_merchant"] for g in out)      # no null merchant slipped in
    assert out[0]["raw_merchant"] == "Amazon"        # sorted by total desc


def test_aggregate_attaches_suggestion_only_when_in_catalog(monkeypatch):
    monkeypatch.setattr(
        tx, "rule_category",
        lambda m, memo: ("Shopping", 0.9) if m == "Amazon" else None,
    )
    out = tx.aggregate_triage([_row("Amazon", 100), _row("RahulK", 500)], {"Shopping": "cat-shop"})
    by = {g["raw_merchant"]: g for g in out}
    assert by["Amazon"]["suggestion"] == {
        "category": "Shopping", "category_id": "cat-shop", "confidence": 0.9,
    }
    assert by["RahulK"]["suggestion"] is None


def test_aggregate_drops_suggestion_when_category_not_visible(monkeypatch):
    monkeypatch.setattr(tx, "rule_category", lambda m, memo: ("Ghost", 0.9))
    out = tx.aggregate_triage([_row("X", 10)], {})   # 'Ghost' not in name_to_id
    assert out[0]["suggestion"] is None


# --- recording fake Supabase (records writes, returns canned rows) ---------

class _Res:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, store):
        self.table = table
        self.store = store
        self.eqs = {}
        self._ilike = None
        self._op = "select"
        self._payload = None
        self._on_conflict = None

    def select(self, *a, **k):
        return self

    def or_(self, expr):
        return self

    def eq(self, col, val):
        self.eqs[col] = val
        return self

    def ilike(self, col, val):
        self._ilike = (col, str(val).strip("%").lower())
        return self

    def is_(self, col, val):
        self.eqs[col] = None
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def upsert(self, payload, on_conflict=None):
        self._op, self._payload, self._on_conflict = "upsert", payload, on_conflict
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def execute(self):
        self.store["log"].append({
            "table": self.table, "op": self._op, "payload": self._payload,
            "eqs": self.eqs, "on_conflict": self._on_conflict,
        })
        if self._op == "select":
            rows = self.store["data"].get(self.table, [])
            if self._ilike:
                col, sub = self._ilike
                rows = [r for r in rows if sub in str(r.get(col) or "").lower()]
            return _Res(rows)
        return _Res(self.store.get(self._op + "_rows", [{"id": "x"}]))


class _FakeDB:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeQuery(name, self.store)


# --- assign-merchant --------------------------------------------------------

async def test_assign_merchant_scopes_to_user_and_learns():
    store = {
        "data": {"categories": [{"id": "cat-1"}]},
        "update_rows": [{"id": "t1"}, {"id": "t2"}],
        "log": [],
    }
    res = await tx.assign_merchant_category(
        AssignMerchantRequest(raw_merchant="Amazon", category_id="cat-1"),
        user_id="u1", db=_FakeDB(store),
    )
    assert res == {"updated": 2}

    upd = next(l for l in store["log"] if l["table"] == "transactions" and l["op"] == "update")
    assert upd["eqs"] == {"user_id": "u1", "raw_merchant": "Amazon"}     # scoped to token user
    assert upd["payload"] == {"category_id": "cat-1", "confidence_score": 1.0}

    lr = next(l for l in store["log"] if l["table"] == "learning_records" and l["op"] == "upsert")
    assert lr["payload"] == {"user_id": "u1", "raw_merchant": "Amazon", "category_id": "cat-1"}
    assert lr["on_conflict"] == "user_id,raw_merchant"


async def test_assign_merchant_rejects_unknown_category():
    store = {"data": {"categories": []}, "log": []}
    with pytest.raises(HTTPException) as ei:
        await tx.assign_merchant_category(
            AssignMerchantRequest(raw_merchant="X", category_id="nope"),
            user_id="u1", db=_FakeDB(store),
        )
    assert ei.value.status_code == 404
    # never touched transactions when the category is invalid
    assert not any(l["table"] == "transactions" for l in store["log"])


# --- create-category --------------------------------------------------------

async def test_create_category_creates_user_scoped():
    store = {
        "data": {"categories": []},
        "insert_rows": [{"id": "c-new", "name": "Rent", "icon": "🏠", "user_id": "u1"}],
        "log": [],
    }
    res = await categorization.create_category(
        CategoryCreate(name="Rent", icon="🏠"), user_id="u1", db=_FakeDB(store),
    )
    assert res["created"] is True
    ins = next(l for l in store["log"] if l["op"] == "insert")
    assert ins["payload"] == {"name": "Rent", "icon": "🏠", "user_id": "u1", "parent_id": None}


async def test_create_category_reuses_existing_by_name():
    store = {"data": {"categories": [{"id": "c1", "name": "Rent", "icon": "🏠", "user_id": None}]}, "log": []}
    res = await categorization.create_category(
        CategoryCreate(name="rent"), user_id="u1", db=_FakeDB(store),
    )
    assert res["created"] is False
    assert res["data"]["id"] == "c1"
    assert not any(l["op"] == "insert" for l in store["log"])


async def test_create_category_rejects_blank():
    with pytest.raises(HTTPException) as ei:
        await categorization.create_category(
            CategoryCreate(name="   "), user_id="u1", db=_FakeDB({"data": {}, "log": []}),
        )
    assert ei.value.status_code == 422


async def test_create_subcategory_under_valid_parent():
    store = {
        "data": {"categories": [{"id": "p1", "name": "Food", "user_id": None, "parent_id": None}]},
        "insert_rows": [{"id": "s1", "name": "Pizza", "parent_id": "p1", "user_id": "u1"}],
        "log": [],
    }
    res = await categorization.create_category(
        CategoryCreate(name="Pizza", parent_id="p1"), user_id="u1", db=_FakeDB(store),
    )
    assert res["created"] is True
    ins = next(l for l in store["log"] if l["op"] == "insert")
    assert ins["payload"]["parent_id"] == "p1"      # linked to the parent


async def test_create_subcategory_rejects_unknown_parent():
    store = {"data": {"categories": []}, "log": []}   # parent p-missing not visible
    with pytest.raises(HTTPException) as ei:
        await categorization.create_category(
            CategoryCreate(name="Pizza", parent_id="p-missing"), user_id="u1", db=_FakeDB(store),
        )
    assert ei.value.status_code == 404
    assert not any(l["op"] == "insert" for l in store["log"])


async def test_category_names_stay_globally_unique():
    # Names must be unique regardless of parent — name->id lookups elsewhere
    # (triage/recategorize/chat) key on name and can't disambiguate duplicates.
    store = {"data": {"categories": [
        {"id": "existing", "name": "Pizza", "user_id": "u1", "parent_id": "other-parent"},
    ]}, "log": []}
    res = await categorization.create_category(
        CategoryCreate(name="Pizza", parent_id="p1"), user_id="u1", db=_FakeDB(store),
    )
    assert res["created"] is False               # reused, not duplicated
    assert res["data"]["id"] == "existing"
    assert not any(l["op"] == "insert" for l in store["log"])
