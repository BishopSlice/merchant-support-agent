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


def test_title_over_150_characters_is_flagged():
    assert issue_types(clean_product(title="x" * 151)) == [IssueType.TITLE_TOO_LONG]


def test_title_of_exactly_150_characters_is_fine():
    assert issue_types(clean_product(title="x" * 150)) == []


def test_in_stock_in_feed_but_out_of_stock_on_page_is_flagged():
    product = clean_product(availability="in_stock", landing_page_availability="out_of_stock")
    assert issue_types(product) == [IssueType.AVAILABILITY_MISMATCH]


def test_availability_comparison_ignores_case_and_spaces():
    product = clean_product(availability="in stock", landing_page_availability="In_Stock")
    assert issue_types(product) == []


def test_missing_shipping_is_flagged():
    assert issue_types(clean_product(shipping="")) == [IssueType.MISSING_SHIPPING]


def test_cbd_product_is_flagged_as_restricted():
    product = clean_product(title="CBD Infused Lavender Candle")
    assert issue_types(product) == [IssueType.RESTRICTED_PRODUCT]


def test_restricted_term_in_product_type_is_flagged():
    product = clean_product(product_type="Home & Garden > Decor > Candles > CBD Products")
    assert issue_types(product) == [IssueType.RESTRICTED_PRODUCT]


def test_restricted_terms_match_whole_words_only():
    assert issue_types(clean_product(title="ABCD Brand Mug")) == []


SEVERITY_BY_TYPE = {
    IssueType.MISSING_GTIN: "limited",
    IssueType.PRICE_MISMATCH: "disapproved",
    IssueType.INVALID_IMAGE: "disapproved",
    IssueType.TITLE_TOO_LONG: "disapproved",
    IssueType.AVAILABILITY_MISMATCH: "disapproved",
    IssueType.MISSING_SHIPPING: "disapproved",
    IssueType.RESTRICTED_PRODUCT: "disapproved",
}


def test_every_issue_type_has_a_severity():
    assert set(SEVERITY_BY_TYPE) == set(IssueType)


def test_each_rule_sets_the_expected_severity():
    broken = clean_product(
        gtin="",
        price="14.00 USD",
        landing_page_price="18.00 USD",
        image_link="",
        title="CBD " + "x" * 150,
        availability="in_stock",
        landing_page_availability="out_of_stock",
        shipping="",
    )
    found = {issue.issue_type: issue.severity for issue in feed_rules.run_checks(broken)}
    assert found == SEVERITY_BY_TYPE


def test_blank_landing_page_price_is_not_a_mismatch():
    assert issue_types(clean_product(landing_page_price="")) == []


def test_price_without_a_currency_is_skipped_rather_than_crashing():
    assert issue_types(clean_product(price="14.00", landing_page_price="18.00 USD")) == []


def test_unreadable_price_amount_is_skipped():
    assert issue_types(clean_product(price="about 14 USD", landing_page_price="18.00 USD")) == []


def test_image_link_must_start_with_a_full_scheme():
    product = clean_product(image_link="httpcdn.shop.example/mug.jpg")
    assert issue_types(product) == [IssueType.INVALID_IMAGE]


def test_blank_landing_page_availability_is_not_a_mismatch():
    assert issue_types(clean_product(landing_page_availability="")) == []


def test_whitespace_shipping_counts_as_missing():
    assert issue_types(clean_product(shipping="   ")) == [IssueType.MISSING_SHIPPING]
