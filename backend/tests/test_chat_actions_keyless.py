"""Deterministic chat actions — work with NO LLM configured (user's real state).

The action executors are deterministic; only intent parsing needed the model.
try_action parses the common phrasings and runs the same executors, so
"categorize my amazon as shopping" does the thing instead of returning a summary.
"""

from app.services import chat_service
from tests.test_chat_actions import _FakeDB, _store


def _cat_store():
    return _store(
        categories=[{"id": "cat-shop", "name": "Shopping"}],
        transactions=[{"raw_merchant": "AmazonIndia"}, {"raw_merchant": "AmazonPay"}],
    )


def test_categorize_phrasing_runs_the_action():
    for q in [
        "put my amazon under Shopping",
        "categorize amazon as shopping",
        "move all my amazon to shopping",
        "label amazon as Shopping.",
    ]:
        store = _cat_store()
        store["update_rows"] = [{"id": "t1"}, {"id": "t2"}]
        out = chat_service.try_action(q, "u1", _FakeDB(store))
        assert out is not None, q
        assert "Shopping" in out
        assert any(l["op"] == "update" for l in store["log"]), q


def test_unknown_category_is_not_treated_as_action():
    # "how much did I spend on amazon" must NOT be parsed as a categorize command.
    store = _cat_store()
    out = chat_service.try_action("how much did I spend at amazon", "u1", _FakeDB(store))
    assert out is None
    assert not any(l["op"] == "update" for l in store["log"])


def test_categorize_to_nonexistent_category_defers_to_qa():
    # Category "Groceries" doesn't exist here -> not an action, let Q&A handle it.
    store = _cat_store()
    out = chat_service.try_action("put amazon under Groceries", "u1", _FakeDB(store))
    assert out is None


def test_create_category_phrasing_runs_the_action():
    store = _store(categories=[])
    store["insert_rows"] = [{"id": "c-new", "name": "Rent"}]
    out = chat_service.try_action("create a category called Rent", "u1", _FakeDB(store))
    assert out is not None
    assert "Rent" in out
    assert any(l["op"] == "insert" for l in store["log"])


def test_plain_question_is_not_an_action():
    store = _cat_store()
    assert chat_service.try_action("where did most of my money go", "u1", _FakeDB(store)) is None
    assert chat_service.try_action("how much did I spend last month", "u1", _FakeDB(store)) is None
