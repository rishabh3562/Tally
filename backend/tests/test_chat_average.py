"""Average monthly spend / run-rate — deterministic keyless answer."""

from app.services import chat_service


def _tx(amount, date, merchant="X"):
    return {"amount": amount, "raw_merchant": merchant, "date": date}


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
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

    def execute(self):
        return _Res(self._rows)


class _DB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _Q(self._rows)


def test_is_average_query():
    assert chat_service._is_average_query("what's my average monthly spend") is True
    assert chat_service._is_average_query("how much do I spend on average") is True
    assert chat_service._is_average_query("what's my run rate") is True
    assert chat_service._is_average_query("how much did I spend on food") is False
    assert chat_service._is_average_query("did I spend more this month than last") is False


def test_answer_average_computes_mean_and_peak():
    rows = [
        _tx(600, "2026-01-10"), _tx(400, "2026-01-20"),   # Jan 1000
        _tx(2000, "2026-02-15"),                          # Feb 2000
        _tx(3000, "2026-03-15"),                          # Mar 3000
    ]
    out = chat_service._answer_average(_DB(rows), "u1")
    assert "Rs 2,000" in out          # (1000+2000+3000)/3
    assert "3 months" in out
    assert "March 2026" in out        # peak month, in words


def test_answer_average_ignores_credits():
    rows = [
        _tx(1000, "2026-01-10"),
        _tx(-5000, "2026-01-11"),     # a credit must not count as spend
        _tx(1000, "2026-02-10"),
    ]
    out = chat_service._answer_average(_DB(rows), "u1")
    assert "Rs 1,000" in out          # 2000 spend / 2 months


def test_answer_average_empty_is_graceful():
    out = chat_service._answer_average(_DB([]), "u1")
    assert "enough spending history" in out.lower()
