"""Agent read tools for the analytical answers — so the LLM path (once a key is
set) can answer 'what jumped' and 'average monthly spend', matching the keyless
deterministic path. Pure fake DB; no network."""

from app.services import chat_tools


def _tx(amount, date, category="Food"):
    return {"amount": amount, "date": date, "raw_merchant": "M",
            "categories": {"name": category}}


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        return _Res(self._rows)


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _Q(self._rows)


def test_category_movers_tool():
    rows = [
        _tx(1000, "2026-02-05", "Food"),
        _tx(3000, "2026-03-05", "Food"),   # +2000
    ]
    out = chat_tools.get_category_movers(_DB(rows), "u1")
    assert out["latest"] == "2026-03" and out["prev"] == "2026-02"
    assert out["movers"][0]["category"] == "Food"
    assert out["movers"][0]["delta"] == 2000


def test_category_movers_tool_empty():
    out = chat_tools.get_category_movers(_DB([]), "u1")
    assert out == {"latest": None, "prev": None, "movers": []}


def test_average_monthly_tool():
    rows = [
        _tx(600, "2026-01-10"), _tx(400, "2026-01-20"),   # Jan 1000
        _tx(2000, "2026-02-15"),                          # Feb 2000
        _tx(3000, "2026-03-15"),                          # Mar 3000
    ]
    out = chat_tools.get_average_monthly_spend(_DB(rows), "u1")
    assert out["average_monthly"] == 2000.0
    assert out["months"] == 3
    assert out["peak_month"] == "2026-03" and out["peak_amount"] == 3000.0


def test_average_monthly_tool_ignores_credits():
    rows = [_tx(1000, "2026-01-10"), _tx(-9000, "2026-01-11"), _tx(1000, "2026-02-10")]
    out = chat_tools.get_average_monthly_spend(_DB(rows), "u1")
    assert out["average_monthly"] == 1000.0 and out["months"] == 2


def test_average_monthly_tool_empty():
    out = chat_tools.get_average_monthly_spend(_DB([]), "u1")
    assert out == {"average_monthly": 0.0, "months": 0}
