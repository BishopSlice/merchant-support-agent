"""The agent's data tools: the Merchant API MCP's read tools, scoped to the session's store.

Each tool takes the store from session state (never from the model) and returns the MCP's
response unchanged in shape. `list_products` can be narrowed to one issue code; the filter is
applied to the MCP response here, so the agent can fetch just the affected products.
"""

from google.adk import Context

from merchant_agent.data import MockMerchantMcp

# The data source behind the tools. Tests and evals can swap it (for example to inject failures).
merchant_data = MockMerchantMcp()


def _account(tool_context: Context) -> str:
    return tool_context.state["store_id"]


def list_products(tool_context: Context, issue_code: str = "") -> dict:
    """List this merchant's products with their status and item-level issues.

    Pass an issue code (for example "price_mismatch") to get only the products with that issue.
    Each issue has a code, a severity (DISAPPROVED, DEMOTED or NOT_IMPACTED), the attribute
    involved, a detail and a documentation link.
    """
    result = merchant_data.call("list_products", account=_account(tool_context))
    if issue_code and "products" in result:
        result["products"] = [
            product
            for product in result["products"]
            if any(i["code"] == issue_code for i in product["productStatus"]["itemLevelIssues"])
        ]
    return result


def get_product_by_name(name: str, tool_context: Context) -> dict:
    """Get one product's full status and issues.

    name has the form accounts/{account}/products/en~US~{offerId}, for example
    accounts/sample-store/products/en~US~HG-004.
    """
    if not name.startswith(f"accounts/{_account(tool_context)}/products/"):
        return {"error": "You can only look up products in this merchant's own account."}
    return merchant_data.call("get_product_by_name", name=name)


def list_account_issues(tool_context: Context) -> dict:
    """List account-level issues, such as a suspension, that affect every product."""
    return merchant_data.call("list_account_issues", account=_account(tool_context))


def list_aggregate_product_statuses(tool_context: Context) -> dict:
    """Get counts of active, pending and disapproved products, and each issue's product count."""
    return merchant_data.call("list_aggregate_product_statuses", account=_account(tool_context))


def get_automatic_improvements(tool_context: Context) -> dict:
    """Get whether Merchant Center's automatic improvements are on for this account.

    itemUpdates covers automatic price and availability updates; imageImprovements and
    shippingImprovements cover image fixes and delivery-time estimates.
    """
    return merchant_data.call("get_automatic_improvements", account=_account(tool_context))


DATA_TOOLS = [
    list_products,
    get_product_by_name,
    list_account_issues,
    list_aggregate_product_statuses,
    get_automatic_improvements,
]
