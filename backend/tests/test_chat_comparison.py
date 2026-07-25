"""Deterministic period-comparison — 'this month vs last month' now answers as a
comparison instead of falling through to a generic summary (keyless path)."""

from datetime import date

from app.services import chat_service as cs
from tests.test_chat_service import _mk_db, _txn


TODAY = date(2026, 7, 15)


def test_parse_two_periods_vs():
    a, b = cs.parse_two_periods("this month vs last month", TODAY)
    assert a == ("2026-07-01", "2026-07-15")     # this month, to today
    assert b == ("2026-06-01", "2026-06-30")     # last month, full


def test_parse_two_periods_than():
    res = cs.parse_two_periods("did I spend more this month than last month", TODAY)
    assert res is not None
    (a, b) = res
    assert a[0] == "2026-07-01"
    assert b == ("2026-06-01", "2026-06-30")


def test_parse_two_periods_named_months():
    a, b = cs.parse_two_periods("compare June and July", TODAY)
    assert a == ("2026-06-01", "2026-06-30")
    assert b == ("2026-07-01", "2026-07-31")


def test_parse_two_periods_none_when_unresolvable():
    assert cs.parse_two_periods("how much did I spend", TODAY) is None


# The shared _mk_db fake doesn't filter by date, so use a date-aware one to prove
# the two periods actually resolve to different totals.
class _DateResult:
    def __init__(self, data):
        self.data = data


class _DateTable:
    def __init__(self, rows):
        self._rows = rows
        self._ge = None
        self._le = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, col, val):
        self._ge = val
        return self

    def lte(self, col, val):
        self._le = val
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        rows = self._rows
        if self._ge:
            rows = [r for r in rows if r["date"] >= self._ge]
        if self._le:
            rows = [r for r in rows if r["date"] <= self._le]
        return _DateResult(rows)


class _DateDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _DateTable(self._rows)


def test_comparison_intent_routes_and_computes():
    # more spend in June than July -> "more in the first".
    db = _DateDB([
        {"amount": 300, "date": "2026-06-10", "raw_merchant": "A", "categories": None},
        {"amount": 100, "date": "2026-07-10", "raw_merchant": "B", "categories": None},
    ])
    out = cs.answer_question("compare June and July", "u1", db)
    assert "Rs 300" in out
    assert "Rs 100" in out
    assert "more in the first" in out


def test_comparison_classified_as_comparison():
    assert cs.classify_intent("did I spend more this month than last month") == (
        cs.IntentType.PERIOD_COMPARISON
    )


def test_amount_threshold_is_not_hijacked_as_comparison():
    # "more than 500" is an amount, not two periods — must stay category-aware.
    assert cs.classify_intent("did I spend more than 500 on food") == (
        cs.IntentType.TOTAL_BY_CATEGORY
    )
    db = _DateDB([
        {"amount": 300, "date": "2026-07-10", "raw_merchant": "Zomato",
         "categories": {"name": "Food"}},
    ])
    out = cs.answer_question("did I spend more than 500 on food", "u1", db)
    assert "food" in out.lower()      # the category filter survived
