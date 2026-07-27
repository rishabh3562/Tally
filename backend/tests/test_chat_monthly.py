"""Two failures taken straight from the user's own chat_traces rows.

  "so what does my spending month wise looks like"  -> 78 SECONDS, and the answer
      was the average and the peak month. No tool could return spend per month, so
      the model reached for the nearest thing it had.
  "what is the current spending last month?"        -> 26 SECONDS to say the period
      is empty (the data ends May 2026) — an answer no model is needed for.
"""

import asyncio

import pytest

from app.services import chat_agent, chat_service as cs, chat_tools


def _tx(amount, d):
    return {"amount": amount, "raw_merchant": "Shop", "date": d,
            "categories": {"name": "Food"}}


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows, sink=None):
        self._rows, self._sink = rows, sink
        self._start = self._end = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, _c, v):
        self._start = v
        return self

    def lte(self, _c, v):
        self._end = v
        return self

    def insert(self, row):
        if self._sink is not None:
            self._sink.append(row)
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
        self.traces: list[dict] = []

    def table(self, name):
        if name == "chat_traces":
            return _Q([], self.traces)
        return _Q(self._rows)


ROWS = [
    _tx(1000, "2025-12-10"),
    _tx(500, "2026-01-05"), _tx(1500, "2026-01-20"),
    _tx(300, "2026-05-31"),
]


# --- month-by-month ---------------------------------------------------------

def test_month_wise_is_not_an_average_question():
    for q in ["so what does my spending month wise looks like",
              "show me spending month by month",
              "what did I spend each month",
              "monthly breakdown please"]:
        assert cs._is_monthly_breakdown_query(q) is True, q
    # Asking for an average means they want the single figure, not the list.
    for q in ["what's my average monthly spend", "average per month", "my run rate"]:
        assert cs._is_monthly_breakdown_query(q) is False, q


def test_monthly_breakdown_lists_every_month():
    out = cs.answer_question("spending month wise", "u1", _DB(ROWS))
    lines = out.split("\n")
    assert lines[0].startswith("Your spending month by month (Rs 3,300 in total)")
    assert lines[1] == "• December 2025 — Rs 1,000"
    assert lines[2] == "• January 2026 — Rs 2,000"
    assert lines[3] == "• May 2026 — Rs 300"
    assert "Biggest month: January 2026" in lines[4]


def test_monthly_breakdown_when_there_is_nothing():
    assert "nothing to break down" in cs.answer_question(
        "monthly breakdown", "u1", _DB([])
    )


def test_monthly_helper_is_shared_with_the_agent_tool():
    res = chat_tools.get_monthly_spending(_DB(ROWS), "u1")
    assert [m["month"] for m in res["months"]] == ["2025-12", "2026-01", "2026-05"]
    assert res["total_spent"] == 3300
    assert "get_monthly_spending" in chat_tools.TOOLS
    assert "get_monthly_spending" in chat_tools.TOOL_SPECS


def test_month_wise_skips_the_model_entirely():
    assert cs.prefers_deterministic("spending month wise") is True


# --- an empty period needs no model ----------------------------------------

def _no_model(monkeypatch):
    async def never(*a, **k):
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", never)
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(cs.llm_client, "acomplete", never)


def test_an_empty_period_answers_instantly(monkeypatch):
    _no_model(monkeypatch)
    db = _DB(ROWS)
    out = asyncio.run(
        cs._resolve_answer("what is the current spending last month?", "u1", db)
    )
    assert "no transactions" in out.lower()
    assert "31 May 2026" in out
    assert db.traces[0]["source"] == "instant"


def test_a_period_WITH_data_still_goes_to_the_model(monkeypatch):
    """Don't steal real questions from the agent — only empty ones."""
    called = {"n": 0}

    async def json_once(*a, **k):
        called["n"] += 1
        return {"action": "final", "answer": "You spent Rs 2,000 in January 2026."}

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", json_once)

    db = _DB(ROWS)
    asyncio.run(cs._resolve_answer("how much did I spend in January 2026", "u1", db))
    assert called["n"] > 0
    assert db.traces[0]["source"] != "instant"
