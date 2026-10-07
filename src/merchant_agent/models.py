"""Shared data shapes: stores, products, issues and handoff cases."""

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


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


class Severity(StrEnum):
    """How badly an issue hurts a product."""

    DISAPPROVED = "disapproved"  # the product can't show at all
    LIMITED = "limited"  # the product shows, but with reduced reach


class Issue(BaseModel):
    """One problem found on one product."""

    product_id: str
    issue_type: IssueType
    severity: Severity
    field: str
    detail: str


class HandoffReason(StrEnum):
    """Why a case went to a human specialist. One value per handoff rule in the PRD."""

    ACCOUNT_SUSPENDED = "account_suspended"
    POLICY_APPEAL = "policy_appeal"
    MERCHANT_REQUESTED_HUMAN = "merchant_requested_human"
    REPEATED_FAILURE_OR_FRUSTRATION = "repeated_failure_or_frustration"
    NO_SUPPORTING_DOC = "no_supporting_doc"


# Contact details a case must not contain. Plain digit runs are allowed, since GTINs are
# 8 to 14 digits; phone numbers are caught by a leading "+" or US-style separators.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+\d[\d\s().-]{6,}\d|\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")


class Case(BaseModel):
    """A structured handoff case for a human support specialist. Holds no personal details."""

    case_id: str
    store_id: str
    created_at: datetime
    reason: HandoffReason
    issues_found: list[str] = Field(default_factory=list)
    already_tried: list[str] = Field(default_factory=list)
    merchant_request: str
    merchant_reasons: list[str] = Field(default_factory=list)
    suggested_next_step: str
    cited_doc_ids: list[str] = Field(default_factory=list)

    @field_validator("merchant_request", "suggested_next_step")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator(
        "issues_found", "already_tried", "merchant_request", "merchant_reasons", "suggested_next_step"
    )
    @classmethod
    def _no_personal_details(cls, value: str | list[str]) -> str | list[str]:
        texts = [value] if isinstance(value, str) else value
        if any(_EMAIL.search(text) or _PHONE.search(text) for text in texts):
            raise ValueError("contains personal contact details (email or phone); leave them out")
        return value


class HelpDoc(BaseModel):
    """A short paraphrased summary of one Merchant Center help page."""

    doc_id: str
    title: str
    source_url: str
    issue_codes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    passages: list[str] = Field(default_factory=list)
