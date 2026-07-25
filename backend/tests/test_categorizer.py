"""Deterministic categorization rules (rule_category).

Uses real-world Indian UPI merchant strings (the kind that were landing in
"Other") to lock in the substring + regex behavior.
"""

from app.services.categorizer import rule_category


def test_brand_substring_reclaims_variants():
    # Exact-match used to miss these; substring on a distinctive token catches them.
    assert rule_category("AmazonIndia")[0] == "Shopping"
    assert rule_category("AmazonPay")[0] == "Shopping"
    assert rule_category("HungerBox")[0] == "Food & Dining"
    assert rule_category("BundlTechnologiespvtLtd")[0] == "Food & Dining"  # = Swiggy
    assert rule_category("FLIPKART INTERNET")[0] == "Shopping"


def test_regex_catches_descriptive_names():
    assert rule_category("MAHALAXMITEAANDSNACKCENTER")[0] == "Food & Dining"  # SNACK
    assert rule_category("BOMBAYCHAAPCORNER")[0] == "Food & Dining"          # CHAAP
    assert rule_category("SMARTLIFECHEMIST")[0] == "Healthcare"              # CHEMIST
    assert rule_category("PuneMahanagarParivahanMahamandalLimited")[0] == "Transport"
    assert rule_category("KHELOMORESPORTSPRIVATELIMITED")[0] == "Entertainment"  # SPORT
    assert rule_category("MATCHPOINT")[0] == "Entertainment"


def test_person_to_person_stays_uncategorized():
    # These genuinely need the LLM (or are transfers) — must NOT false-match.
    for name in ("MOHANLALSHARMA", "AYUSHPATEL", "JAHANGIRALI", "OMTRIPATHI",
                 "SANDIPAPPASAHEBUBALE", "VEDANTKOTKAR", "PriyanshuGanatra"):
        assert rule_category(name) is None, f"{name} should stay uncategorized"


def test_empty_and_confidence():
    assert rule_category("") is None
    assert rule_category("AmazonIndia")[1] == 1.0   # brand token = high confidence
    assert rule_category("SMARTLIFECHEMIST")[1] == 0.85  # regex = medium
