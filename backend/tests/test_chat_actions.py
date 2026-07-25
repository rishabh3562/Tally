"""Tests for chat WRITE actions — categorize_merchant / create_category.

Fake Supabase (records mutations, returns canned rows) + the scripted-LLM helper
from test_chat_agent, so nothing touches the network or a real DB.
"""

import pytest

from app.services import chat_tools, chat_agent
from tests.test_chat_agent import _script_llm


class _Res:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, store):
        self.table = table
        self.store = store
        self.eqs = {}
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
            return _Res(self.store["data"].get(self.table, []))
        return _Res(self.store.get(self._op + "_rows", [{"id": "x"}]))


class _FakeDB:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeQuery(name, self.store)


def _store(**data):
    return {"data": data, "log": []}


# --- categorize_merchant ----------------------------------------------------

def test_categorize_merchant_labels_all_matches_and_learns():
    store = _store(
        categories=[{"id": "cat-shop", "name": "Shopping"}],
        transactions=[
            {"raw_merchant": "AmazonIndia"},
            {"raw_merchant": "AmazonPay"},
            {"raw_merchant": "AmazonIndia"},  # duplicate collapses
        ],
    )
    store["update_rows"] = [{"id": "t1"}, {"id": "t2"}]  # 2 rows per merchant
    out = chat_tools.categorize_merchant(
        _FakeDB(store), "u1", merchant="amazon", category="shopping"
    )
    assert out["category"] == "Shopping"
    assert out["matched_merchants"] == ["AmazonIndia", "AmazonPay"]
    assert out["transactions_updated"] == 4  # 2 merchants × 2 rows

    updates = [l for l in store["log"] if l["table"] == "transactions" and l["op"] == "update"]
    assert len(updates) == 2
    assert all(u["eqs"]["user_id"] == "u1" for u in updates)     # scoped to token user
    assert all(u["payload"]["category_id"] == "cat-shop" for u in updates)
    learns = [l for l in store["log"] if l["table"] == "learning_records"]
    assert len(learns) == 2
    assert all(l["on_conflict"] == "user_id,raw_merchant" for l in learns)


def test_categorize_merchant_unknown_category_lists_options():
    store = _store(categories=[{"id": "c1", "name": "Shopping"}])
    out = chat_tools.categorize_merchant(
        _FakeDB(store), "u1", merchant="amazon", category="Groceries"
    )
    assert "error" in out
    assert out["available_categories"] == ["Shopping"]
    assert not any(l["op"] == "update" for l in store["log"])   # nothing changed


def test_categorize_merchant_no_match_is_noop():
    store = _store(categories=[{"id": "c1", "name": "Shopping"}], transactions=[])
    out = chat_tools.categorize_merchant(
        _FakeDB(store), "u1", merchant="nope", category="Shopping"
    )
    assert out["transactions_updated"] == 0
    assert out["matched_merchants"] == []


def test_categorize_merchant_rejects_short_token():
    # A vague token like "pay" must not relabel unrelated merchants.
    store = _store(categories=[{"id": "c1", "name": "Shopping"}])
    out = chat_tools.categorize_merchant(
        _FakeDB(store), "u1", merchant="pay", category="Shopping"
    )
    assert "error" in out
    assert not any(l["op"] == "update" for l in store["log"])


def test_categorize_merchant_refuses_too_many_merchants():
    store = _store(
        categories=[{"id": "c1", "name": "Shopping"}],
        transactions=[{"raw_merchant": f"Merchant{i}"} for i in range(11)],
    )
    out = chat_tools.categorize_merchant(
        _FakeDB(store), "u1", merchant="merch", category="Shopping"
    )
    assert out["needs_confirmation"] is True
    assert out["transactions_updated"] == 0
    assert not any(l["op"] == "update" for l in store["log"])  # nothing mutated


# --- create_category --------------------------------------------------------

def test_create_category_creates_and_is_idempotent():
    store = _store(categories=[])
    store["insert_rows"] = [{"id": "c-new", "name": "Rent"}]
    out = chat_tools.create_category(_FakeDB(store), "u1", name="Rent")
    assert out["created"] is True
    ins = next(l for l in store["log"] if l["op"] == "insert")
    assert ins["payload"] == {"name": "Rent", "icon": "🏷️", "user_id": "u1"}

    store2 = _store(categories=[{"id": "c1", "name": "Rent"}])
    out2 = chat_tools.create_category(_FakeDB(store2), "u1", name="rent")
    assert out2["created"] is False
    assert out2["category"]["id"] == "c1"


# --- end-to-end through the agent -------------------------------------------

async def test_agent_runs_categorize_action_then_confirms(monkeypatch):
    _script_llm(
        monkeypatch,
        [
            {"action": "call_tool", "tool": "categorize_merchant",
             "args": {"merchant": "amazon", "category": "Shopping"}},
            {"action": "final", "answer": "Labeled 4 Amazon payments as Shopping."},
        ],
    )
    store = _store(
        categories=[{"id": "cat-shop", "name": "Shopping"}],
        transactions=[{"raw_merchant": "AmazonIndia"}, {"raw_merchant": "AmazonPay"}],
    )
    store["update_rows"] = [{"id": "t1"}, {"id": "t2"}]
    out = await chat_agent.run_agent("put my amazon under Shopping", "u1", _FakeDB(store))
    # Confirmation is server-composed from the REAL count (4), not the model's text.
    assert "Categorized 4 payments" in out
    assert "Shopping" in out
    # the action actually mutated data (not just answered)
    assert any(l["op"] == "update" and l["table"] == "transactions" for l in store["log"])
