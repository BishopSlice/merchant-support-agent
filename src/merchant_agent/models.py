"""Shared data shapes: stores, products, issues and handoff cases."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AccountStatus(StrEnum):
    """Whether a merchant's account can show products at all."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class Store(BaseModel):
    """A merchant's store and the state of its Merchant Center account."""

    store_id: str
    name: str
    country: str = "US"
    account_status: AccountStatus = AccountStatus.ACTIVE
    suspension_reason: str = ""


class Product(BaseModel):
    """One row of a product feed, plus what the product's landing page shows.

    The landing_page_* fields simulate crawling the merchant's website, which a
    real system would do but we cannot in v1.
    """

    id: str
    title: str
    description: str = ""
    link: str = ""
    image_link: str = ""
    price: str = ""
    availability: str = ""
    brand: str = ""
    gtin: str = ""
    product_type: str = ""
    shipping: str = ""
    landing_page_price: str = ""
    landing_page_availability: str = ""


class IssueType(StrEnum):
    """Every kind of problem the feed checker knows how to find."""

    MISSING_GTIN = "missing_gtin"
    PRICE_MISMATCH = "price_mismatch"
    INVALID_IMAGE = "invalid_image"
    TITLE_TOO_LONG = "title_too_long"
    AVAILABILITY_MISMATCH = "availability_mismatch"
    MISSING_SHIPPING = "missing_shipping"
    RESTRICTED_PRODUCT = "restricted_product"


class Issue(BaseModel):
    """One problem found on one product."""

    product_id: str
    issue_type: IssueType
    field: str
    detail: str


class Case(BaseModel):
    """A structured handoff case for a human support specialist."""

    case_id: str
    store_id: str
    created_at: datetime
    reason: str
    issues_found: list[str] = Field(default_factory=list)
    already_tried: list[str] = Field(default_factory=list)
    merchant_request: str
    suggested_next_step: str


class HelpDoc(BaseModel):
    """A short paraphrased summary of one Merchant Center help page."""

    doc_id: str
    title: str
    source_url: str
    issue_codes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    passages: list[str] = Field(default_factory=list)
