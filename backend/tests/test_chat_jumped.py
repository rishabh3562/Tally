"""'What jumped this month' — biggest month-over-month category increase."""

from app.services import chat_service


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

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def execute(self):
        return _Res(self._rows)


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _Q(self._rows)


def test_is_change_query():
    assert chat_service._is_change_query("what jumped this month") is True
    assert chat_service._is_change_query("what went up vs last month") is True
    assert chat_service._is_change_query("which category changed the most") is True
    assert chat_service._is_change_query("how much did I spend on food") is False


def test_reports_biggest_increase():
    rows = [
        _tx(1000, "2026-02-05", "Food"),
        _tx(1000, "2026-02-06", "Transport"),
        _tx(3000, "2026-03-05", "Food"),        # Food +2000
        _tx(1200, "2026-03-06", "Transport"),   # Transport +200
    ]
    out = chat_service._answer_what_jumped(_DB(rows), "u1")
    assert "Food" in out
    assert "Rs 2,000" in out           # the increase
    assert "2026-03" in out and "2026-02" in out


def test_flat_or_down_says_nothing_rose():
    rows = [
        _tx(3000, "2026-02-05", "Food"),
        _tx(1000, "2026-03-05", "Food"),   # went DOWN
    ]
    out = chat_service._answer_what_jumped(_DB(rows), "u1")
    assert "Nothing rose" in out


def test_needs_two_months():
    rows = [_tx(1000, "2026-03-05", "Food")]
    out = chat_service._answer_what_jumped(_DB(rows), "u1")
    assert "at least two months" in out
