"""Breakdown answers are listings, not run-on sentences.

Line breaks survive the SSE transport now (`test_chat_service` covers the wire),
so a "top categories / top merchants / biggest expenses / subscriptions" answer
is a headline plus one item per line. These assert the shape, and that the LLM
rephrase step can't flatten it back into prose.
"""

import asyncio

from app.services import chat_service as cs


def _tx(amount, date, merchant="X", category=None):
    return {
        "amount": amount,
        "raw_merchant": merchant,
        "date": date,
        "categories": {"name": category} if category else None,
    }


ROWS = [
    _tx(600, "2026-03-01", "Amazon", "Shopping"),
    _tx(400, "2026-03-02", "Amazon", "Shopping"),
    _tx(300, "2026-03-03", "Swiggy", "Food & Dining"),
    _tx(100, "2026-03-04", "DMart", "Groceries"),
]


def test_listing_shape():
    out = cs._listing("Head:", ["a", "b"], footer="tail")
    assert out.split("\n") == ["Head:", "• a", "• b", "tail"]


def test_share_is_omitted_below_one_percent_and_for_zero_totals():
    assert cs._share(50, 100) == " · 50%"
    assert cs._share(0.1, 1000) == ""
    assert cs._share(10, 0) == ""


def test_category_breakdown_is_one_line_per_category():
    out = cs._answer_total_by_category(ROWS, "where did my money go", "March 2026")
    lines = out.split("\n")
    assert lines[0].startswith("For March 2026 you spent Rs 1,400")
    assert lines[1] == "• Shopping — Rs 1,000 · 71%"
    assert any(line.startswith("• Food & Dining — Rs 300") for line in lines)


def test_merchant_breakdown_counts_payments_per_line():
    out = cs._answer_merchant_breakdown(ROWS, "all time")
    lines = out.split("\n")
    assert lines[0] == "Your top merchants for all time:"
    assert lines[1] == "• Amazon — Rs 1,000 · 71% (2 payments)"
    assert "(1 payment)" in out          # singular, not "1 payments"


def test_biggest_expenses_lead_with_the_amount():
    out = cs._answer_biggest(ROWS, "March 2026")
    lines = out.split("\n")
    assert lines[0] == "Your biggest expenses for March 2026:"
    assert lines[1] == "• Rs 600 — Amazon on 1 Mar 2026"
    assert len(lines) == 4              # headline + top 3


def test_single_figure_answers_stay_one_line():
    """Only breakdowns become listings — a one-number answer must not grow bullets."""
    out = cs._answer_total_by_category(ROWS, "how much did I spend on shopping", "March 2026")
    assert "\n" not in out
    assert "Rs 1,000" in out


def test_rephrase_leaves_a_listing_untouched(monkeypatch):
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)

    async def boom(*a, **k):  # must never be called for a structured answer
        raise AssertionError("rephrase called on a multi-line answer")

    monkeypatch.setattr(cs.llm_client, "acomplete", boom)
    listing = "Top categories:\n• Shopping — Rs 1,000"
    assert asyncio.run(cs.rephrase("where did my money go", listing)) == listing


def test_rephrase_still_runs_for_single_line_answers(monkeypatch):
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)

    async def fake(*a, **k):
        return "You spent Rs 1,000 on shopping."

    monkeypatch.setattr(cs.llm_client, "acomplete", fake)
    out = asyncio.run(cs.rephrase("q", "You spent Rs 1,000 on shopping in March."))
    assert out == "You spent Rs 1,000 on shopping."
