"""Recurring-payment (subscription) detection + its chat integration.

Pure detector logic plus the deterministic chat answer and the read tool. No
network/DB — a tiny fake returns canned transaction rows.
"""

from app.services.recurring import detect_recurring
from app.services import chat_service, chat_tools


def _tx(merchant, amount, date):
    return {"amount": amount, "raw_merchant": merchant, "date": date}


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


# --- detector ---------------------------------------------------------------

def test_detects_regular_monthly_same_amount():
    txns = [
        _tx("Netflix", 199, "2026-01-05"),
        _tx("Netflix", 199, "2026-02-04"),
        _tx("Netflix", 199, "2026-03-06"),
    ]
    out = detect_recurring(txns)
    assert len(out) == 1
    assert out[0]["merchant"] == "Netflix"
    assert out[0]["monthly"] == 199
    assert out[0]["count"] == 3


def test_irregular_gaps_not_recurring():
    # gaps 2 and 57 days — nowhere near a steady monthly cadence.
    txns = [
        _tx("Blinkit", 199, "2026-01-01"),
        _tx("Blinkit", 199, "2026-01-03"),
        _tx("Blinkit", 199, "2026-03-01"),
    ]
    assert detect_recurring(txns) == []


def test_varying_amounts_not_recurring():
    txns = [
        _tx("Zomato", 100, "2026-01-05"),
        _tx("Zomato", 300, "2026-02-04"),
        _tx("Zomato", 100, "2026-03-06"),
    ]
    assert detect_recurring(txns) == []


def test_two_occurrences_below_threshold():
    txns = [_tx("Gym", 500, "2026-01-05"), _tx("Gym", 500, "2026-02-04")]
    assert detect_recurring(txns) == []


def test_credits_are_ignored():
    # Negative = received; a monthly salary credit is not a subscription.
    txns = [
        _tx("Employer", -50000, "2026-01-01"),
        _tx("Employer", -50000, "2026-02-01"),
        _tx("Employer", -50000, "2026-03-01"),
    ]
    assert detect_recurring(txns) == []


def test_sorted_by_monthly_cost_desc():
    txns = [
        _tx("Cheap", 99, "2026-01-05"), _tx("Cheap", 99, "2026-02-04"), _tx("Cheap", 99, "2026-03-06"),
        _tx("Pricey", 999, "2026-01-10"), _tx("Pricey", 999, "2026-02-09"), _tx("Pricey", 999, "2026-03-11"),
    ]
    out = detect_recurring(txns)
    assert [r["merchant"] for r in out] == ["Pricey", "Cheap"]


# --- chat integration -------------------------------------------------------

def test_is_recurring_query_distinguishes_list_from_amount():
    assert chat_service._is_recurring_query("what are my subscriptions") is True
    assert chat_service._is_recurring_query("show my recurring payments") is True
    # "how much on subscriptions" is a category-spend question, not a list.
    assert chat_service._is_recurring_query("how much on subscriptions") is False
    assert chat_service._is_recurring_query("how much did I spend on food") is False


def test_answer_recurring_lists_the_payment():
    rows = [
        _tx("Netflix", 199, "2026-01-05"),
        _tx("Netflix", 199, "2026-02-04"),
        _tx("Netflix", 199, "2026-03-06"),
    ]
    out = chat_service._answer_recurring(_DB(rows), "u1")
    assert "Netflix" in out and "Rs 199" in out


def test_answer_recurring_empty_is_graceful():
    out = chat_service._answer_recurring(_DB([]), "u1")
    assert "couldn't spot" in out.lower()


def test_recurring_tool_returns_total():
    rows = [
        _tx("Netflix", 199, "2026-01-05"),
        _tx("Netflix", 199, "2026-02-04"),
        _tx("Netflix", 199, "2026-03-06"),
    ]
    out = chat_tools.get_recurring_payments(_DB(rows), "u1")
    assert out["count"] == 1
    assert out["monthly_total"] == 199
    assert out["recurring"][0]["merchant"] == "Netflix"
