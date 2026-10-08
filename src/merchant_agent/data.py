"""The agent's data layer: a mock of Google's Merchant API MCP, serving the demo stores.

`MockMerchantMcp` answers the same read tools as the Merchant API MCP Access Service
(https://developers.google.com/merchant/api/guides/agentic-tools/merchant-data-mcp) with
responses shaped like the documented Merchant API resources (see `merchant_api`). It builds
them from the v1 stores and feed rules, so the issues it reports are exactly what the v1
checker found. It is not connected to Google (ADR 0004).

Only the read tools in ALLOWED_TOOLS can be called. Every other tool the real MCP offers,
including all data-source write tools, raises ToolNotAllowedError.

Issue codes are this project's own (for example "price_mismatch"); Google doesn't publish a
complete list, so they are illustrative. Field names and enum values are Google's.
"""

from collections import Counter
from decimal import Decimal, InvalidOperation

from merchant_agent.merchant_api import (
    AccountIssue,
    AccountIssueSeverity,
    AggregateItemLevelIssue,
    AggregateProductStatus,
    AutomaticImageImprovements,
    AutomaticImprovements,
    AutomaticItemUpdates,
    AutomaticShippingImprovements,
    DestinationStatus,
    ImageImprovementsAccountLevelSettings,
    Impact,
    ImpactedDestination,
    ItemLevelIssue,
    ItemUpdatesAccountLevelSettings,
    Product,
    ProductStatus,
    Resolution,
    Severity,
    Stats,
    product_name,
)
from merchant_agent.models import AccountStatus, IssueType
from merchant_agent.models import Product as FeedProduct
from merchant_agent.stores import StoreNotFoundError, load_feed, load_store
from merchant_agent.tools.feed_rules import run_checks
from merchant_agent.tools.help_search import load_help_docs

ALLOWED_TOOLS = frozenset(
    {
        "list_products",
        "get_product_by_name",
        "list_account_issues",
        "list_aggregate_product_statuses",
        "get_automatic_improvements",
    }
)
# Tools the real MCP offers that the agent must never use: the data-source write tools,
# plus read tools it doesn't need (fewer tools, smaller attack surface).
BLOCKED_TOOLS = frozenset(
    {
        "create_data_source",
        "fetch_data_source",
        "get_file_upload",
        "get_data_source",
        "list_data_sources",
        "report_search",
        "list_accounts",
        "list_programs",
    }
)

REPORTING_CONTEXT = "SHOPPING_ADS"
COUNTRY = "US"

# Issue type -> (Merchant API severity, documented attribute name, short description).
ISSUES = {
    IssueType.MISSING_GTIN: (Severity.DEMOTED, "gtins", "Missing value [gtin]"),
    IssueType.PRICE_MISMATCH: (Severity.DISAPPROVED, "price", "Mismatched value (page crawl) [price]"),
    IssueType.INVALID_IMAGE: (Severity.DISAPPROVED, "imageLink", "Invalid or placeholder image [image_link]"),
    IssueType.TITLE_TOO_LONG: (Severity.DISAPPROVED, "title", "Text too long [title]"),
    IssueType.AVAILABILITY_MISMATCH: (
        Severity.DISAPPROVED,
        "availability",
        "Mismatched value (page crawl) [availability]",
    ),
    IssueType.MISSING_SHIPPING: (Severity.DISAPPROVED, "shipping", "Missing shipping information"),
    IssueType.RESTRICTED_PRODUCT: (
        Severity.DISAPPROVED,
        "productTypes",
        "Restricted product (unapproved substances policy)",
    ),
}


class ToolNotAllowedError(PermissionError):
    """Raised when anything calls a tool outside the read-only allowlist."""


def _documentation_urls() -> dict[str, str]:
    """Issue code -> source URL of the first help doc (by id) that covers it."""
    urls: dict[str, str] = {}
    for doc in sorted(load_help_docs(), key=lambda doc: doc.doc_id):
        for code in doc.issue_codes:
            urls.setdefault(code, doc.source_url)
    return urls


def _price(text: str) -> dict | None:
    """"14.00 USD" -> {"amountMicros": "14000000", "currencyCode": "USD"}."""
    parts = text.split()
    if len(parts) != 2:
        return None
    try:
        micros = int(Decimal(parts[0]) * 1_000_000)
    except InvalidOperation:
        return None
    return {"amountMicros": str(micros), "currencyCode": parts[1].upper()}


def _shipping(text: str) -> list[dict]:
    """"US:::5.95 USD" -> [{"country": "US", "price": {...}}]."""
    if not text.strip():
        return []
    country, _, _, price = (text.split(":") + ["", "", "", ""])[:4]
    entry: dict = {"country": country or COUNTRY}
    if parsed := _price(price):
        entry["price"] = parsed
    return [entry]


def _attributes(product: FeedProduct) -> dict:
    """Product data under the Merchant API's documented attribute names."""
    attributes = {
        "title": product.title,
        "description": product.description,
        "link": product.link,
        "imageLink": product.image_link,
        "availability": product.availability.strip().upper().replace(" ", "_"),
        "brand": product.brand,
        "gtins": [product.gtin] if product.gtin.strip() else [],
        "productTypes": [product.product_type] if product.product_type else [],
        "shipping": _shipping(product.shipping),
    }
    if price := _price(product.price):
        attributes["price"] = price
    return {key: value for key, value in attributes.items() if value not in ("", None)}


class MockMerchantMcp:
    """Serves the demo stores through the Merchant API MCP's read tools."""

    def call(self, tool: str, **arguments) -> dict:
        """Run one allowlisted tool. Tools outside the allowlist raise ToolNotAllowedError."""
        if tool not in ALLOWED_TOOLS:
            raise ToolNotAllowedError(f"Tool {tool!r} is not allowed; the agent is read-only")
        try:
            return getattr(self, tool)(**arguments)
        except StoreNotFoundError as error:
            return {"error": str(error)}

    # --- Tools ---

    def list_products(self, account: str) -> dict:
        load_store(account)  # unknown accounts raise StoreNotFoundError
        return {"products": [self._product(account, p) for p in load_feed(account)]}

    def get_product_by_name(self, name: str) -> dict:
        parts = name.split("/")
        if len(parts) != 4 or parts[0] != "accounts" or parts[2] != "products":
            return {"error": f"Not a product name: {name!r}"}
        account, offer_id = parts[1], parts[3].split("~")[-1]
        for product in self.list_products(account)["products"]:
            if product["name"] == name:
                return product
        return {"error": f"No product {offer_id!r} in account {account!r}"}

    def list_account_issues(self, account: str) -> dict:
        store = load_store(account)
        if store.account_status is not AccountStatus.SUSPENDED:
            return {"accountIssues": []}
        title = store.suspension_reason.split(":")[0] or "Account suspended"
        issue = AccountIssue(
            name=f"accounts/{account}/issues/{title.lower().replace(' ', '-')}",
            title=title,
            severity=AccountIssueSeverity.CRITICAL,
            impactedDestinations=[
                ImpactedDestination(
                    reportingContext=REPORTING_CONTEXT,
                    impacts=[Impact(regionCode=COUNTRY, severity=AccountIssueSeverity.CRITICAL)],
                )
            ],
            detail=store.suspension_reason,
            documentationUri=_documentation_urls().get("account_suspended"),
        )
        return {"accountIssues": [issue.model_dump(mode="json", exclude_none=True)]}

    def list_aggregate_product_statuses(self, account: str) -> dict:
        products = self.list_products(account)["products"]
        issues = [i for p in products for i in p["productStatus"]["itemLevelIssues"]]
        disapproved = sum(
            any(i["severity"] == Severity.DISAPPROVED for i in p["productStatus"]["itemLevelIssues"])
            for p in products
        )
        counts = Counter(issue["code"] for issue in issues)
        first = {issue["code"]: issue for issue in reversed(issues)}
        status = AggregateProductStatus(
            name=f"accounts/{account}/aggregateProductStatuses/{REPORTING_CONTEXT}~{COUNTRY}",
            reportingContext=REPORTING_CONTEXT,
            country=COUNTRY,
            stats=Stats(
                activeCount=str(len(products) - disapproved),
                pendingCount="0",
                disapprovedCount=str(disapproved),
                expiringCount="0",
            ),
            itemLevelIssues=[
                AggregateItemLevelIssue(
                    code=code,
                    severity=first[code]["severity"],
                    resolution=Resolution.MERCHANT_ACTION,
                    attribute=first[code].get("attribute"),
                    description=first[code].get("description"),
                    documentationUri=first[code].get("documentation"),
                    productCount=str(count),
                )
                for code, count in counts.most_common()
            ],
        )
        return {"aggregateProductStatuses": [status.model_dump(mode="json", exclude_none=True)]}

    def get_automatic_improvements(self, account: str) -> dict:
        settings = load_store(account).automatic_improvements
        if settings is None:
            return {"error": f"Store {account!r} doesn't declare its automatic improvements"}
        item = ItemUpdatesAccountLevelSettings(
            allowPriceUpdates=settings.price_updates,
            allowAvailabilityUpdates=settings.availability_updates,
            allowStrictAvailabilityUpdates=False,
            allowConditionUpdates=False,
        )
        improvements = AutomaticImprovements(
            name=f"accounts/{account}/automaticImprovements",
            itemUpdates=AutomaticItemUpdates(
                accountItemUpdatesSettings=item,
                effectiveAllowPriceUpdates=item.allowPriceUpdates,
                effectiveAllowAvailabilityUpdates=item.allowAvailabilityUpdates,
                effectiveAllowStrictAvailabilityUpdates=item.allowStrictAvailabilityUpdates,
                effectiveAllowConditionUpdates=item.allowConditionUpdates,
            ),
            imageImprovements=AutomaticImageImprovements(
                effectiveAllowAutomaticImageImprovements=settings.image_improvements,
                accountImageImprovementsSettings=ImageImprovementsAccountLevelSettings(
                    allowAutomaticImageImprovements=settings.image_improvements
                ),
            ),
            shippingImprovements=AutomaticShippingImprovements(
                allowShippingImprovements=settings.shipping_improvements
            ),
        )
        return improvements.model_dump(mode="json", exclude_none=True)

    # --- Building products ---

    def _product(self, account: str, product: FeedProduct) -> dict:
        urls = _documentation_urls()
        issues = [
            ItemLevelIssue(
                code=issue.issue_type.value,
                severity=ISSUES[issue.issue_type][0],
                resolution="merchant_action",
                attribute=ISSUES[issue.issue_type][1],
                reportingContext=REPORTING_CONTEXT,
                description=ISSUES[issue.issue_type][2],
                detail=issue.detail,
                documentation=urls.get(issue.issue_type.value),
                applicableCountries=[COUNTRY],
            )
            for issue in run_checks(product)
        ]
        disapproved = any(issue.severity is Severity.DISAPPROVED for issue in issues)
        destination = DestinationStatus(
            reportingContext=REPORTING_CONTEXT,
            approvedCountries=[] if disapproved else [COUNTRY],
            disapprovedCountries=[COUNTRY] if disapproved else [],
        )
        return Product(
            name=product_name(account, product.id),
            offerId=product.id,
            contentLanguage="en",
            feedLabel=COUNTRY,
            productAttributes=_attributes(product),
            productStatus=ProductStatus(destinationStatuses=[destination], itemLevelIssues=issues),
        ).model_dump(mode="json", exclude_none=True)
