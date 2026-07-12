"""Tests for chat_tools — deterministic data tools (fake Supabase, no DB)."""

import pytest

from app.services import chat_tools

from tests.test_chat_service import _mk_db, _txn


def test_get_spending_summary_totals():
    db = _mk_db(transactions=[_txn(100), _txn(50), _txn(-30)])
    out = chat_tools.get_spending_summary(db, "u", start="2026-01-01", end="2026-12-31")
    assert out["total_spent"] == 150
    assert out["total_received"] == 30
    assert out["net"] == -120
    assert out["txn_count"] == 3


def test_get_spending_by_category_grouped_and_sorted():
    db = _mk_db(transactions=[_txn(100, category="Food"), _txn(40, category="Transport"),
                              _txn(60, category="Food")])
    out = chat_tools.get_spending_by_category(db, "u")
    assert out["categories"][0]["name"] == "Food"
    assert out["categories"][0]["total"] == 160
    assert out["total_spent"] == 200


def test_get_spending_by_category_filter_one():
    db = _mk_db(transactions=[_txn(100, category="Food"), _txn(40, category="Transport")])
    out = chat_tools.get_spending_by_category(db, "u", category="food")
    assert len(out["categories"]) == 1
    assert out["categories"][0]["name"] == "Food"


def test_get_top_merchants_ranked_and_clamped():
    db = _mk_db(transactions=[_txn(100, merchant="Zomato"), _txn(60, merchant="Zomato"),
                              _txn(40, merchant="Uber")])
    out = chat_tools.get_top_merchants(db, "u", limit=999)  # clamped to _MAX_ROWS
    assert out["merchants"][0]["name"] == "Zomato"
    assert out["merchants"][0]["total"] == 160
    assert len(out["merchants"]) <= chat_tools._MAX_ROWS


def test_search_transactions_empty_keyword():
    db = _mk_db(transactions=[_txn(100)])
    out = chat_tools.search_transactions(db, "u", keyword="")
    assert out["count"] == 0
    assert out["transactions"] == []


def test_search_transactions_returns_rows():
    db = _mk_db(transactions=[
        {"date": "2026-07-01", "amount": 500, "raw_merchant": "Amazon",
         "counterparty": None, "categories": {"name": "Shopping"}},
    ])
    out = chat_tools.search_transactions(db, "u", keyword="Amazon", limit=5)
    assert out["count"] == 1
    assert out["transactions"][0]["merchant"] == "Amazon"
    assert out["transactions"][0]["amount"] == 500


def test_list_events():
    db = _mk_db(events=[{"name": "Goa Trip", "summary": "fun", "total_amount": 5000}])
    out = chat_tools.list_events(db, "u")
    assert out["events"][0]["name"] == "Goa Trip"
    assert out["events"][0]["total_amount"] == 5000


def test_compare_periods():
    # Same fake DB returns the same rows for both periods (stub ignores filters),
    # so the difference is zero — enough to prove the shape and wiring.
    db = _mk_db(transactions=[_txn(100), _txn(50)])
    out = chat_tools.compare_periods(
        db, "u", period_a_start="2026-07-01", period_a_end="2026-07-31",
        period_b_start="2026-06-01", period_b_end="2026-06-30",
    )
    assert out["period_a"]["total_spent"] == 150
    assert out["period_b"]["total_spent"] == 150
    assert out["spent_difference"] == 0


def test_clamp_limit():
    assert chat_tools._clamp_limit("abc", 10, 15) == 10
    assert chat_tools._clamp_limit(999, 10, 15) == 15
    assert chat_tools._clamp_limit(0, 10, 15) == 1
    assert chat_tools._clamp_limit(7, 10, 15) == 7
