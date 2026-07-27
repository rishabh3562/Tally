"""Questions the chat used to answer wrongly. Found by running a 30-question
battery against the LIVE data, not by imagining what a user might type.

Each test names the real failure it locks down.
"""

from datetime import date

from app.services import chat_service as cs


def _tx(amount, d, merchant="Shop", category="Food"):
    return {"amount": amount, "raw_merchant": merchant, "date": d,
            "categories": {"name": category} if category else None}


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    """Honours the date filters, so a period question really scopes the rows."""

    def __init__(self, rows):
        self._rows, self._start, self._end = rows, None, None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, _c, v):
        self._start = v
        return self

    def lte(self, _c, v):
        self._end = v
        return self

    def execute(self):
        rows = self._rows
        if self._start:
            rows = [r for r in rows if r["date"] >= self._start]
        if self._end:
            rows = [r for r in rows if r["date"] <= self._end]
        return _Res(rows)


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _n):
        return _Q(self._rows)


TODAY = date(2026, 7, 15)  # a Wednesday


# --- "last week" silently answered ALL TIME ---------------------------------

def test_last_week_is_the_previous_monday_to_sunday():
    assert cs.parse_period("what did I spend last week", today=TODAY) == (
        "2026-07-06", "2026-07-12",
    )


def test_this_week_runs_from_monday_to_today():
    assert cs.parse_period("spending this week", today=TODAY) == (
        "2026-07-13", "2026-07-15",
    )


def test_yesterday_and_today():
    assert cs.parse_period("what did I spend yesterday", today=TODAY) == (
        "2026-07-14", "2026-07-14",
    )
    assert cs.parse_period("anything today", today=TODAY) == (
        "2026-07-15", "2026-07-15",
    )


def test_last_n_weeks_and_months():
    assert cs.parse_period("the last 2 weeks", today=TODAY)[0] == "2026-07-01"
    assert cs.parse_period("past 3 months", today=TODAY)[0] == "2026-04-16"


def test_a_week_question_no_longer_falls_through_to_all_time():
    """The actual bug: an unparsed period meant the answer covered everything."""
    rows = [_tx(500, "2026-01-05"), _tx(100, "2026-07-08")]
    out = cs.answer_question("how much did I spend last week", "u1", _DB(rows))
    # Only the July row is in the previous week; the January one must not be counted.
    assert "Rs 500" not in out and "Rs 600" not in out


# --- "top categories" answered with an unrelated net summary ----------------

def test_category_questions_are_classified_by_the_word_category():
    assert cs.classify_intent("what are my top 3 categories") == cs.IntentType.TOTAL_BY_CATEGORY
    assert cs.classify_intent("show spending by category") == cs.IntentType.TOTAL_BY_CATEGORY


def test_top_categories_returns_a_breakdown():
    rows = [_tx(300, "2026-05-01", category="Shopping"),
            _tx(100, "2026-05-02", category="Food")]
    out = cs.answer_question("what are my top 3 categories", "u1", _DB(rows))
    assert "• Shopping — Rs 300" in out


# --- "average per day" answered with a monthly figure ----------------------

def test_daily_average_is_recognized_separately():
    assert cs._is_daily_average_query("how much do I spend on average per day") is True
    assert cs._is_daily_average_query("what's my average monthly spend") is False


def test_daily_average_answer():
    rows = [_tx(100, "2026-05-01"), _tx(300, "2026-05-05")]  # 400 over 5 days
    out = cs.answer_question("how much do I spend per day", "u1", _DB(rows))
    assert "Rs 80 a day" in out
    assert "5 days" in out


def test_monthly_average_still_works():
    rows = [_tx(1000, "2026-04-10"), _tx(3000, "2026-05-10")]
    out = cs.answer_question("what's my average monthly spend", "u1", _DB(rows))
    assert "Rs 2,000" in out


# --- a percentage question got an absolute amount --------------------------

def test_percentage_question_gets_a_share():
    rows = [_tx(250, "2026-05-01", category="Food"),
            _tx(750, "2026-05-02", category="Shopping")]
    out = cs.answer_question("what percentage of my money goes to food", "u1", _DB(rows))
    assert "Rs 250" in out
    assert "25%" in out


def test_plain_amount_question_gets_no_share():
    rows = [_tx(250, "2026-05-01", category="Food"),
            _tx(750, "2026-05-02", category="Shopping")]
    out = cs.answer_question("how much did I spend on food", "u1", _DB(rows))
    assert "%" not in out


# --- "help" / "what can you do" got a wall of numbers ---------------------

def test_help_lists_capabilities():
    out = cs.answer_question("help", "u1", _DB([]))
    assert "Try:" in out
    assert "biggest expense" in out
    assert "Rs" not in out.replace("Rs 1,200", "")  # no invented figures


def test_capability_query_variants():
    for q in ["help", "what can you do", "what can I ask?", "who are you"]:
        assert cs._is_capability_query(q) is True, q
    assert cs._is_capability_query("how much did I spend") is False


# --- "how many transactions do I have" got a spend summary ---------------

def test_coverage_question_reports_the_data_not_the_spend():
    rows = [_tx(100, "2025-12-07"), _tx(200, "2026-05-31")]
    out = cs.answer_question("how many transactions do I have", "u1", _DB(rows))
    assert "2 transactions" in out
    assert "7 Dec 2025" in out and "31 May 2026" in out


def test_when_did_i_start_uses_the_same_answer():
    rows = [_tx(100, "2025-12-07")]
    out = cs.answer_question("when did I start", "u1", _DB(rows))
    assert "7 Dec 2025" in out


# --- "more on food than shopping" answered only about food ---------------

def test_extract_categories_finds_both_in_order():
    assert cs.extract_categories("more on food than shopping") == ["food", "shopping"]
    # "grocery"/"groceries" are the same spend area, not two categories.
    assert cs.extract_categories("groceries this month") == ["groceries"]


def test_two_categories_are_compared():
    rows = [_tx(400, "2026-05-01", category="Food & Dining"),
            _tx(900, "2026-05-02", category="Shopping")]
    out = cs.answer_question("am I spending more on food than shopping", "u1", _DB(rows))
    assert "Rs 400" in out and "Rs 900" in out
    assert "shopping is higher, by Rs 500" in out


def test_one_category_is_not_treated_as_a_comparison():
    rows = [_tx(400, "2026-05-01", category="Food & Dining")]
    out = cs.answer_question("did I spend more on food than usual", "u1", _DB(rows))
    assert "vs" not in out


# --- the net figure read as a puzzle -------------------------------------

def test_net_is_stated_in_words():
    rows = [_tx(1000, "2026-05-01"), _tx(-200, "2026-05-02")]
    out = cs.answer_question("give me a summary", "u1", _DB(rows))
    assert "down Rs 800" in out
    assert "Rs -" not in out
