"""Two-user cross-access isolation (Phase 4).

The backend uses the Supabase service-role key, which BYPASSES row-level
security — so per-endpoint ``user_id``-from-token scoping is the ONLY thing
separating users. These tests use a filter-aware fake Supabase (it actually
honours ``.eq()``) and assert that a request authenticated as user A never
returns user B's rows. If an endpoint ever drops its ``.eq("user_id", ...)``,
one of these fails.
"""

from app.api import transactions, events, groups, insights


class _Result:
    def __init__(self, data):
        self.data = data


class _Not:
    """Supports the ``query.not_.is_(col, 'null')`` chain (negation is a no-op
    for these isolation tests — we only assert user_id scoping)."""

    def __init__(self, q):
        self._q = q

    def is_(self, col, val):
        return self._q


class _Query:
    """Minimal PostgREST builder that actually applies eq/ilike/lt filters."""

    def __init__(self, rows):
        self._rows = rows
        self._eq = []
        self._ilike = []
        self._lt = []

    def select(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def is_(self, col, val):
        self._eq.append((col, None))
        return self

    @property
    def not_(self):
        return _Not(self)

    def eq(self, col, val):
        self._eq.append((col, val))
        return self

    def ilike(self, col, val):
        self._ilike.append((col, str(val).strip("%")))
        return self

    def lt(self, col, val):
        self._lt.append((col, val))
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        rows = self._rows
        for col, val in self._eq:
            rows = [r for r in rows if r.get(col) == val]
        for col, sub in self._ilike:
            rows = [r for r in rows if sub.lower() in str(r.get(col) or "").lower()]
        for col, val in self._lt:
            rows = [r for r in rows if (r.get(col) is not None and r[col] < val)]
        return _Result(list(rows))


class _FakeDB:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _Query(self._tables.get(name, []))


def _two_user_transactions():
    return [
        {"id": "a1", "user_id": "A", "date": "2026-07-01", "amount": 100,
         "raw_merchant": "AmazonA", "memo": None, "category_id": None,
         "confidence_score": 0.5, "categories": None},
        {"id": "b1", "user_id": "B", "date": "2026-07-01", "amount": 200,
         "raw_merchant": "FlipkartB", "memo": None, "category_id": None,
         "confidence_score": 0.5, "categories": None},
    ]


async def test_transactions_list_never_leaks_other_user():
    db = _FakeDB({"transactions": _two_user_transactions()})
    out = await transactions.list_transactions(
        start_date=None, end_date=None, category_id=None, merchant=None,
        page=1, limit=50, user_id="A", db=db,
    )
    ids = {r["id"] for r in out["data"]}
    assert ids == {"a1"}          # B's row is invisible to A
    assert out["total"] == 1


async def test_triage_never_leaks_other_user():
    db = _FakeDB({"transactions": _two_user_transactions(), "categories": []})
    out = await transactions.get_triage_queue(user_id="A", db=db)
    merchants = {m["raw_merchant"] for m in out["data"]}
    assert merchants == {"AmazonA"}   # B's FlipkartB not aggregated into A's triage


async def test_review_queue_never_leaks_other_user():
    rows = _two_user_transactions()
    for r in rows:
        r["confidence_score"] = 0.2   # both low-confidence
    db = _FakeDB({"transactions": rows})
    out = await transactions.get_review_queue(user_id="B", db=db)
    ids = {r["id"] for r in out["data"]}
    assert ids == {"b1"}          # A's row invisible to B


async def test_events_list_never_leaks_other_user():
    db = _FakeDB({"events": [
        {"id": "e-a", "user_id": "A", "name": "A trip", "created_at": "2026-07-01"},
        {"id": "e-b", "user_id": "B", "name": "B trip", "created_at": "2026-07-01"},
    ]})
    out = await events.list_events(user_id="A", db=db)
    assert {e["id"] for e in out} == {"e-a"}   # B's event invisible to A


async def test_groups_list_never_leaks_other_user():
    db = _FakeDB({
        "transaction_groups": [
            {"id": "g-a", "user_id": "A", "name": "A group", "kind": "manual",
             "created_at": "2026-07-01"},
            {"id": "g-b", "user_id": "B", "name": "B group", "kind": "manual",
             "created_at": "2026-07-01"},
        ],
        "transactions": [
            {"user_id": "A", "group_id": "g-a", "amount": 100},
            {"user_id": "B", "group_id": "g-b", "amount": 200},
        ],
    })
    out = await groups.list_groups(user_id="A", db=db)
    assert {g["id"] for g in out} == {"g-a"}   # B's group invisible to A


async def test_contributions_never_leaks_other_user():
    # A has a 3-credit cluster; B has their own. A must only see A's.
    rows = (
        [{"id": f"a{i}", "user_id": "A", "date": "2026-05-01", "amount": -62,
          "raw_merchant": "friend"} for i in range(3)]
        + [{"id": f"b{i}", "user_id": "B", "date": "2026-05-01", "amount": -80,
            "raw_merchant": "other"} for i in range(3)]
    )
    db = _FakeDB({"transactions": rows})
    out = await insights.get_contributions(user_id="A", db=db)
    ids = {i for c in out["data"] for i in c["transaction_ids"]}
    assert ids == {"a0", "a1", "a2"}   # none of B's transfers appear
