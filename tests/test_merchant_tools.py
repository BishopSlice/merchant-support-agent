"""The agent's MCP-shaped data tools: scoped to the session's store, read-only, filterable."""

from types import SimpleNamespace

import pytest

from merchant_agent.data import ALLOWED_TOOLS, BLOCKED_TOOLS
from merchant_agent.merchant_api import product_name
from merchant_agent.tools import merchant_tools


def session(store: str = "sample-store") -> SimpleNamespace:
    return SimpleNamespace(state={"store_id": store})


def test_list_products_reads_the_session_store():
    assert len(merchant_tools.list_products(tool_context=session())["products"]) == 30


def test_list_products_can_filter_to_one_issue_code():
    products = merchant_tools.list_products(issue_code="price_mismatch", tool_context=session())
    assert sorted(p["offerId"] for p in products["products"]) == ["HG-004", "HG-015", "HG-021"]


def test_get_product_by_name_returns_the_product():
    name = product_name("sample-store", "HG-004")
    assert merchant_tools.get_product_by_name(name=name, tool_context=session())["offerId"] == "HG-004"


def test_get_product_by_name_refuses_other_accounts():
    name = product_name("suspended-store", "PP-001")
    result = merchant_tools.get_product_by_name(name=name, tool_context=session("sample-store"))
    assert "error" in result


def test_account_level_tools_read_the_session_store():
    assert merchant_tools.list_account_issues(tool_context=session("suspended-store"))[
        "accountIssues"
    ][0]["severity"] == "CRITICAL"
    [status] = merchant_tools.list_aggregate_product_statuses(tool_context=session())[
        "aggregateProductStatuses"
    ]
    assert status["stats"]["disapprovedCount"] == "13"
    improvements = merchant_tools.get_automatic_improvements(tool_context=session())
    assert improvements["itemUpdates"]["effectiveAllowPriceUpdates"] is False


def test_the_data_tools_are_exactly_the_allowlist():
    names = {tool.__name__ for tool in merchant_tools.DATA_TOOLS}
    assert names == ALLOWED_TOOLS
    assert not names & BLOCKED_TOOLS


@pytest.mark.parametrize("tool", sorted(BLOCKED_TOOLS))
def test_no_wrapper_exists_for_blocked_tools(tool):
    assert not hasattr(merchant_tools, tool)
