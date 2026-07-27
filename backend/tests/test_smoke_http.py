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

    def select(self, *a, **k):
        return self

    def or_(self, *a, **k):
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

    def ilike(self, *a, **k):
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
        return _Res(list(rows))


class _DB:
    def __init__(self, tables):
        self._t = tables

    def table(self, name):
        return _Q(self._t.get(name, []))


_TABLES = {
    "transactions": [
        {"id": "t1", "user_id": "smoke-user", "date": "2026-07-01", "amount": 500,
         "currency": "INR", "raw_merchant": "AmazonIndia", "memo": None,
         "category_id": None, "confidence_score": 0.5, "is_transfer": False,
         "upi_transaction_id": None, "direction": "debit", "group_id": None,
         "categories": None},
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
    assert body["total"] == 1
    assert body["data"][0]["raw_merchant"] == "AmazonIndia"


def test_categories_list(client):
    r = client.get("/api/categories")
    assert r.status_code == 200
    names = {c["name"] for c in r.json()["data"]}
    assert "Shopping" in names


def test_triage_groups_the_uncategorized(client):
    r = client.get("/api/transactions/triage")
    assert r.status_code == 200
    body = r.json()
    assert body["merchants"] == 1
    assert body["data"][0]["raw_merchant"] == "AmazonIndia"


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
