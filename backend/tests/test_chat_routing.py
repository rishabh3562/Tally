"""Which path answers which question.

The bug this locks down: with GEMINI_API_KEYS set, `_resolve_answer` sent EVERY
question to the agent, so the dedicated deterministic handlers (the capability
menu, data coverage, habits, recurring, averages, what-jumped) only ever ran when
the LLM was down. Two of them the agent cannot answer at all — there is no
coverage tool, and the only average tool is monthly.
"""

import asyncio

import pytest

from app.services import chat_agent, chat_service as cs


def _tx(amount, d, merchant="Shop", category="Food"):
    return {"amount": amount, "raw_merchant": merchant, "date": d,
            "categories": {"name": category}}


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows):
        self._rows = rows
        self.inserted: list[dict] = []

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def insert(self, row):
        self._sink.append(row)
        return self

    def execute(self):
        return _Res(self._rows)


class _DB:
    """Records chat_traces inserts so we can assert on the recorded source."""

    def __init__(self, rows):
        self._rows = rows
        self.traces: list[dict] = []

    def table(self, name):
        q = _Q([] if name == "chat_traces" else self._rows)
        q._sink = self.traces if name == "chat_traces" else []
        return q


ROWS = [_tx(80, f"2026-05-{d:02d}", "HungerBox") for d in range(1, 8)]


@pytest.fixture(autouse=True)
def _llm_is_up(monkeypatch):
    """Every test here runs as if a key IS set — that's the broken case."""
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)

    async def never(*a, **k):
        raise AssertionError("the model must not be called for this question")

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", never)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete", never)
    monkeypatch.setattr(cs.llm_client, "acomplete", never)


@pytest.mark.parametrize("question", [
    "help",
    "what can you do",
    "how many transactions do I have",
    "when did I start",
    "what do I buy most often",
    "what are my recurring payments",
    "what's my average monthly spend",
    "how much do I spend per day",
    "what jumped this month",
])
def test_dedicated_handlers_skip_the_model(question):
    assert cs.prefers_deterministic(question) is True, question
    db = _DB(ROWS)
    # The fixture makes any model call raise, so reaching an answer proves the
    # agent was never consulted.
    answer = asyncio.run(cs._resolve_answer(question, "u1", db))
    assert answer
    assert db.traces and db.traces[0]["source"] == "instant"


@pytest.mark.parametrize("question", [
    "which merchants did I spend the most at",
    "where did my money go",
    "what was my biggest expense",
    "how much money did I get back",
    "how much did I spend at dmart",
])
def test_shapes_the_live_model_did_worse_or_slower_are_also_instant(question):
    """Measured, not assumed: the merchant ranking took 68s through the agent for
    a re-rendering of the same tool output, and its keyword search answered
    "Rs 0" for DMart (stored as AVENUESUPERMARTS)."""
    assert cs.prefers_deterministic(question) is True, question


@pytest.mark.parametrize("question", [
    "how much did I spend on food last month",
    "put all my amazon purchases under Shopping",
    "did I spend more this month than last month",
    "how much did I spend in March 2026",
    "how much on food at restaurants",
])
def test_general_questions_still_go_to_the_agent(question):
    """The model handles arbitrary phrasing better and its figures are verified —
    don't steal those questions from it."""
    assert cs.prefers_deterministic(question) is False, question


def test_instant_answers_are_not_rephrased():
    """rephrase() would flatten a listing and could reword a menu; the fixture
    raises if it's called."""
    db = _DB(ROWS)
    out = asyncio.run(cs._resolve_answer("what do I buy most often", "u1", db))
    assert out.startswith("The places you pay most often:")
    assert "\n• HungerBox" in out
