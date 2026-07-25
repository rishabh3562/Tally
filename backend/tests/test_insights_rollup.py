"""Sub-category spend rolls up to the top-level parent in insights (#4 completion)."""

from app.api.insights import _compute_summary, _root_name_map


def _txn(amount, category, d="2026-07-01"):
    return {"amount": amount, "date": d, "raw_merchant": "M",
            "categories": {"name": category}}


def test_root_name_map_resolves_multi_level():
    cats = [
        {"id": "food", "name": "Food", "parent_id": None},
        {"id": "swiggy", "name": "Swiggy", "parent_id": "food"},
        {"id": "pizza", "name": "Pizza", "parent_id": "swiggy"},
    ]
    m = _root_name_map(cats)
    assert m["Pizza"] == "Food"        # Food › Swiggy › Pizza -> Food
    assert m["Swiggy"] == "Food"
    assert m["Food"] == "Food"


def test_root_name_map_is_cycle_safe():
    cats = [
        {"id": "a", "name": "A", "parent_id": "b"},
        {"id": "b", "name": "B", "parent_id": "a"},   # cycle
    ]
    m = _root_name_map(cats)              # must terminate
    assert set(m.keys()) == {"A", "B"}


def test_summary_rolls_subcategory_into_parent():
    root_of = {"Pizza": "Food", "Food": "Food", "Transport": "Transport"}
    txns = [_txn(100, "Pizza"), _txn(50, "Food"), _txn(40, "Transport")]
    out = _compute_summary(txns, root_of)
    cats = {c["name"]: c["total"] for c in out["top_categories"]}
    assert cats["Food"] == 150           # Pizza (100) rolled into Food (50)
    assert cats["Transport"] == 40
    assert "Pizza" not in cats           # no fragmented child slice


def test_summary_without_map_is_unchanged():
    txns = [_txn(100, "Pizza"), _txn(50, "Food")]
    out = _compute_summary(txns)          # no root map -> child stays its own slice
    cats = {c["name"]: c["total"] for c in out["top_categories"]}
    assert cats["Pizza"] == 100
    assert cats["Food"] == 50
