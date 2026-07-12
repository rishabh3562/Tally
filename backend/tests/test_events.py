"""Tests for the DB-free logic in the events API (summary generation)."""

import pytest

from app.api import events


async def test_summary_empty_transactions():
    out = await events._generate_event_summary("Goa Trip", [])
    assert "Goa Trip" in out
    assert "no transactions" in out.lower()


async def test_summary_falls_back_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: False)
    txns = [{"amount": 500}, {"amount": 250}]
    out = await events._generate_event_summary("Goa Trip", txns)
    assert "Goa Trip" in out
    assert "750" in out            # deterministic total
    assert "2 transactions" in out


async def test_summary_falls_back_on_llm_error(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: True)

    async def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(events.llm_client, "acomplete", boom)
    out = await events._generate_event_summary("Goa Trip", [{"amount": 100}])
    assert "100" in out
    assert "Goa Trip" in out


async def test_summary_uses_llm_output_when_available(monkeypatch):
    monkeypatch.setattr(events.llm_client, "is_available", lambda: True)

    async def ok(*a, **k):
        return "Goa Trip: a lovely getaway."

    monkeypatch.setattr(events.llm_client, "acomplete", ok)
    out = await events._generate_event_summary("Goa Trip", [{"amount": 100}])
    assert out == "Goa Trip: a lovely getaway."
