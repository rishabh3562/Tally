"""A user's correction outranks the rules — and a machine's guess does not.

Real failures this locks down. The user had corrected, by hand:
    SWIGGYINSTAMART              -> Food & Dining   (rules say Groceries)
    KHELOMORESPORTSPRIVATELIMITED-> Health          (rules say Entertainment)
    REDBUS                       -> Transport       (rules say Travel)
`categorize_transaction` consulted `learning_records` only AFTER `rule_category`
missed, so every one of those was silently contradicted on the next import. The
same read had no user filter at all, so with two users one person's private
correction drove the other's ingestion.
"""

import asyncio

import pytest

from app.services import categorizer
from app.services.categorizer import (
    load_user_overrides,
    match_override,
    resolve_category,
    rule_category,
)


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows, log):
        self._rows, self._log = rows, log
        self._eq = {}

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        self._log.append(dict(self._eq))
        rows = [r for r in self._rows if all(r.get(k) == v for k, v in self._eq.items())]
        return _Res(rows)


class _DB:
    def __init__(self, learning=(), categories=()):
        self._learning, self._categories = list(learning), list(categories)
        self.log: list[dict] = []

    def table(self, name):
        rows = self._learning if name == "learning_records" else self._categories
        return _Q(rows, self.log)


# The user's real corrections, with the source column migration 006 added.
LEARNING = [
    {"user_id": "A", "raw_merchant": "SWIGGYINSTAMART", "category_id": "food",
     "source": "user"},
    {"user_id": "A", "raw_merchant": "KHELOMORESPORTSPRIVATELIMITED",
     "category_id": "health", "source": "user"},
    {"user_id": "A", "raw_merchant": "REDBUS", "category_id": "transport",
     "source": "user"},
    {"user_id": "A", "raw_merchant": "AmazonPay", "category_id": "shopping",
     "source": "user"},
    # A machine guess must NOT behave like a decision.
    {"user_id": "A", "raw_merchant": "DMART", "category_id": "wrong",
     "source": "rule"},
    # Another user's correction must never be visible.
    {"user_id": "B", "raw_merchant": "SWIGGYINSTAMART", "category_id": "b-secret",
     "source": "user"},
]

CATEGORIES = [
    {"id": "food", "name": "Food & Dining"},
    {"id": "health", "name": "Health"},
    {"id": "transport", "name": "Transport"},
    {"id": "shopping", "name": "Shopping"},
]


# --- loading ----------------------------------------------------------------

def test_only_this_users_hand_made_records_load():
    db = _DB(learning=LEARNING)
    overrides = load_user_overrides(db, "A")
    assert "b-secret" not in overrides.values()      # other user's row
    assert "wrong" not in overrides.values()         # source='rule' is not a decision
    assert overrides["SWIGGYINSTAMART"] == "food"


def test_the_query_is_scoped_to_user_and_source():
    db = _DB(learning=LEARNING)
    load_user_overrides(db, "A")
    assert db.log[0] == {"user_id": "A", "source": "user"}


def test_no_user_id_means_no_overrides_at_all():
    """Fail closed. The old code had no user filter, so an unscoped read applied
    one user's corrections to another's transactions."""
    db = _DB(learning=LEARNING)
    assert load_user_overrides(db, None) == {}
    assert db.log == []          # it didn't even ask


# --- matching ---------------------------------------------------------------

def test_exact_match():
    assert match_override("REDBUS", {"REDBUS": "transport"}) == "transport"


def test_punctuation_and_case_are_ignored():
    assert match_override("Amazon Pay", {"AMAZONPAY": "shopping"}) == "shopping"


def test_a_correction_covers_the_longer_variant_of_the_same_merchant():
    """Verified against the real data: the correction was saved as
    SWIGGYINSTAMART but the statement also carries the …PRIVATELIMITED form."""
    overrides = {"SWIGGYINSTAMART": "food"}
    assert match_override("SWIGGYINSTAMARTPRIVATELIMITED", overrides) == "food"


def test_the_most_specific_correction_wins():
    """AmazonPay is a prefix of AmazonPayGroceries, and both are corrected —
    longest key first, or the general one would swallow the specific one."""
    overrides = {"AMAZONPAY": "shopping", "AMAZONPAYGROCERIES": "groceries"}
    assert match_override("AmazonPayGroceries", overrides) == "groceries"
    assert match_override("AmazonPayonDelivery", overrides) == "shopping"


def test_a_short_key_never_acts_as_a_wildcard():
    """A 3-letter correction must not claim every merchant containing it."""
    assert match_override("BIGBAZAAR", {"BAZ": "x"}) is None


def test_no_match_returns_none():
    assert match_override("SOMEONEELSE", {"REDBUS": "transport"}) is None


# --- precedence -------------------------------------------------------------

@pytest.mark.parametrize("merchant,expected_id,rule_says", [
    ("SWIGGYINSTAMART", "food", "Groceries"),
    ("KHELOMORESPORTSPRIVATELIMITED", "health", "Entertainment"),
    ("REDBUS", "transport", "Travel"),
])
def test_the_users_decision_beats_a_contradicting_rule(merchant, expected_id, rule_says):
    overrides = {k: v for k, v in {
        "SWIGGYINSTAMART": "food",
        "KHELOMORESPORTSPRIVATELIMITED": "health",
        "REDBUS": "transport",
    }.items()}
    # The rule really does disagree — otherwise this test proves nothing.
    assert rule_category(merchant)[0] == rule_says
    cat_id, cat_name, conf = resolve_category(merchant, None, overrides)
    assert cat_id == expected_id
    assert cat_name is None      # an id, because user categories aren't in name maps
    assert conf == 1.0


def test_rules_still_apply_where_the_user_has_not_decided():
    cat_id, cat_name, conf = resolve_category("AmazonIndia", None, {})
    assert cat_id is None
    assert cat_name == "Shopping"
    assert conf == 1.0


def test_nothing_matches_at_all():
    assert resolve_category("MOHANLALSHARMA", None, {}) == (None, None, 0.0)


# --- the async wrapper ------------------------------------------------------

def test_categorize_transaction_applies_the_override_by_name():
    db = _DB(learning=LEARNING, categories=CATEGORIES)
    name, conf = asyncio.run(categorizer.categorize_transaction(
        "SWIGGYINSTAMARTPRIVATELIMITED", 100.0, None, db, "A",
    ))
    assert name == "Food & Dining"
    assert conf == 1.0


def test_categorize_transaction_without_user_id_never_reads_learning_records():
    db = _DB(learning=LEARNING, categories=CATEGORIES)
    name, _ = asyncio.run(categorizer.categorize_transaction(
        "SWIGGYINSTAMART", 100.0, None, db,          # no user_id
    ))
    assert name == "Groceries"                       # fell through to the rules
    assert db.log == []                              # and asked the DB nothing


def test_categorize_transaction_falls_back_to_other():
    db = _DB(learning=[], categories=CATEGORIES)
    name, conf = asyncio.run(categorizer.categorize_transaction(
        "MOHANLALSHARMA", 100.0, None, db, "A",
    ))
    assert (name, conf) == ("Other", 0.5)


# --- /api/learning/reapply --------------------------------------------------

class _ReapplyQ:
    def __init__(self, store, table):
        self._store, self._table = store, table
        self._eq, self._in, self._payload = {}, None, None
        self._op = "select"

    def select(self, *a, **k):
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def in_(self, col, vals):
        self._in = (col, list(vals))
        return self

    def execute(self):
        if self._op == "update":
            ids = self._in[1] if self._in else []
            touched = [r for r in self._store["transactions"]
                       if r["id"] in ids and r["user_id"] == self._eq.get("user_id")]
            for r in touched:
                r.update(self._payload)
            self._store["updates"].append({"payload": self._payload, "ids": ids})
            return _Res(touched)
        rows = [r for r in self._store[self._table]
                if all(r.get(k) == v for k, v in self._eq.items())]
        return _Res(rows)


class _ReapplyDB:
    def __init__(self, store):
        self._store = store

    def table(self, name):
        return _ReapplyQ(self._store, name)


def _store():
    return {
        "learning_records": [
            {"user_id": "A", "raw_merchant": "SWIGGYINSTAMART",
             "category_id": "food", "source": "user"},
            {"user_id": "A", "raw_merchant": "DMART", "category_id": "guess",
             "source": "rule"},
        ],
        "transactions": [
            # Drifted: a rule labelled it Groceries after the user chose Food.
            {"id": "t1", "user_id": "A", "raw_merchant": "SWIGGYINSTAMART",
             "category_id": "groceries"},
            # The longer variant of the same merchant, also drifted.
            {"id": "t2", "user_id": "A", "raw_merchant": "SWIGGYINSTAMARTPRIVATELIMITED",
             "category_id": "groceries"},
            # Already correct — must not be rewritten.
            {"id": "t3", "user_id": "A", "raw_merchant": "SWIGGYINSTAMART",
             "category_id": "food"},
            # Not corrected by the user at all — left alone.
            {"id": "t4", "user_id": "A", "raw_merchant": "MOHANLALSHARMA",
             "category_id": None},
        ],
        "updates": [],
    }


def test_reapply_puts_drifted_rows_back():
    from app.api.categorization import reapply_user_corrections

    store = _store()
    out = asyncio.run(reapply_user_corrections(user_id="A", db=_ReapplyDB(store)))
    assert out["updated_transactions"] == 2
    by_id = {r["id"]: r["category_id"] for r in store["transactions"]}
    assert by_id["t1"] == "food" and by_id["t2"] == "food"
    assert by_id["t3"] == "food"          # untouched, already right
    assert by_id["t4"] is None            # never corrected -> not our business


def test_reapply_is_idempotent():
    from app.api.categorization import reapply_user_corrections

    store = _store()
    asyncio.run(reapply_user_corrections(user_id="A", db=_ReapplyDB(store)))
    store["updates"].clear()
    out = asyncio.run(reapply_user_corrections(user_id="A", db=_ReapplyDB(store)))
    assert out["updated_transactions"] == 0
    assert store["updates"] == []


def test_reapply_only_uses_user_sourced_records():
    """A 'rule' record is a cache, not a decision — reapply must ignore it."""
    from app.api.categorization import reapply_user_corrections

    store = _store()
    store["transactions"].append(
        {"id": "t5", "user_id": "A", "raw_merchant": "DMART", "category_id": "groceries"}
    )
    asyncio.run(reapply_user_corrections(user_id="A", db=_ReapplyDB(store)))
    by_id = {r["id"]: r["category_id"] for r in store["transactions"]}
    assert by_id["t5"] == "groceries"     # NOT forced to the cached 'guess'
