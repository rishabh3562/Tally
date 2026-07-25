"""complete_json must survive how REAL models actually format output.

This is the seam that decides whether the AI agent path works once GEMINI_API_KEYS
is set: Gemini/OpenRouter routinely wrap JSON in ```json fences or add prose. If
parsing were strict, every real agent turn would fail and silently fall back to the
deterministic path — so these cases are exactly what "the AI parser works" rests on.
No network: the underlying blocking `complete` is monkeypatched to return the raw
string a model would emit.
"""

import pytest

from app.services import llm_client


def _model_returns(monkeypatch, raw: str):
    monkeypatch.setattr(llm_client, "complete", lambda *a, **k: raw)


DECISION = '{"action": "call_tool", "tool": "get_spending_summary", "args": {}}'


def test_plain_json(monkeypatch):
    _model_returns(monkeypatch, DECISION)
    assert llm_client.complete_json("p")["tool"] == "get_spending_summary"


def test_json_fenced_with_language(monkeypatch):
    _model_returns(monkeypatch, f"```json\n{DECISION}\n```")
    assert llm_client.complete_json("p")["action"] == "call_tool"


def test_json_fenced_bare(monkeypatch):
    _model_returns(monkeypatch, f"```\n{DECISION}\n```")
    assert llm_client.complete_json("p")["action"] == "call_tool"


def test_prose_prefixed(monkeypatch):
    _model_returns(monkeypatch, f"Sure! Here is the decision:\n{DECISION}")
    assert llm_client.complete_json("p")["tool"] == "get_spending_summary"


def test_prose_suffixed(monkeypatch):
    _model_returns(monkeypatch, f"{DECISION}\nHope that helps!")
    assert llm_client.complete_json("p")["tool"] == "get_spending_summary"


def test_prose_both_sides(monkeypatch):
    _model_returns(monkeypatch, f"Thinking... {DECISION} — done.")
    assert llm_client.complete_json("p")["action"] == "call_tool"


def test_array_output(monkeypatch):
    _model_returns(monkeypatch, '```json\n["Food & Dining", "Transport"]\n```')
    assert llm_client.complete_json("p") == ["Food & Dining", "Transport"]


def test_unparseable_raises(monkeypatch):
    _model_returns(monkeypatch, "I cannot help with that.")
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete_json("p")
