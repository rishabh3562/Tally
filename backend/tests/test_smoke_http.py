"""HTTP-level smoke test: drive the real app through TestClient with auth and the
database dependency overridden, so the full request -> auth -> route -> service ->
serialization stack is exercised (beyond the unit tests that call handlers directly).

No network, no real DB: get_current_user returns a fixed user and get_supabase
returns a filter-aware fake. Proves the wiring the browser would hit.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.core.database import get_supabase


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows):
        self._rows = rows
        self._eq = {}
        self._any_ilike: list[tuple[str, str]] = []   # OR of ilike patterns
        self._ilike: tuple[str, str] | None = None

    def select(self, *a, **k):
        return self

    def or_(self, expr, *a, **k):
        # PostgREST or-filter as the API builds it:
        # "raw_merchant.ilike.%swiggy%,raw_merchant.ilike.%bundltech%"
        for clause in expr.split(","):
            col, op, value = clause.split(".", 2)
            if op == "ilike":
                self._any_ilike.append((col, value.strip("%").lower()))
        return self

    def eq(self, c, v):
        self._eq[c] = v
        return self

    def is_(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def ilike(self, col, pattern):
        self._ilike = (col, pattern.strip("%").lower())
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, row):
        # chat_traces / chat_messages writes: accept them so the streaming test
        # exercises the real save path instead of a swallowed AttributeError.
        self._rows.append(row)
        return self

    def execute(self):
        rows = self._rows
        uid = self._eq.get("user_id")
        if uid is not None:
            rows = [r for r in rows if r.get("user_id") in (uid, None)]
        exact = self._eq.get("raw_merchant")
        if exact is not None:
            rows = [r for r in rows if r.get("raw_merchant") == exact]
        if self._ilike:
            col, needle = self._ilike
            rows = [r for r in rows if needle in str(r.get(col) or "").lower()]
        if self._any_ilike:
            rows = [
                r for r in rows
                if any(n in str(r.get(c) or "").lower() for c, n in self._any_ilike)
            ]
        return _Res(list(rows))


class _DB:
    def __init__(self, tables):
        self._t = tables

    def table(self, name):
        return _Q(self._t.get(name, []))


def _txn_row(id_, merchant, amount=500):
    return {"id": id_, "user_id": "smoke-user", "date": "2026-07-01",
            "amount": amount, "currency": "INR", "raw_merchant": merchant,
            "memo": None, "category_id": None, "confidence_score": 0.5,
            "is_transfer": False, "upi_transaction_id": None,
            "direction": "debit", "group_id": None, "categories": None}


_TABLES = {
    "transactions": [
        _txn_row("t1", "AmazonIndia"),
        # Real-statement shapes: a brand hiding behind a legal name, and a
        # variant that shares no substring with what a user would type.
        _txn_row("t2", "AVENUESUPERMARTSLTD", 1200),
        _txn_row("t3", "BundlTechnologiespvtLtd", 300),
    ],
    "categories": [
        {"id": "c1", "name": "Shopping", "icon": "🛍️", "user_id": None, "parent_id": None},
        {"id": "c2", "name": "Other", "icon": "📌", "user_id": None, "parent_id": None},
    ],
    "events": [],
    "chat_messages": [],
    "chat_traces": [],
}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: "smoke-user"
    app.dependency_overrides[get_supabase] = lambda: _DB(_TABLES)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "healthy"}


def test_transactions_list_serializes(client):
    r = client.get("/api/transactions")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert {t["raw_merchant"] for t in body["data"]} == {
        "AmazonIndia", "AVENUESUPERMARTSLTD", "BundlTechnologiespvtLtd",
    }


def test_merchant_filter_is_a_search_not_an_exact_match(client):
    """The bug: `merchant` was .eq(raw_merchant), so the UI's search box returned
    NOTHING for "Amazon" — every real row is "AmazonIndia"/"AmazonPay"."""
    r = client.get("/api/transactions", params={"merchant": "amazon"})
    assert r.status_code == 200
    assert [t["raw_merchant"] for t in r.json()["data"]] == ["AmazonIndia"]


def test_merchant_search_is_brand_aware(client):
    """"dmart" shares no substring with AVENUESUPERMARTSLTD, and "swiggy" none
    with BundlTechnologiespvtLtd — the same brand map the chat uses."""
    for keyword, expected in [("dmart", "AVENUESUPERMARTSLTD"),
                              ("swiggy", "BundlTechnologiespvtLtd")]:
        r = client.get("/api/transactions", params={"merchant": keyword})
        assert [t["raw_merchant"] for t in r.json()["data"]] == [expected], keyword


def test_merchant_exact_still_isolates_one_string(client):
    """The triage drill-in edits the rows of one exact merchant; a search there
    would pull in look-alikes and let an override hit the wrong rows."""
    r = client.get("/api/transactions", params={"merchant_exact": "AmazonIndia"})
    assert [t["id"] for t in r.json()["data"]] == ["t1"]
    r = client.get("/api/transactions", params={"merchant_exact": "Amazon"})
    assert r.json()["data"] == []


def test_categories_list(client):
    r = client.get("/api/categories")
    assert r.status_code == 200
    names = {c["name"] for c in r.json()["data"]}
    assert "Shopping" in names


def test_triage_groups_the_uncategorized(client):
    r = client.get("/api/transactions/triage")
    assert r.status_code == 200
    body = r.json()
    assert body["merchants"] == 3
    # ₹-sorted, so the biggest pile is first — that's the one worth labelling.
    assert body["data"][0]["raw_merchant"] == "AVENUESUPERMARTSLTD"


def test_chat_messages_history_endpoint(client):
    r = client.get("/api/chat/messages")
    assert r.status_code == 200
    assert r.json() == {"data": []}


def test_chat_streams_through_the_real_endpoint(client, monkeypatch):
    """The closest thing to a browser: POST /api/chat and read the raw SSE body.

    Every other chat test calls the generator directly, so nothing covered
    route -> StreamingResponse -> generator, which is exactly where a framing
    mistake would only show up in the browser. "help" takes the instant path, so
    no model is involved.
    """
    r = client.post("/api/chat", json={"question": "help"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    body = r.text
    # Reassemble the way useChat.ts does: track the event name, keep status out of
    # the answer, and turn the two-character newline escape back into a real one.
    escaped_newline = chr(92) + "n"
    answer, statuses, event_name = "", [], ""
    for line in body.split("\n"):
        if line.startswith("event: "):
            event_name = line[7:].strip()
        elif line.startswith("data: "):
            payload = line[6:]
            if event_name == "status":
                statuses.append(payload)
            else:
                answer += payload.replace(escaped_newline, "\n")
        elif line == "":
            event_name = ""

    assert "Try:" in answer                  # the capability menu came through
    assert answer.count("\n") >= 5           # and it's still a list, not one line
    for s in statuses:
        assert s not in answer               # progress never leaks into the answer
