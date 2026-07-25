"""Deterministic brand canonicalization — collapse merchant-string variants."""

from app.services.merchant import canonical_merchant as cm


def test_amazon_variants_collapse():
    for raw in ["AmazonIndia", "AmazonPay", "AmazonPayGroceries", "AmazonPayonDelivery"]:
        assert cm(raw) == "Amazon"


def test_swiggy_variants_collapse():
    for raw in ["Swiggy", "SWIGGY", "SwiggyLimited", "SWIGGYINSTAMART",
                "BundlTechnologiespvtLtd", "SWIGGYINSTAMARTPRIVATELIMITED"]:
        assert cm(raw) == "Swiggy"


def test_known_brands():
    assert cm("AVENUESUPERMARTSLTD") == "DMart"
    assert cm("KHELOMORESPORTSPRIVATELIMITED") == "KheloMore"
    assert cm("HungerBox") == "HungerBox"


def test_people_and_unknowns_pass_through():
    for raw in ["PriyaPandey", "MOHANLALSHARMA", "JAIHIND", "SATHISHREDDYVADICHERLA"]:
        assert cm(raw) == raw


def test_empty_is_safe():
    assert cm("") == ""


def test_dmart_alias():
    assert cm("AVENUESUPERMARTSLTD") == "DMart"
    assert cm("DMart") == "DMart"


def test_brand_names_exposed():
    from app.services.merchant import BRAND_NAMES
    assert {"Swiggy", "Amazon", "DMart"} <= BRAND_NAMES
