"""Rule checks for product feeds. Each check looks at one product and returns its issues.

To add a rule: write a test with a planted problem, add a check function here,
and append it to RULES.
"""

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

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


def _parse_price(text: str) -> tuple[Decimal, str] | None:
    """Turn "14.00 USD" into (Decimal("14.00"), "USD"), or None if it can't be read."""
    parts = text.split()
    if len(parts) != 2:
        return None
    try:
        return Decimal(parts[0]), parts[1].upper()
    except InvalidOperation:
        return None


def check_price_mismatch(product: Product) -> list[Issue]:
    """Flag products whose feed price differs from the price on their landing page."""
    feed_price = _parse_price(product.price)
    page_price = _parse_price(product.landing_page_price)
    if feed_price is None or page_price is None or feed_price == page_price:
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.PRICE_MISMATCH,
            field="price",
            detail=(
                f"Feed price is {product.price} but the product page shows "
                f"{product.landing_page_price}."
            ),
        )
    ]


RULES: list[Rule] = [
    check_missing_gtin,
    check_price_mismatch,
]


def run_checks(product: Product) -> list[Issue]:
    """Run every registered rule on one product and return all issues found."""
    return [issue for rule in RULES for issue in rule(product)]
