"""Pydantic models mirroring the Merchant API resources the agent reads.

Field names and enum values follow Google's Merchant API reference (read 8 Oct 2026):
- Product, ProductStatus, ItemLevelIssue, Severity:
  https://developers.google.com/merchant/api/reference/rest/products_v1/accounts.products
- AccountIssue: https://developers.google.com/merchant/api/reference/rest/accounts_v1/accounts.issues
- AggregateProductStatus:
  https://developers.google.com/merchant/api/reference/rest/issueresolution_v1/accounts.aggregateProductStatuses
- AutomaticImprovements:
  https://developers.google.com/merchant/api/reference/rest/accounts_v1/accounts.automaticImprovements

Models forbid extra fields, so the mock can only emit documented fields. Only the subset of
each resource that the agent uses is modelled; product attributes are kept as a plain dict.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Severity(StrEnum):
    """How an item-level issue affects serving (Product and aggregate statuses)."""

    SEVERITY_UNSPECIFIED = "SEVERITY_UNSPECIFIED"
    NOT_IMPACTED = "NOT_IMPACTED"
    DEMOTED = "DEMOTED"
    DISAPPROVED = "DISAPPROVED"


class AccountIssueSeverity(StrEnum):
    """Severity of an account-level issue."""

    SEVERITY_UNSPECIFIED = "SEVERITY_UNSPECIFIED"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    SUGGESTION = "SUGGESTION"


class Resolution(StrEnum):
    """How an aggregate issue can be resolved."""

    RESOLUTION_UNSPECIFIED = "RESOLUTION_UNSPECIFIED"
    MERCHANT_ACTION = "MERCHANT_ACTION"
    PENDING_PROCESSING = "PENDING_PROCESSING"


# --- Products ---


class ItemLevelIssue(_Resource):
    code: str
    severity: Severity
    resolution: str | None = None
    attribute: str | None = None
    reportingContext: str | None = None
    description: str | None = None
    detail: str | None = None
    documentation: str | None = None
    applicableCountries: list[str] = Field(default_factory=list)


class DestinationStatus(_Resource):
    reportingContext: str
    approvedCountries: list[str] = Field(default_factory=list)
    pendingCountries: list[str] = Field(default_factory=list)
    disapprovedCountries: list[str] = Field(default_factory=list)


class ProductStatus(_Resource):
    destinationStatuses: list[DestinationStatus] = Field(default_factory=list)
    itemLevelIssues: list[ItemLevelIssue] = Field(default_factory=list)
    creationDate: str | None = None
    lastUpdateDate: str | None = None
    googleExpirationDate: str | None = None


class Product(_Resource):
    name: str
    offerId: str
    contentLanguage: str
    feedLabel: str
    productAttributes: dict[str, Any] = Field(default_factory=dict)
    productStatus: ProductStatus


def product_name(account: str, offer_id: str, language: str = "en", feed_label: str = "US") -> str:
    """The documented product name: accounts/{account}/products/{language}~{feedLabel}~{offerId}."""
    return f"accounts/{account}/products/{language}~{feed_label}~{offer_id}"


# --- Account issues ---


class Impact(_Resource):
    regionCode: str
    severity: AccountIssueSeverity


class ImpactedDestination(_Resource):
    reportingContext: str
    impacts: list[Impact] = Field(default_factory=list)


class AccountIssue(_Resource):
    name: str
    title: str
    severity: AccountIssueSeverity
    impactedDestinations: list[ImpactedDestination] = Field(default_factory=list)
    detail: str | None = None
    documentationUri: str | None = None


# --- Aggregate product statuses ---


class Stats(_Resource):
    activeCount: str
    pendingCount: str
    disapprovedCount: str
    expiringCount: str


class AggregateItemLevelIssue(_Resource):
    code: str
    severity: Severity
    resolution: Resolution
    attribute: str | None = None
    description: str | None = None
    detail: str | None = None
    documentationUri: str | None = None
    productCount: str


class AggregateProductStatus(_Resource):
    name: str
    reportingContext: str
    country: str
    stats: Stats
    itemLevelIssues: list[AggregateItemLevelIssue] = Field(default_factory=list)


# --- Automatic improvements ---


class ItemUpdatesAccountLevelSettings(_Resource):
    allowPriceUpdates: bool
    allowAvailabilityUpdates: bool
    allowStrictAvailabilityUpdates: bool
    allowConditionUpdates: bool


class AutomaticItemUpdates(_Resource):
    accountItemUpdatesSettings: ItemUpdatesAccountLevelSettings | None = None
    effectiveAllowPriceUpdates: bool
    effectiveAllowAvailabilityUpdates: bool
    effectiveAllowStrictAvailabilityUpdates: bool
    effectiveAllowConditionUpdates: bool


class ImageImprovementsAccountLevelSettings(_Resource):
    allowAutomaticImageImprovements: bool


class AutomaticImageImprovements(_Resource):
    effectiveAllowAutomaticImageImprovements: bool
    accountImageImprovementsSettings: ImageImprovementsAccountLevelSettings | None = None


class AutomaticShippingImprovements(_Resource):
    allowShippingImprovements: bool


class AutomaticImprovements(_Resource):
    name: str
    itemUpdates: AutomaticItemUpdates
    imageImprovements: AutomaticImageImprovements
    shippingImprovements: AutomaticShippingImprovements
