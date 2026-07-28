"""Answers are markdown — and a table is still policed like a sentence.

Rendering a breakdown as a table is a UI win and a verification risk: a table
looks authoritative, so an unbacked figure in one costs more than the same figure
in prose. These tests pin both halves — the table survives, the invention doesn't.
"""

import pytest

from app.services import chat_agent

from tests.test_chat_agent import _script_llm
from tests.test_chat_service import _mk_db, _txn


_TABLE_ANSWER = (
    "You spent **Rs 150** in June.\n\n"
    "| Category | Amount |\n"
    "| --- | ---: |\n"
    "| Food | Rs 100 |\n"
    "| Transport | Rs 50 |\n"
)


async def test_markdown_table_answer_is_returned_intact(monkeypatch):
    """Pipes, newlines and bold survive the return path unmangled."""
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_by_category",
         "args": {"start": "2026-06-01", "end": "2026-06-30"}},
        {"action": "final", "answer": _TABLE_ANSWER},
    ])
    db = _mk_db(transactions=[_txn(100, category="Food"),
                              _txn(50, category="Transport")])
    out = await chat_agent.run_agent("break down June", "u", db)
    assert "| Food | Rs 100 |" in out
    assert out.count("\n") >= 4          # still a table, not flattened
    assert "**Rs 150**" in out           # bold left alone


async def test_table_row_with_an_invented_figure_is_rejected(monkeypatch):
    """A number the tools never returned is refused even inside a tidy table."""
    bad = _TABLE_ANSWER + "| Shopping | Rs 9,999 |\n"
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_by_category",
         "args": {"start": "2026-06-01", "end": "2026-06-30"}},
        {"action": "final", "answer": bad},
    ], text_response=bad)
    db = _mk_db(transactions=[_txn(100, category="Food"),
                              _txn(50, category="Transport")])
    with pytest.raises(chat_agent.AgentUnavailable):
        await chat_agent.run_agent("break down June", "u", db)


async def test_rupee_sign_inside_a_table_is_normalised(monkeypatch):
    """The INR rewrite runs on table cells too — one currency across the app."""
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_by_category",
         "args": {"start": "2026-06-01", "end": "2026-06-30"}},
        {"action": "final", "answer": "| Food | ₹100 |\n"},
    ])
    db = _mk_db(transactions=[_txn(100, category="Food")])
    out = await chat_agent.run_agent("break down June", "u", db)
    assert "₹" not in out
    assert "Rs 100" in out


def test_both_answer_paths_get_the_same_format_rules():
    """The loop's own 'final' and the finalize call must agree, or the same
    question comes back as a table one time and prose the next."""
    selection = chat_agent._selection_prompt("break down my spending", [])
    finalize = chat_agent._answer_prompt("break down my spending", [])
    for prompt in (selection, finalize):
        assert "markdown table" in prompt
        assert "**bold**" in prompt


def test_format_rules_forbid_derived_columns():
    """`_verify_figures` only checks Rs amounts, so a % or delta column would be an
    unverified number wearing the authority of a table."""
    rules = chat_agent._FORMAT_RULES
    assert "percentage" in rules
    assert "never compute a number the tools did not return" in rules
