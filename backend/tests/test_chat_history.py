"""Conversation memory.

Before this, `chat_messages` was written for the UI and nothing else — the model
never saw a previous turn, so "and what about April?" could not work. History now
reaches the tool-SELECTION prompt only: it decides what to look up, while tool
results alone decide what is said (otherwise the model would restate an old figure
and `_verify_figures`, which only knows this turn's results, would reject it).
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.services import chat_agent, chat_service as cs


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows):
        self._rows = rows
        self._desc = False
        self._limit = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def order(self, _col, desc=False):
        self._desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def insert(self, *a, **k):
        return self

    def execute(self):
        rows = sorted(self._rows, key=lambda r: r["created_at"], reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _Res(rows)


class _DB:
    def __init__(self, messages=(), txns=()):
        self._m = list(messages)
        self._t = list(txns)

    def table(self, name):
        return _Q(self._m if name == "chat_messages" else self._t)


def _msg(role, content, at):
    return {"role": role, "content": content, "created_at": at}


def _now_iso() -> str:
    """Inside the 30-minute conversation window, so the gap rule keeps it."""
    return datetime.now(timezone.utc).isoformat()


HISTORY = [
    _msg("user", "how much did I spend on food in May 2026", "2026-07-27T10:00:00Z"),
    _msg("assistant", "You spent Rs 4,556 on Food & Dining in May 2026.", "2026-07-27T10:00:05Z"),
]


# --- reading history --------------------------------------------------------

def test_recent_turns_are_oldest_first():
    turns = cs.recent_turns(_DB(messages=HISTORY), "u1")
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["content"].startswith("how much did I spend on food")


def test_recent_turns_is_capped_to_the_most_recent():
    many = [_msg("user", f"q{i}", f"2026-07-27T10:{i:02d}:00Z") for i in range(10)]
    turns = cs.recent_turns(_DB(messages=many), "u1", limit=3)
    assert [t["content"] for t in turns] == ["q7", "q8", "q9"]


def test_history_stops_at_a_conversation_gap():
    """chat_messages persists across sessions (only "New chat" clears it), so
    without a gap rule tomorrow's first question inherits yesterday's scope."""
    rows = [
        _msg("user", "yesterday's question", "2026-07-26T09:00:00+00:00"),
        _msg("assistant", "yesterday's answer", "2026-07-26T09:00:05+00:00"),
        _msg("user", "this sitting", "2026-07-27T10:00:00+00:00"),
        _msg("assistant", "this answer", "2026-07-27T10:00:04+00:00"),
    ]
    now = datetime(2026, 7, 27, 10, 1, tzinfo=timezone.utc)
    turns = cs.recent_turns(_DB(messages=rows), "u1", now=now)
    assert [t["content"] for t in turns] == ["this sitting", "this answer"]


def test_a_stale_conversation_contributes_nothing():
    rows = [_msg("user", "hours ago", "2026-07-27T04:00:00+00:00")]
    now = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    assert cs.recent_turns(_DB(messages=rows), "u1", now=now) == []


def test_unparseable_timestamps_keep_the_row():
    rows = [_msg("user", "no timestamp", None)]
    assert cs.recent_turns(_DB(messages=rows), "u1")[0]["content"] == "no timestamp"


def test_recent_turns_survives_a_broken_table():
    class _Boom:
        def table(self, _n):
            raise RuntimeError("no such table")

    assert cs.recent_turns(_Boom(), "u1") == []


# --- where history is (and is not) used ------------------------------------

def test_history_reaches_the_selection_prompt():
    prompt = chat_agent._selection_prompt("and what about April?", [], HISTORY)
    assert "Earlier in this conversation" in prompt
    assert "how much did I spend on food in May 2026" in prompt
    assert "and what about April?" in prompt


def test_history_never_reaches_the_answer_prompt():
    """Old figures in the answer prompt would be restated and then rejected by
    the figure verifier, which only knows this turn's tool results."""
    prompt = chat_agent._answer_prompt("and what about April?", [])
    assert "Earlier in this conversation" not in prompt
    assert "food in May 2026" not in prompt   # the earlier turn, not the format example


def test_no_history_leaves_the_prompt_as_it_was():
    assert "Earlier in this conversation" not in chat_agent._selection_prompt("q", [])


def test_history_truncates_a_long_message():
    long = [_msg("assistant", "x" * 900, "2026-07-27T10:00:00Z")]
    block = chat_agent._history_block(
        [{"role": "assistant", "content": long[0]["content"]}]
    )
    assert len(block) < 500


# --- end to end -------------------------------------------------------------

def test_a_follow_up_question_is_given_the_previous_turn(monkeypatch):
    """The whole point: the model sees the earlier question when answering a
    fragment that only makes sense in context."""
    seen: list[str] = []

    async def fake_json(prompt, **_):
        seen.append(prompt)
        # No Rs figure: this turn called no tool, so a figure here would (rightly)
        # fail verification and fall back — which would also make this test hit
        # the network through rephrase().
        return {"action": "final", "answer": "About the same as May."}

    async def no_network(*a, **k):
        raise AssertionError("no plain-completion call should be needed here")

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete", no_network)
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(cs.llm_client, "acomplete", no_network)

    # April must have data, or the empty-period fast path answers without the model
    # (correctly — that's the other half of this design).
    april = [{"amount": 700, "date": "2026-04-10", "raw_merchant": "Shop",
              "categories": {"name": "Food"}, "created_at": "2026-04-10"}]
    db = _DB(messages=HISTORY, txns=april)
    asyncio.run(cs._resolve_answer("and what about April?", "u1", db))

    assert seen, "the agent never ran"
    assert "food in May 2026" in seen[0]


# --- a fragment must not be answered instantly at the wrong scope -----------

@pytest.mark.parametrize("fragment", [
    "and per day?",
    "what about each month?",
    "what about the biggest one?",
    "and swiggy?",
])
def test_fragments_are_recognized(fragment):
    assert cs.looks_like_a_follow_up(fragment) is True


@pytest.mark.parametrize("whole", [
    "how much do I spend per day",
    "what are my spending habits",
    "how much did I spend at dmart",
])
def test_whole_questions_are_not_fragments(whole):
    assert cs.looks_like_a_follow_up(whole) is False


def test_a_fragment_with_history_goes_to_the_agent(monkeypatch):
    """"what about each month?" trips the month-breakdown predicate and would be
    answered INSTANTLY with total spend per month — ignoring that the previous
    turn was about food. With a conversation behind it, the agent gets it."""
    assert cs.prefers_deterministic("what about each month?") is True  # the trap
    seen: list[str] = []

    async def fake_json(prompt, **_):
        seen.append(prompt)
        return {"action": "final", "answer": "Here you go."}

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)

    recent = [
        _msg("user", "how much did I spend on food in May 2026", _now_iso()),
        _msg("assistant", "Rs 4,556 on Food & Dining.", _now_iso()),
    ]
    asyncio.run(cs._resolve_answer("what about each month?", "u1", _DB(messages=recent)))
    assert seen and "food in May 2026" in seen[0]


def test_the_same_fragment_with_no_history_is_still_instant(monkeypatch):
    async def never(*a, **k):
        raise AssertionError("no model needed when there's no conversation")

    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", never)

    out = asyncio.run(cs._resolve_answer("what about each month?", "u1", _DB()))
    assert "month by month" in out or "nothing to break down" in out
