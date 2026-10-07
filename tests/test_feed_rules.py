from merchant_agent.models import IssueType, Product
from merchant_agent.tools import feed_rules


def clean_product(**overrides) -> Product:
    """A product with no problems, with any field overridden for a test."""
    fields = {
        "id": "SKU-1",
        "title": "Stoneware Mug",
        "link": "https://shop.example/mug",
        "image_link": "https://cdn.shop.example/mug.jpg",
        "price": "14.00 USD",
        "availability": "in_stock",
        "brand": "Acme",
        "gtin": "0850012345012",
        "product_type": "Home & Garden > Kitchen & Dining > Mugs",
        "shipping": "US:::5.95 USD",
        "landing_page_price": "14.00 USD",
        "landing_page_availability": "in_stock",
    }
    return Product(**(fields | overrides))


def issue_types(product: Product) -> list[IssueType]:
    return [issue.issue_type for issue in feed_rules.run_checks(product)]


def test_clean_product_has_no_issues():
    assert issue_types(clean_product()) == []


def test_missing_gtin_is_flagged():
    assert issue_types(clean_product(gtin="")) == [IssueType.MISSING_GTIN]


def test_whitespace_gtin_counts_as_missing():
    assert issue_types(clean_product(gtin="  ")) == [IssueType.MISSING_GTIN]


def test_feed_price_lower_than_landing_page_is_flagged():
    product = clean_product(price="14.00 USD", landing_page_price="18.00 USD")
    assert issue_types(product) == [IssueType.PRICE_MISMATCH]


def test_same_price_written_differently_is_not_a_mismatch():
    product = clean_product(price="14 USD", landing_page_price="14.00 USD")
    assert issue_types(product) == []


def test_price_mismatch_detail_shows_both_prices():
    product = clean_product(price="14.00 USD", landing_page_price="18.00 USD")
    detail = feed_rules.check_price_mismatch(product)[0].detail
    assert "14.00 USD" in detail and "18.00 USD" in detail


def test_missing_image_link_is_flagged():
    assert issue_types(clean_product(image_link="")) == [IssueType.INVALID_IMAGE]


def test_placeholder_image_is_flagged():
    product = clean_product(image_link="https://cdn.shop.example/img/placeholder.png")
    assert issue_types(product) == [IssueType.INVALID_IMAGE]


def test_image_link_must_be_a_web_address():
    assert issue_types(clean_product(image_link="mug.jpg")) == [IssueType.INVALID_IMAGE]
