"""Tests for the agentic chat loop (fake LLM + fake Supabase, no network/DB)."""

import pytest

from app.services import chat_agent

from tests.test_chat_service import _mk_db, _txn


def _script_llm(monkeypatch, json_responses, text_response="Rs 150 spent.", available=True):
    """Wire chat_agent.llm_client with scripted async responses.

    json_responses is a list consumed one-per acomplete_json call; text_response is
    returned by the finalize acomplete call.
    """
    monkeypatch.setattr(chat_agent.llm_client, "is_available", lambda: available)

    seq = list(json_responses)

    async def fake_json(*a, **k):
        if not seq:
            raise AssertionError("acomplete_json called more times than scripted")
        return seq.pop(0)

    async def fake_text(*a, **k):
        return text_response

    monkeypatch.setattr(chat_agent.llm_client, "acomplete_json", fake_json)
    monkeypatch.setattr(chat_agent.llm_client, "acomplete", fake_text)


async def test_agent_single_tool_then_final(monkeypatch):
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_summary", "args": {"start": "2026-06-01", "end": "2026-06-30"}},
        {"action": "final", "answer": "You spent Rs 150 in June."},
    ])
    db = _mk_db(transactions=[_txn(100), _txn(50)])
    out = await chat_agent.run_agent("how much in June", "u", db)
    assert out == "You spent Rs 150 in June."


async def test_agent_finalizes_after_max_steps(monkeypatch):
    # Model keeps calling tools; after max_steps we synthesise the answer via acomplete.
    call = {"action": "call_tool", "tool": "get_spending_summary", "args": {}}
    _script_llm(monkeypatch, [call, call], text_response="You spent Rs 150 overall.")
    db = _mk_db(transactions=[_txn(100), _txn(50)])
    out = await chat_agent.run_agent("summary", "u", db, max_steps=2)
    assert out == "You spent Rs 150 overall."


async def test_agent_unavailable_when_no_llm(monkeypatch):
    _script_llm(monkeypatch, [], available=False)
    db = _mk_db(transactions=[_txn(100)])
    with pytest.raises(chat_agent.AgentUnavailable):
        await chat_agent.run_agent("anything", "u", db)


async def test_agent_unavailable_when_no_tool_results(monkeypatch):
    # First decision is garbage / unrecognised action -> no transcript -> unavailable.
    _script_llm(monkeypatch, [{"action": "chitchat"}])
    db = _mk_db(transactions=[_txn(100)])
    with pytest.raises(chat_agent.AgentUnavailable):
        await chat_agent.run_agent("hi", "u", db)


async def test_agent_handles_unknown_tool_then_finalizes(monkeypatch):
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "does_not_exist", "args": {}},
        {"action": "call_tool", "tool": "get_spending_summary", "args": {}},
    ], text_response="You spent Rs 150.")
    db = _mk_db(transactions=[_txn(100), _txn(50)])
    out = await chat_agent.run_agent("summary", "u", db, max_steps=2)
    assert out == "You spent Rs 150."


def test_normalize_currency():
    assert chat_agent._normalize_currency("You spent $1,800.00 on food") == "You spent Rs 1,800.00 on food"
    assert chat_agent._normalize_currency("₹2,500 and ₹1,500") == "Rs 2,500 and Rs 1,500"
    assert chat_agent._normalize_currency("total Rs 4,000") == "total Rs 4,000"


async def test_agent_final_answer_is_normalized(monkeypatch):
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_summary", "args": {}},
        {"action": "final", "answer": "You spent $150 total."},
    ])
    db = _mk_db(transactions=[_txn(100), _txn(50)])
    out = await chat_agent.run_agent("summary", "u", db)
    assert out == "You spent Rs 150 total."
    assert "$" not in out


async def test_agent_strips_privileged_args(monkeypatch):
    # A malicious/confused model tries to pass user_id; it must be ignored, not
    # forwarded to the tool (which would raise a duplicate-arg TypeError otherwise).
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_summary",
         "args": {"user_id": "someone-else", "db": "x"}},
        {"action": "final", "answer": "ok Rs 100"},
    ])
    db = _mk_db(transactions=[_txn(100)])
    out = await chat_agent.run_agent("summary", "u", db)
    assert out == "ok Rs 100"
