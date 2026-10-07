"""Rule checks for product feeds. Each check looks at one product and returns its issues.

To add a rule: write a test with a planted problem, add a check function here,
and append it to RULES.
"""

import re
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


PLACEHOLDER_IMAGE_WORDS = ("placeholder", "no-image", "noimage", "coming-soon")


def _image_problem(image_link: str) -> str:
    """Describe what is wrong with an image link, or return "" if it looks fine."""
    link = image_link.strip()
    if not link:
        return "No image link is set."
    if not link.startswith(("http://", "https://")):
        return f"Image link {link!r} is not a full web address."
    if any(word in link.lower() for word in PLACEHOLDER_IMAGE_WORDS):
        return f"Image link {link!r} points to a placeholder, not a real product photo."
    return ""


def check_invalid_image(product: Product) -> list[Issue]:
    """Flag products with a missing, malformed or placeholder image link."""
    problem = _image_problem(product.image_link)
    if not problem:
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.INVALID_IMAGE,
            field="image_link",
            detail=problem,
        )
    ]


MAX_TITLE_LENGTH = 150


def check_title_too_long(product: Product) -> list[Issue]:
    """Flag products whose title is longer than Google's 150 character limit."""
    length = len(product.title)
    if length <= MAX_TITLE_LENGTH:
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.TITLE_TOO_LONG,
            field="title",
            detail=f"Title is {length} characters; the limit is {MAX_TITLE_LENGTH}.",
        )
    ]


def _normalize_availability(value: str) -> str:
    """Treat "In stock", "in stock" and "in_stock" as the same value."""
    return value.strip().lower().replace(" ", "_")


def check_availability_mismatch(product: Product) -> list[Issue]:
    """Flag products whose feed availability differs from what their landing page says."""
    feed = _normalize_availability(product.availability)
    page = _normalize_availability(product.landing_page_availability)
    if not feed or not page or feed == page:
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.AVAILABILITY_MISMATCH,
            field="availability",
            detail=f"Feed says {feed} but the product page says {page}.",
        )
    ]


def check_missing_shipping(product: Product) -> list[Issue]:
    """Flag products with no shipping cost set."""
    if product.shipping.strip():
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.MISSING_SHIPPING,
            field="shipping",
            detail="No shipping cost is set for this product.",
        )
    ]


RESTRICTED_TERMS = ("cbd", "cannabidiol", "hemp extract")
_RESTRICTED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in RESTRICTED_TERMS) + r")\b", re.IGNORECASE
)


def check_restricted_product(product: Product) -> list[Issue]:
    """Flag products that fall under a restricted content policy, such as CBD."""
    match = _RESTRICTED_PATTERN.search(f"{product.title} {product.product_type}")
    if not match:
        return []
    return [
        Issue(
            product_id=product.id,
            issue_type=IssueType.RESTRICTED_PRODUCT,
            field="product_type",
            detail=f"Mentions {match.group(0)!r}, which is a restricted product category.",
        )
    ]


RULES: list[Rule] = [
    check_missing_gtin,
    check_price_mismatch,
    check_invalid_image,
    check_title_too_long,
    check_availability_mismatch,
    check_missing_shipping,
    check_restricted_product,
]


def run_checks(product: Product) -> list[Issue]:
    """Run every registered rule on one product and return all issues found."""
    return [issue for rule in RULES for issue in rule(product)]
