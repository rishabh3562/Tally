"""Tests for 'contri' / settle-up detection (user point #8)."""

from app.services.contributions import detect_contributions


def _t(amount, d="2026-07-01", id="x", merchant="M"):
    return {"amount": amount, "date": d, "id": id, "raw_merchant": merchant}


def test_detects_similar_credit_cluster():
    txns = [_t(-62, "2026-07-01", f"c{i}") for i in range(4)]
    out = detect_contributions(txns)
    assert len(out) == 1
    assert out[0]["count"] == 4
    assert out[0]["total_received"] == 248
    assert out[0]["source_debit"] is None
    assert out[0]["net_cost"] is None


def test_ignores_clusters_below_minimum():
    txns = [_t(-62, "2026-07-01", "c1"), _t(-62, "2026-07-01", "c2")]
    assert detect_contributions(txns) == []


def test_links_source_spend_and_reports_net_cost():
    # 3 people repay Rs 250 each (=750) for a Rs 800 booking -> net Rs 50.
    txns = [_t(-250, "2026-07-01", f"c{i}") for i in range(3)]
    txns.append(_t(800, "2026-07-01", "d1", "KheloMore"))
    out = detect_contributions(txns)
    assert len(out) == 1
    c = out[0]
    assert c["total_received"] == 750
    assert c["source_debit"]["amount"] == 800
    assert c["source_debit"]["merchant"] == "KheloMore"
    assert c["net_cost"] == 50


def test_dissimilar_amounts_are_not_a_cluster():
    txns = [
        _t(-10, "2026-07-01", "c1"),
        _t(-500, "2026-07-01", "c2"),
        _t(-3000, "2026-07-01", "c3"),
    ]
    assert detect_contributions(txns) == []


def test_no_source_link_when_no_plausible_debit():
    txns = [_t(-250, "2026-07-01", f"c{i}") for i in range(3)]
    txns.append(_t(100, "2026-07-01", "d1"))  # too small to be the source
    out = detect_contributions(txns)
    assert len(out) == 1
    assert out[0]["source_debit"] is None
    assert out[0]["net_cost"] is None


def test_links_source_within_day_window():
    # Booking on the 1st, repayments trickle in on the 2nd.
    txns = [_t(-250, "2026-07-02", f"c{i}") for i in range(3)]
    txns.append(_t(800, "2026-07-01", "d1", "KheloMore"))
    out = detect_contributions(txns)
    assert out[0]["net_cost"] == 50
