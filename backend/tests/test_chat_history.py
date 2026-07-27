"""Conversation memory.

Before this, `chat_messages` was written for the UI and nothing else — the model
never saw a previous turn, so "and what about April?" could not work. History now
reaches the tool-SELECTION prompt only: it decides what to look up, while tool
results alone decide what is said (otherwise the model would restate an old figure
and `_verify_figures`, which only knows this turn's results, would reject it).
"""

import asyncio

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
