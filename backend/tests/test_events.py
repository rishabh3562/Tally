"""Tests for the events API — summary generation + scoped, total-computing create."""

import pytest

from app.api import events
from app.schemas.events import EventCreate


class _R:
    def __init__(self, d):
        self.data = d


class _Q:
    """Filter-aware fake: honours eq/in_ on select, records inserts/deletes."""

    def __init__(self, table, store):
        self.table = table
        self.store = store
        self.eqs = {}
        self._in = None
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
        return self

    def eq(self, c, v):
        self.eqs[c] = v
        return self

    def in_(self, c, vals):
        self._in = (c, list(vals))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def execute(self):
        self.store["log"].append({
            "table": self.table, "op": self._op, "payload": self._payload,
            "eqs": dict(self.eqs), "in": self._in,
        })
        if self._op == "insert":
            row = dict(self._payload) if isinstance(self._payload, dict) else self._payload
            if isinstance(row, dict):
                row.setdefault("created_at", "2026-07-25T00:00:00Z")
                row.setdefault("currency", "INR")
                return _R([row])
            return _R(row)
        if self._op == "delete":
            return _R([])
        rows = self.store["data"].get(self.table, [])
        for c, v in self.eqs.items():
            rows = [r for r in rows if r.get(c) == v]
        if self._in:
            c, vals = self._in
            rows = [r for r in rows if r.get(c) in vals]
        return _R(list(rows))


class _DB:
    def __init__(self, store):
        self.store = store

    def table(self, n):
        return _Q(n, self.store)


async def test_create_event_scopes_transactions_and_computes_total(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: False)
    store = {"data": {"transactions": [
        {"id": "t1", "user_id": "A", "amount": 100, "date": "2026-04-01",
         "raw_merchant": "Amazon", "category_id": None},
        {"id": "t2", "user_id": "B", "amount": 999, "date": "2026-04-01",
         "raw_merchant": "X", "category_id": None},
    ]}, "log": []}
    out = await events.create_event(
        EventCreate(name="New phone", transaction_ids=["t1", "t2"], description="my phone"),
        user_id="A", db=_DB(store), settings=None,
    )
    assert out.total_amount == 100          # B's t2 excluded from A's event
    assert out.description == "my phone"
    links = [l for l in store["log"]
             if l["table"] == "event_transactions" and l["op"] == "insert"]
    assert len(links) == 1                    # only the owned transaction linked
    assert links[0]["payload"]["transaction_id"] == "t1"


async def test_summary_empty_transactions():
    out = await events._generate_event_summary("Goa Trip", [])
    assert "Goa Trip" in out
    assert "no transactions" in out.lower()


async def test_summary_falls_back_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: False)
    txns = [{"amount": 500}, {"amount": 250}]
    out = await events._generate_event_summary("Goa Trip", txns)
    assert "Goa Trip" in out
    assert "750" in out            # deterministic total
    assert "2 transactions" in out


async def test_summary_falls_back_on_llm_error(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: True)

    async def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(events.llm_client, "acomplete", boom)
    out = await events._generate_event_summary("Goa Trip", [{"amount": 100}])
    assert "100" in out
    assert "Goa Trip" in out


async def test_summary_uses_llm_output_when_available(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: True)

    async def ok(*a, **k):
        return "Goa Trip: a lovely getaway."

    monkeypatch.setattr(events.llm_client, "acomplete", ok)
    out = await events._generate_event_summary("Goa Trip", [{"amount": 100}])
    assert out == "Goa Trip: a lovely getaway."
