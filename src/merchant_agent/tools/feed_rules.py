"""Rule checks for product feeds. Each check looks at one product and returns its issues.

To add a rule: write a test with a planted problem, add a check function here,
and append it to RULES.
"""

from collections.abc import Callable

from merchant_agent.models import Issue, IssueType, Product

Rule = Callable[[Product], list[Issue]]


def check_missing_gtin(product: Product) -> list[Issue]:
    """Flag products with no GTIN (the barcode number Google uses to identify a product)."""
    if product.gtin.strip():
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.MISSING_GTIN,
            field="gtin",
            detail="No GTIN (barcode number) is set for this product.",
        )
    ]


RULES: list[Rule] = [
    check_missing_gtin,
]


def run_checks(product: Product) -> list[Issue]:
    """Run every registered rule on one product and return all issues found."""
    return [issue for rule in RULES for issue in rule(product)]
