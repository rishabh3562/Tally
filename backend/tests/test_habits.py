"""Spending habits — the merchants paid most OFTEN.

Motivated by the real data: the recurring detector correctly finds nothing (there
are no monthly subscriptions in these statements), but the same statements have a
canteen paid 28 times and a tea stall paid 22 times. That's where the money goes,
and neither the subscription detector nor top-merchants surfaces it.
"""

from app.services import chat_service, chat_tools
from app.services.habits import detect_habits


def _tx(amount, date, merchant):
    return {"amount": amount, "date": date, "raw_merchant": merchant}


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

    def table(self, _name):
        return _Q(self._rows)


# A canteen tapped constantly, plus one big one-off that must NOT be a habit.
CANTEEN = [_tx(80, f"2026-05-{d:02d}", "HungerBox") for d in range(1, 13)]
ONE_OFF = [_tx(47805, "2026-03-30", "AmazonIndia")]


def test_frequent_merchant_is_detected():
    items = detect_habits(CANTEEN + ONE_OFF)
    assert [i["merchant"] for i in items] == ["HungerBox"]
    h = items[0]
    assert h["count"] == 12
    assert h["total"] == 960
    assert h["avg"] == 80


def test_a_single_big_spend_is_not_a_habit():
    assert detect_habits(ONE_OFF) == []


def test_min_count_is_respected():
    rows = [_tx(50, f"2026-05-0{d}", "Chai") for d in range(1, 5)]  # 4 payments
    assert detect_habits(rows) == []
    assert len(detect_habits(rows, min_count=4)) == 1


def test_credits_are_ignored():
    rows = [_tx(-100, f"2026-05-{d:02d}", "Refunds") for d in range(1, 10)]
    assert detect_habits(rows) == []


def test_per_month_uses_the_span_the_payments_cover():
    """A burst inside one month is a high monthly rate, not a divide-by-zero."""
    items = detect_habits(CANTEEN)          # 12 payments inside 12 days
    assert items[0]["per_month"] == 12.0    # span floored at one month
    spread = [_tx(80, d, "Gym") for d in
              ["2026-01-05", "2026-02-05", "2026-03-05", "2026-04-05", "2026-05-05"]]
    assert detect_habits(spread)[0]["per_month"] == 1.3


def test_ranked_by_frequency_not_by_total():
    rows = CANTEEN + [_tx(5000, f"2026-04-{d:02d}", "Bigshop") for d in range(1, 7)]
    assert [i["merchant"] for i in detect_habits(rows)] == ["HungerBox", "Bigshop"]


def test_merchant_variants_are_counted_as_one_brand():
    rows = (
        [_tx(200, f"2026-05-{d:02d}", "SWIGGY") for d in (1, 2, 3)]
        + [_tx(200, f"2026-05-{d:02d}", "BundlTechnologiespvtLtd") for d in (4, 5, 6)]
    )
    items = detect_habits(rows)
    assert len(items) == 1 and items[0]["count"] == 6


# --- chat wiring ------------------------------------------------------------

def test_habit_questions_are_recognized():
    for q in [
        "what are my spending habits",
        "what do I buy most often",
        "which merchant do I pay most frequently",
        "what small purchases add up",
    ]:
        assert chat_service._is_habit_query(q) is True, q
    for q in ["how much did I spend on food", "what are my subscriptions"]:
        assert chat_service._is_habit_query(q) is False, q


def test_habits_answer_is_a_listing():
    out = chat_service.answer_question(
        "what are my spending habits", "u1", _DB(CANTEEN + ONE_OFF)
    )
    lines = out.split("\n")
    assert lines[0] == "The places you pay most often:"
    assert lines[1].startswith("• HungerBox — 12 payments, Rs 960")
    assert "/month" in lines[1]


def test_habits_answer_when_there_is_no_habit():
    out = chat_service.answer_question("what are my spending habits", "u1", _DB(ONE_OFF))
    assert "habit" in out.lower()
    assert "•" not in out


def test_agent_tool_returns_habits():
    res = chat_tools.get_frequent_merchants(_DB(CANTEEN), "u1")
    assert res["count"] == 1
    assert res["combined_total"] == 960
    assert res["habits"][0]["merchant"] == "HungerBox"


def test_tool_is_registered_for_the_agent():
    assert "get_frequent_merchants" in chat_tools.TOOLS
    assert "get_frequent_merchants" in chat_tools.TOOL_SPECS
