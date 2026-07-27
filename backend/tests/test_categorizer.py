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


# --- brand map (reuses merchant.canonical_merchant) -------------------------
# Added after measuring the REAL uncategorised pile: DMart was Rs 3,138 of
# "Other" purely because no token matched "AVENUESUPERMARTSLTD".

def test_every_canonical_brand_has_a_category():
    """merchant.py and categorizer.py must not drift: a brand added to the
    canonicalizer without a category here would silently stay uncategorised."""
    from app.services.categorizer import BRAND_CATEGORY
    from app.services.merchant import BRAND_NAMES

    assert set(BRAND_CATEGORY) == set(BRAND_NAMES)


def test_brand_variants_categorize_without_their_own_token():
    from app.services.categorizer import rule_category

    for raw, expected in [
        ("AVENUESUPERMARTSLTD", "Groceries"),      # DMart
        ("DMART BHOPAL", "Groceries"),
        ("BundlTechnologiespvtLtd", "Food & Dining"),   # Swiggy
        ("KHELOMORE", "Entertainment"),
        ("AmazonPayonDelivery", "Shopping"),
    ]:
        got = rule_category(raw)
        assert got is not None, raw
        assert got[0] == expected, (raw, got)


def test_a_sub_brand_beats_its_parent_brand():
    """Swiggy Instamart is a grocery run, not a restaurant meal."""
    from app.services.categorizer import rule_category

    assert rule_category("SWIGGYINSTAMARTPRIVATELIMITED")[0] == "Groceries"
    assert rule_category("Swiggy")[0] == "Food & Dining"


def test_regex_gaps_found_in_real_statements():
    from app.services.categorizer import rule_category

    assert rule_category("INDIANOILCORPORATIONLTDLPGCRMDEBITCARD")[0] == "Transport"
    assert rule_category("EKART")[0] == "Shopping"


def test_people_still_do_not_match_any_rule():
    """P2P UPI payments must stay unmatched — that's what triage is for; a false
    rule match would mislabel money and get remembered."""
    from app.services.categorizer import rule_category

    for name in ["MOHANLALSHARMA", "AYUSHPATEL", "PriyaPandey", "VEDANTKOTKAR"]:
        assert rule_category(name) is None, name
