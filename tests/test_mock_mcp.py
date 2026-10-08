"""The mock Merchant API MCP: documented shapes, parity with the v1 checker, and a read-only allowlist."""

import pytest

from merchant_agent.data import (
    ALLOWED_TOOLS,
    BLOCKED_TOOLS,
    MockMerchantMcp,
    ToolNotAllowedError,
)
from merchant_agent.merchant_api import (
    AccountIssue,
    AggregateProductStatus,
    AutomaticImprovements,
    Product,
    product_name,
)
from merchant_agent.stores import load_feed
from merchant_agent.tools.feed_rules import run_checks

MCP = MockMerchantMcp()


def products(store: str = "sample-store") -> dict[str, dict]:
    return {p["offerId"]: p for p in MCP.call("list_products", account=store)["products"]}


def test_list_products_returns_every_product_in_the_documented_shape():
    listed = products()
    assert len(listed) == 30
    for offer_id, product in listed.items():
        Product.model_validate(product)
        assert product["name"] == product_name("sample-store", offer_id)


def test_item_issues_match_the_v1_checker_exactly():
    listed = products()
    for product in load_feed("sample-store"):
        expected = sorted(issue.issue_type.value for issue in run_checks(product))
        issues = listed[product.id]["productStatus"]["itemLevelIssues"]
        assert sorted(issue["code"] for issue in issues) == expected, product.id


def test_issue_severity_attribute_and_documentation_are_mapped():
    by_code = {i["code"]: i for i in products()["HG-019"]["productStatus"]["itemLevelIssues"]}
    gtin, shipping = by_code["missing_gtin"], by_code["missing_shipping"]
    assert gtin["severity"] == "DEMOTED" and gtin["attribute"] == "gtins"
    assert shipping["severity"] == "DISAPPROVED" and shipping["attribute"] == "shipping"
    assert gtin["documentation"] == "https://support.google.com/merchants/answer/6324461"
    assert gtin["applicableCountries"] == ["US"]


def test_destination_status_reflects_disapprovals_only():
    listed = products()

    def destination(offer_id):
        return listed[offer_id]["productStatus"]["destinationStatuses"][0]

    assert destination("HG-004")["disapprovedCountries"] == ["US"]  # price mismatch
    assert destination("HG-002")["approvedCountries"] == ["US"]  # missing GTIN: demoted only
    assert destination("HG-001")["approvedCountries"] == ["US"]  # clean


def test_product_attributes_use_documented_names_and_types():
    attributes = products()["HG-004"]["productAttributes"]
    assert attributes["price"] == {"amountMicros": "32000000", "currencyCode": "USD"}
    assert attributes["availability"] == "IN_STOCK"
    assert attributes["gtins"] == ["0850012345043"]
    assert products()["HG-002"]["productAttributes"]["gtins"] == []


def test_get_product_by_name_returns_one_product():
    name = product_name("sample-store", "HG-023")
    product = MCP.call("get_product_by_name", name=name)
    assert product["offerId"] == "HG-023"
    assert [i["code"] for i in product["productStatus"]["itemLevelIssues"]] == [
        "restricted_product"
    ]


@pytest.mark.parametrize(
    "name",
    [
        "accounts/sample-store/products/en~US~NOPE",
        "not-a-product-name",
        "accounts/nowhere/products/en~US~HG-001",
    ],
)
def test_get_product_by_name_reports_unknown_products_as_errors(name):
    assert "error" in MCP.call("get_product_by_name", name=name)


def test_aggregate_statuses_count_products_and_issues():
    [status] = MCP.call("list_aggregate_product_statuses", account="sample-store")[
        "aggregateProductStatuses"
    ]
    AggregateProductStatus.model_validate(status)
    assert status["stats"] == {
        "activeCount": "17",
        "pendingCount": "0",
        "disapprovedCount": "13",
        "expiringCount": "0",
    }
    counts = {i["code"]: i["productCount"] for i in status["itemLevelIssues"]}
    assert counts["missing_gtin"] == "6" and counts["price_mismatch"] == "3"


def test_account_issues_come_from_the_account_status():
    assert MCP.call("list_account_issues", account="sample-store")["accountIssues"] == []
    [issue] = MCP.call("list_account_issues", account="suspended-store")["accountIssues"]
    AccountIssue.model_validate(issue)
    assert issue["severity"] == "CRITICAL"
    assert "returns policy" in issue["detail"]
    assert issue["documentationUri"] == "https://support.google.com/merchants/answer/6150127"


def test_automatic_improvements_reflect_the_store_settings():
    result = MCP.call("get_automatic_improvements", account="sample-store")
    AutomaticImprovements.model_validate(result)
    assert result["itemUpdates"]["effectiveAllowPriceUpdates"] is False
    assert result["itemUpdates"]["effectiveAllowAvailabilityUpdates"] is False
    assert result["imageImprovements"]["effectiveAllowAutomaticImageImprovements"] is False


def test_unknown_accounts_are_reported_as_errors():
    assert "error" in MCP.call("list_products", account="no-such-store")


# --- Read-only allowlist: a hard gate ---


def test_the_allowlist_is_exactly_the_five_read_tools():
    assert ALLOWED_TOOLS == {
        "list_products",
        "get_product_by_name",
        "list_account_issues",
        "list_aggregate_product_statuses",
        "get_automatic_improvements",
    }


def test_write_and_unneeded_mcp_tools_are_blocked():
    assert BLOCKED_TOOLS == {
        "create_data_source",
        "fetch_data_source",
        "get_file_upload",
        "get_data_source",
        "list_data_sources",
        "report_search",
        "list_accounts",
        "list_programs",
    }
    assert not ALLOWED_TOOLS & BLOCKED_TOOLS


@pytest.mark.parametrize("tool", sorted(BLOCKED_TOOLS) + ["delete_everything"])
def test_calling_a_tool_outside_the_allowlist_raises(tool):
    with pytest.raises(ToolNotAllowedError):
        MCP.call(tool, account="sample-store")


def test_a_disapproved_product_is_not_also_listed_as_approved():
    status = products()["HG-004"]["productStatus"]["destinationStatuses"][0]
    assert status["approvedCountries"] == []
