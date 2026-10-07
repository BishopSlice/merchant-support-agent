"""The check_feed tool: run every rule over a store's feed and group the results."""

from collections import defaultdict

from merchant_agent.models import Issue, Product
from merchant_agent.stores import StoreNotFoundError, load_feed, load_store
from merchant_agent.tools.feed_rules import run_checks


def check_feed(store_id: str) -> dict:
    """Check a store's product feed and return disapproved products grouped by issue."""
    try:
        store = load_store(store_id)
        products = load_feed(store_id)
    except StoreNotFoundError as error:
        return {"error": str(error)}

    issues = [issue for product in products for issue in run_checks(product)]
    return {
        "store_id": store.store_id,
        "store_name": store.name,
        "account_status": store.account_status.value,
        "suspension_reason": store.suspension_reason,
        "total_products": len(products),
        "products_with_issues": len({issue.product_id for issue in issues}),
        "issue_groups": group_issues(issues, products),
    }


def group_issues(issues: list[Issue], products: list[Product]) -> list[dict]:
    """Group issues by type, biggest group first, with the affected products listed."""
    titles = {product.id: product.title for product in products}
    groups: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        groups[issue.issue_type.value].append(issue)

    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    return [
        {
            "issue_type": issue_type,
            "field": group[0].field,
            "count": len(group),
            "products": [
                {"id": i.product_id, "title": titles[i.product_id], "detail": i.detail}
                for i in group
            ],
        }
        for issue_type, group in ordered
    ]
