"""Asking about a period with no data must say so — not report "Rs 0".

Caught from a real trace: with statements covering Dec 2025 – May 2026, "how
much did I spend on food last month?" answered "You spent Rs 0 on food in June
2026", which is true and useless. Both chat paths (deterministic and agent) now
name the empty period and the range that actually has data.
"""

import asyncio

import pytest

from app.services import chat_agent, chat_service, chat_tools


def _tx(amount, date, merchant="X", category=None):
    return {
        "amount": amount,
        "raw_merchant": merchant,
        "date": date,
        "categories": {"name": category} if category else None,
    }


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    """PostgREST-shaped stub that actually honours the date filters, so an
    out-of-range period really comes back empty."""

    def __init__(self, rows):
        self._rows = rows
        self._start = None
        self._end = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, _col, value):
        self._start = value
        return self

    def lte(self, _col, value):
        self._end = value
        return self

    def execute(self):
        rows = self._rows
        if self._start:
            rows = [r for r in rows if r["date"] >= self._start]
        if self._end:
            rows = [r for r in rows if r["date"] <= self._end]
        return _Res(rows)


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _Q(self._rows)


ROWS = [
    _tx(500, "2025-12-07", "Swiggy", "Food & Dining"),
    _tx(700, "2026-03-14", "Amazon", "Shopping"),
    _tx(900, "2026-05-31", "DMart", "Groceries"),
]


# --- pieces -----------------------------------------------------------------

def test_data_coverage_reports_first_and_last():
    cov = chat_service.data_coverage(_DB(ROWS), "u1")
    assert cov == {"first": "2025-12-07", "last": "2026-05-31", "count": 3}


def test_data_coverage_empty():
    assert chat_service.data_coverage(_DB([]), "u1")["first"] is None


def test_pretty_period_names_whole_months():
    assert chat_service._pretty_period("2026-06-01", "2026-06-30") == "June 2026"
    assert chat_service._pretty_period("2026-01-01", "2026-03-31") == "January 2026 to March 2026"
    assert chat_service._pretty_period("2026-06-03", "2026-06-09") == "3 Jun 2026 to 9 Jun 2026"


def test_pretty_date_is_platform_independent():
    assert chat_service._pretty_date("2025-12-07") == "7 Dec 2025"
    assert chat_service._pretty_date("nonsense") == "nonsense"


# --- deterministic path -----------------------------------------------------

def test_question_about_an_empty_month_names_the_real_range():
    out = chat_service.answer_question(
        "how much did I spend on food last month?", "u1", _DB(ROWS),
    )
    assert "no transactions" in out.lower()
    assert "7 Dec 2025" in out and "31 May 2026" in out
    assert "Rs 0" not in out


def test_empty_period_answer_when_nothing_is_imported_at_all():
    out = chat_service.answer_question(
        "how much did I spend last month?", "u1", _DB([]),
    )
    assert "no transactions imported yet" in out.lower()


def test_a_period_with_data_still_answers_normally():
    out = chat_service.answer_question(
        "how much did I spend in March 2026?", "u1", _DB(ROWS),
    )
    assert "Rs 700" in out


def test_all_time_question_is_not_treated_as_an_empty_period():
    """No period parsed => unbounded => must not claim "no transactions in ..."."""
    out = chat_service.answer_question("where did my money go", "u1", _DB(ROWS))
    assert "no transactions in" not in out.lower()


def test_comparison_of_two_empty_periods_names_the_real_range():
    out = chat_service._answer_comparison(
        _DB(ROWS), "u1", "did I spend more this month than last month",
    )
    assert "no transactions" in out.lower()
    assert "7 Dec 2025" in out


# --- tool results -----------------------------------------------------------

def test_tools_flag_an_empty_bounded_period():
    res = chat_tools.get_spending_by_category(
        _DB(ROWS), "u1", start="2026-06-01", end="2026-06-30",
    )
    assert res["no_data_in_period"] is True
    assert res["data_covers"] == {"first": "2025-12-07", "last": "2026-05-31"}
    assert res["period_start"] == "2026-06-01"


def test_tools_do_not_flag_a_period_that_has_data():
    res = chat_tools.get_spending_summary(
        _DB(ROWS), "u1", start="2026-03-01", end="2026-03-31",
    )
    assert "no_data_in_period" not in res


def test_tools_do_not_flag_an_unbounded_query():
    res = chat_tools.get_top_merchants(_DB([]), "u1")
    assert "no_data_in_period" not in res


# --- agent path -------------------------------------------------------------

def test_agent_composes_the_empty_period_answer_itself(monkeypatch):
    """The model's "you spent Rs 0" is replaced by ours, which is useful."""
    calls = {"n": 0}

    async def fake_json(prompt, **_):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "action": "call_tool",
                "tool": "get_spending_by_category",
                "args": {"start": "2026-06-01", "end": "2026-06-30", "category": "food"},
            }
        return {"action": "final", "answer": "You spent Rs 0 on food in June 2026."}

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)

    out = asyncio.run(
        chat_agent.run_agent("how much did I spend on food last month?", "u1", _DB(ROWS))
    )
    assert "no transactions in June 2026" in out
    assert "7 Dec 2025" in out
    assert "Rs 0" not in out


def test_agent_keeps_the_model_answer_when_the_period_has_data(monkeypatch):
    calls = {"n": 0}

    async def fake_json(prompt, **_):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "action": "call_tool",
                "tool": "get_spending_summary",
                "args": {"start": "2026-03-01", "end": "2026-03-31"},
            }
        return {"action": "final", "answer": "You spent Rs 700 in March 2026."}

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)

    out = asyncio.run(chat_agent.run_agent("what did I spend in march", "u1", _DB(ROWS)))
    assert out == "You spent Rs 700 in March 2026."


def test_compare_periods_hoists_the_flag_when_both_sides_are_empty():
    """chat_agent only inspects the outermost result, so a nested flag is invisible."""
    res = chat_tools.compare_periods(
        _DB(ROWS), "u1",
        period_a_start="2026-06-01", period_a_end="2026-06-30",
        period_b_start="2026-07-01", period_b_end="2026-07-31",
    )
    assert res["no_data_in_period"] is True
    assert res["period_start"] == "2026-06-01"
    assert res["period_end"] == "2026-07-31"


def test_compare_periods_does_not_flag_when_one_side_has_data():
    res = chat_tools.compare_periods(
        _DB(ROWS), "u1",
        period_a_start="2026-03-01", period_a_end="2026-03-31",
        period_b_start="2026-06-01", period_b_end="2026-06-30",
    )
    assert "no_data_in_period" not in res


def test_agent_answers_an_all_empty_comparison_itself(monkeypatch):
    calls = {"n": 0}

    async def fake_json(prompt, **_):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "action": "call_tool",
                "tool": "compare_periods",
                "args": {
                    "period_a_start": "2026-07-01", "period_a_end": "2026-07-31",
                    "period_b_start": "2026-06-01", "period_b_end": "2026-06-30",
                },
            }
        return {"action": "final", "answer": "You spent Rs 0 in both months."}

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)

    out = asyncio.run(
        chat_agent.run_agent("did I spend more this month than last?", "u1", _DB(ROWS))
    )
    assert "no transactions" in out.lower()
    assert "31 May 2026" in out
    assert "Rs 0" not in out


def test_agent_leaves_the_answer_alone_when_one_tool_did_find_data(monkeypatch):
    """A mixed transcript (one empty period, one with data) is a real comparison —
    the model's answer must survive."""
    steps = [
        {
            "action": "call_tool",
            "tool": "get_spending_summary",
            "args": {"start": "2026-06-01", "end": "2026-06-30"},
        },
        {
            "action": "call_tool",
            "tool": "get_spending_summary",
            "args": {"start": "2026-03-01", "end": "2026-03-31"},
        },
        {"action": "final", "answer": "You spent Rs 700 in March and Rs 0 in June."},
    ]
    it = iter(steps)

    async def fake_json(prompt, **_):
        return next(it)

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)

    out = asyncio.run(chat_agent.run_agent("june vs march", "u1", _DB(ROWS)))
    assert out == "You spent Rs 700 in March and Rs 0 in June."


# --- the same problem one level down: the period has data, the CATEGORY doesn't --
# Found live: "what about groceries that month?" -> "You spent Rs 0 on groceries in
# May 2026." True, useless, and 91% of this data is still "Other" — so an empty
# category answer is usually a labelling gap, and should say so.

MIXED = [
    _tx(21000, "2026-05-02", "Landlord", "Rent"),
    _tx(9000, "2026-05-10", "SomeUpiName", "Other"),
    _tx(500, "2026-05-11", "Swiggy", "Food & Dining"),
]


def test_tool_flags_a_category_with_no_rows_in_a_period_that_has_some():
    res = chat_tools.get_spending_by_category(
        _DB(MIXED), "u1", start="2026-05-01", end="2026-05-31", category="groceries",
    )
    assert res["no_data_for_category"] is True
    assert res["category_requested"] == "groceries"
    assert res["uncategorized_total"] == 9000
    assert [c["name"] for c in res["categories_present"]][0] == "Rent"
    # NOT the empty-period flag: the period itself has spending.
    assert "no_data_in_period" not in res


def test_tool_does_not_flag_a_category_that_has_rows():
    res = chat_tools.get_spending_by_category(
        _DB(MIXED), "u1", start="2026-05-01", end="2026-05-31", category="rent",
    )
    assert "no_data_for_category" not in res


def test_deterministic_answer_says_what_is_there_instead():
    out = chat_service.answer_question(
        "how much did I spend on groceries in May 2026", "u1", _DB(MIXED),
    )
    assert "Nothing is tagged 'groceries' in May 2026" in out
    assert "Rent — Rs 21,000" in out
    assert "still uncategorised" in out
    assert "Rs 0" not in out


def test_agent_composes_the_empty_category_answer_itself(monkeypatch):
    calls = {"n": 0}

    async def fake_json(prompt, **_):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "action": "call_tool",
                "tool": "get_spending_by_category",
                "args": {"start": "2026-05-01", "end": "2026-05-31",
                         "category": "groceries"},
            }
        return {"action": "final", "answer": "You spent Rs 0 on groceries in May 2026."}

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)

    out = asyncio.run(
        chat_agent.run_agent("groceries in may?", "u1", _DB(MIXED))
    )
    assert "Nothing is tagged 'groceries' in May 2026" in out
    assert "Rs 0" not in out
