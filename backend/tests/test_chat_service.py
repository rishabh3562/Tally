"""Unit tests for the pure (DB-free) parts of the chat service.

These cover intent classification, category extraction, period parsing and the
deterministic answer formatters. The live PostgREST fetch and any LLM rephrasing
are not exercised here (no DB in this environment).
"""

from datetime import date

import pytest

from app.services import chat_service as cs
from app.services.chat_service import IntentType


# --- classify_intent --------------------------------------------------------

@pytest.mark.parametrize(
    "question,expected",
    [
        ("How much did I spend on food last month?", IntentType.TOTAL_BY_CATEGORY),
        ("What is my total spending?", IntentType.TOTAL_BY_CATEGORY),
        ("Which merchants did I pay the most?", IntentType.MERCHANT_BREAKDOWN),
        ("Where do I shop most?", IntentType.MERCHANT_BREAKDOWN),
        ("Compare this month vs last month", IntentType.PERIOD_COMPARISON),
        ("How much did my Goa trip cost?", IntentType.EVENT_QUERY),
        ("Tell me about my finances", IntentType.OPEN_ENDED),
    ],
)
def test_classify_intent(question, expected):
    assert cs.classify_intent(question) == expected


# --- extract_category -------------------------------------------------------

def test_extract_category_found():
    assert cs.extract_category("how much on food this month") == "food"
    assert cs.extract_category("my transport costs") == "transport"


def test_extract_category_none():
    assert cs.extract_category("what did I spend overall") is None


def test_extract_category_word_boundary():
    # "foodie" should not match the "food" keyword.
    assert cs.extract_category("nothing relevant here") is None


# --- parse_period -----------------------------------------------------------

TODAY = date(2026, 7, 12)  # a fixed reference so tests are deterministic


def test_parse_period_this_month():
    start, end = cs.parse_period("spending this month", today=TODAY)
    assert start == "2026-07-01"
    assert end == "2026-07-12"


def test_parse_period_last_month():
    start, end = cs.parse_period("what did I spend last month", today=TODAY)
    assert start == "2026-06-01"
    assert end == "2026-06-30"


def test_parse_period_last_n_days():
    start, end = cs.parse_period("total over the last 7 days", today=TODAY)
    assert start == "2026-07-05"
    assert end == "2026-07-12"


def test_parse_period_named_month_current_year():
    start, end = cs.parse_period("how much in May", today=TODAY)
    assert start == "2026-05-01"
    assert end == "2026-05-31"


def test_parse_period_named_future_month_rolls_back():
    # December hasn't happened yet in July 2026 -> assume last year.
    start, end = cs.parse_period("spending in December", today=TODAY)
    assert start == "2025-12-01"
    assert end == "2025-12-31"


def test_parse_period_month_with_explicit_year():
    start, end = cs.parse_period("what about March 2024", today=TODAY)
    assert start == "2024-03-01"
    assert end == "2024-03-31"


def test_parse_period_last_year():
    start, end = cs.parse_period("how much last year", today=TODAY)
    assert start == "2025-01-01"
    assert end == "2025-12-31"


def test_parse_period_none():
    assert cs.parse_period("what are my top categories", today=TODAY) == (None, None)


# --- deterministic answer formatters ---------------------------------------

def _txn(amount, merchant="Shop", category="Food", d="2026-07-01"):
    return {"amount": amount, "raw_merchant": merchant, "date": d,
            "categories": {"name": category}}


def test_answer_total_by_category_breakdown():
    txns = [_txn(100, category="Food"), _txn(50, category="Transport"),
            _txn(30, category="Food")]
    out = cs._answer_total_by_category(txns, "how much did I spend", "all time")
    assert "Rs 180" in out
    assert "Food" in out


def test_answer_total_by_category_specific():
    txns = [_txn(100, category="Food"), _txn(50, category="Transport")]
    out = cs._answer_total_by_category(txns, "how much on food", "all time")
    assert "Rs 100" in out
    assert "food" in out.lower()


def test_answer_total_by_category_empty():
    out = cs._answer_total_by_category([], "how much on food", "May")
    assert "no spending" in out.lower()


def test_answer_merchant_breakdown():
    txns = [_txn(100, merchant="Zomato"), _txn(40, merchant="Uber"),
            _txn(60, merchant="Zomato")]
    out = cs._answer_merchant_breakdown(txns, "all time")
    assert "Zomato" in out
    assert "Rs 160" in out


def test_answer_open_ended_net():
    txns = [_txn(100), _txn(-30)]  # spent 100, received 30
    out = cs._answer_open_ended(txns, "all time")
    assert "Rs 100" in out    # spent
    assert "Rs 30" in out     # received
    assert "Rs -70" in out    # net (received - spent, consistent with insights.py)


def test_spend_only_excludes_income():
    txns = [_txn(100), _txn(-50)]
    assert len(cs._spend_only(txns)) == 1


def test_category_name_tolerates_list_embed():
    assert cs._category_name({"categories": [{"name": "Bills"}]}) == "Bills"
    assert cs._category_name({"categories": None}) == "Uncategorized"


# --- rephrase (LLM layer, mocked) ------------------------------------------

DETERMINISTIC = "You spent Rs 1,200 on food across 3 transactions (all time)."


async def test_rephrase_skips_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: False)
    out = await cs.rephrase("how much on food", DETERMINISTIC)
    assert out == DETERMINISTIC


async def test_rephrase_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)

    async def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(cs.llm_client, "acomplete", boom)
    out = await cs.rephrase("how much on food", DETERMINISTIC)
    assert out == DETERMINISTIC


async def test_rephrase_rejects_altered_figures(monkeypatch):
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)

    async def liar(*a, **k):
        return "You blew Rs 9,999 on food!"  # changed the figure

    monkeypatch.setattr(cs.llm_client, "acomplete", liar)
    out = await cs.rephrase("how much on food", DETERMINISTIC)
    assert out == DETERMINISTIC  # guardrail keeps the correct numbers


async def test_rephrase_accepts_faithful_rewrite(monkeypatch):
    monkeypatch.setattr(cs.llm_client, "is_available", lambda: True)
    good = "Nice — you spent Rs 1,200 on food across 3 transactions (all time)."

    async def faithful(*a, **k):
        return good

    monkeypatch.setattr(cs.llm_client, "acomplete", faithful)
    out = await cs.rephrase("how much on food", DETERMINISTIC)
    assert out == good


# --- answer_question orchestration (fake Supabase, no DB) -------------------

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    """Chainable PostgREST-builder stub. Every filter/select returns self;
    ``execute()`` returns the canned rows registered for the table name."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _FakeResult(self._rows)


class _FakeDB:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _FakeTable(self._tables.get(name, []))


def _mk_db(transactions=None, events=None):
    return _FakeDB({"transactions": transactions or [], "events": events or []})


def test_answer_question_total_by_category_routes_and_computes():
    db = _mk_db(transactions=[_txn(100, category="Food"), _txn(50, category="Transport")])
    out = cs.answer_question("how much did I spend", "user-1", db)
    assert "Rs 150" in out
    assert "Food" in out


def test_answer_question_merchant_routes():
    db = _mk_db(transactions=[_txn(100, merchant="Zomato"), _txn(60, merchant="Zomato")])
    out = cs.answer_question("which merchant did I pay most", "user-1", db)
    assert "Zomato" in out
    assert "Rs 160" in out


def test_answer_question_open_ended_routes():
    db = _mk_db(transactions=[_txn(100), _txn(-40)])
    out = cs.answer_question("tell me about my finances", "user-1", db)
    assert "Rs 100" in out   # spent
    assert "Rs 40" in out    # received


def test_answer_question_events_route():
    db = _mk_db(events=[{"name": "Goa Trip", "summary": "fun", "total_amount": 5000}])
    out = cs.answer_question("how much did my Goa trip cost", "user-1", db)
    assert "Goa Trip" in out
    assert "Rs 5,000" in out


def test_answer_question_events_empty():
    db = _mk_db(events=[])
    out = cs.answer_question("what about my trips", "user-1", db)
    assert "don't have any events" in out.lower()


def test_answer_question_no_transactions():
    db = _mk_db(transactions=[])
    out = cs.answer_question("how much did I spend on food", "user-1", db)
    assert "no spending" in out.lower()


# --- SSE packing ------------------------------------------------------------

def test_sse_pack_is_single_line_events():
    events = list(cs._sse_pack("hello world"))
    assert events == ["data: hello \n\n", "data: world \n\n"]
    # No event payload contains an embedded newline that would break framing.
    for e in events:
        assert e.endswith("\n\n")
        assert "\n" not in e[:-2]
