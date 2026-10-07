"""The check_feed tool: run every rule over a store's feed and group the results."""

from collections import defaultdict

from merchant_agent.models import Issue, Product, Severity
from merchant_agent.stores import StoreNotFoundError, load_feed, load_store
from merchant_agent.tools.feed_rules import run_checks


def check_feed(store_id: str) -> dict:
    """Check a store's product feed and return its problems grouped by issue type.

    Disapprovals (the product can't show) come first, then warnings that limit reach.
    """
    try:
        store = load_store(store_id)
        products = load_feed(store_id)
    except StoreNotFoundError as error:
        return {"error": str(error)}

    issues = [issue for product in products for issue in run_checks(product)]
    with_issues = {issue.product_id for issue in issues}
    disapproved = {i.product_id for i in issues if i.severity is Severity.DISAPPROVED}
    return {
        "store_id": store.store_id,
        "store_name": store.name,
        "account_status": store.account_status.value,
        "suspension_reason": store.suspension_reason,
        "total_products": len(products),
        "products_with_issues": len(with_issues),
        "disapproved_products": len(disapproved),
        "limited_products": len(with_issues - disapproved),
        "issue_groups": group_issues(issues, products),
    }


def group_issues(issues: list[Issue], products: list[Product]) -> list[dict]:
    """Group issues by type, disapprovals first and then biggest first, listing products."""
    titles = {product.id: product.title for product in products}
    groups: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        groups[issue.issue_type.value].append(issue)

    def order(item: tuple[str, list[Issue]]) -> tuple[bool, int, str]:
        issue_type, group = item
        return group[0].severity is not Severity.DISAPPROVED, -len(group), issue_type

    ordered = sorted(groups.items(), key=order)
    return [
        {
            "issue_type": issue_type,
            "severity": group[0].severity.value,
            "field": group[0].field,
            "count": len(group),
            "products": [
                {"id": i.product_id, "title": titles[i.product_id], "detail": i.detail}
                for i in group
            ],
        }
        for issue_type, group in ordered
    ]
