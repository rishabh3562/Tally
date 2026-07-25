"""rename_category action — rename the user's OWN category, never a built-in one.

Uses a filter-aware fake Supabase (honours .eq/.ilike) so the security-critical
distinction between an owned category and a shared system one is actually
exercised — the whole point of the guard.
"""

from app.services import chat_tools, chat_service


class _Res:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table, store):
        self.table, self.store = table, store
        self._eq = {}
        self._ilike = None
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
        return self

    def or_(self, *a, **k):
        # _visible_categories: own + system. No user_id .eq — return everything
        # in the store (tests only stock this user's + system rows).
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def ilike(self, col, val):
        self._ilike = (col, str(val).strip("%"))
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def execute(self):
        if self._op == "update":
            self.store["log"].append(
                {"table": self.table, "op": "update",
                 "payload": self._payload, "eqs": dict(self._eq)}
            )
            return _Res([{"id": "x"}])
        rows = self.store["data"].get(self.table, [])
        out = []
        for r in rows:
            ok = all(r.get(k) == v for k, v in self._eq.items())
            if self._ilike:
                col, sub = self._ilike
                ok = ok and sub.lower() == str(r.get(col) or "").lower()
            if ok:
                out.append(r)
        return _Res(out)


class _FakeDB:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _Query(name, self.store)


def _store(categories):
    return {"data": {"categories": categories}, "log": []}


def _updates(store):
    return [l for l in store["log"] if l["op"] == "update"]


def test_rename_own_category_succeeds_and_is_scoped():
    store = _store([{"id": "c1", "name": "Rnt", "user_id": "u1"}])
    out = chat_tools.rename_category(_FakeDB(store), "u1", old_name="Rnt", new_name="Rent")
    assert out["action"] == "rename_category"
    assert out["old_name"] == "Rnt" and out["new_name"] == "Rent"
    ups = _updates(store)
    assert len(ups) == 1
    assert ups[0]["payload"] == {"name": "Rent"}
    assert ups[0]["eqs"]["user_id"] == "u1"   # scoped to the caller
    assert ups[0]["eqs"]["id"] == "c1"


def test_cannot_rename_system_category():
    # user_id None => a shared built-in; renaming it would hit every user.
    store = _store([{"id": "sys", "name": "Food", "user_id": None}])
    out = chat_tools.rename_category(_FakeDB(store), "u1", old_name="Food", new_name="Grub")
    assert "error" in out and "built-in" in out["error"]
    assert _updates(store) == []   # nothing mutated


def test_rename_unknown_category_errors():
    store = _store([{"id": "c1", "name": "Rent", "user_id": "u1"}])
    out = chat_tools.rename_category(_FakeDB(store), "u1", old_name="Nope", new_name="X")
    assert "error" in out and "don't have" in out["error"]
    assert _updates(store) == []


def test_rename_collision_is_rejected():
    store = _store([
        {"id": "c1", "name": "Rent", "user_id": "u1"},
        {"id": "c2", "name": "Housing", "user_id": "u1"},
    ])
    out = chat_tools.rename_category(_FakeDB(store), "u1", old_name="Rent", new_name="Housing")
    assert "error" in out and "already exists" in out["error"]
    assert _updates(store) == []


def test_rename_noop_when_same_name():
    store = _store([{"id": "c1", "name": "Rent", "user_id": "u1"}])
    out = chat_tools.rename_category(_FakeDB(store), "u1", old_name="Rent", new_name="rent")
    assert "error" in out
    assert _updates(store) == []


def test_deterministic_parse_runs_rename():
    # The keyless path must recognise a plain "rename X to Y" command.
    store = _store([{"id": "c1", "name": "Rnt", "user_id": "u1"}])
    out = chat_service.try_action("rename Rnt to Rent", "u1", _FakeDB(store))
    assert out is not None
    assert "Renamed" in out and "Rent" in out
    assert len(_updates(store)) == 1


def test_deterministic_parse_ignores_non_command():
    # A normal question must not trip the rename parser.
    store = _store([{"id": "c1", "name": "Rent", "user_id": "u1"}])
    out = chat_service.try_action("how much did I spend on food", "u1", _FakeDB(store))
    assert out is None
    assert _updates(store) == []
