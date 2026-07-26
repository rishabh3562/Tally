"""list_transactions sorting — the sort column is whitelisted (no injection)."""

from app.api import transactions


class _Q:
    def __init__(self, rec):
        self.rec = rec

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def order(self, col, desc=True):
        self.rec["order"] = (col, desc)
        return self

    def range(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": []})()


class _DB:
    def __init__(self, rec):
        self.rec = rec

    def table(self, name):
        return _Q(self.rec)


async def _call(sort, order):
    rec: dict = {}
    await transactions.list_transactions(
        start_date=None, end_date=None, category_id=None, merchant=None,
        sort=sort, order=order, page=1, limit=50, user_id="u", db=_DB(rec),
    )
    return rec["order"]


async def test_sort_by_amount_ascending():
    assert await _call("amount", "asc") == ("amount", False)


async def test_sort_by_date_desc_default():
    assert await _call("date", "desc") == ("date", True)


async def test_unknown_sort_column_falls_back_to_date():
    # A crafted column must not reach the query — whitelist forces 'date'.
    assert await _call("password", "desc") == ("date", True)
