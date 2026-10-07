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
