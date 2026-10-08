"""Contract tests: our Merchant API models must accept Google's documented shapes, and only them."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from merchant_agent.merchant_api import (
    AccountIssue,
    AggregateProductStatus,
    AutomaticImprovements,
    Product,
    Severity,
    product_name,
)

FIXTURES = Path(__file__).parent / "fixtures" / "merchant_api"
MODELS = {
    "product.json": Product,
    "account_issue.json": AccountIssue,
    "aggregate_product_status.json": AggregateProductStatus,
    "automatic_improvements.json": AutomaticImprovements,
}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize("name", sorted(MODELS))
def test_every_fixture_cites_a_google_reference_page(name):
    assert fixture(name)["source"].startswith("https://developers.google.com/merchant/api/reference/")


@pytest.mark.parametrize(("name", "model"), sorted(MODELS.items()))
def test_documented_examples_validate_and_round_trip(name, model):
    example = fixture(name)["example"]
    parsed = model.model_validate(example)
    assert parsed.model_dump(mode="json", exclude_none=True) == example


@pytest.mark.parametrize(("name", "model"), sorted(MODELS.items()))
def test_fields_google_does_not_document_are_rejected(name, model):
    example = fixture(name)["example"] | {"madeUpField": 1}
    with pytest.raises(ValidationError):
        model.model_validate(example)


def test_item_issue_severity_only_takes_documented_values():
    assert {s.value for s in Severity} == {
        "SEVERITY_UNSPECIFIED",
        "NOT_IMPACTED",
        "DEMOTED",
        "DISAPPROVED",
    }
    example = fixture("product.json")["example"]
    example["productStatus"]["itemLevelIssues"][0]["severity"] = "LIMITED"
    with pytest.raises(ValidationError):
        Product.model_validate(example)


def test_account_issue_severity_uses_its_own_documented_enum():
    example = fixture("account_issue.json")["example"]
    example["severity"] = "DISAPPROVED"
    with pytest.raises(ValidationError):
        AccountIssue.model_validate(example)


def test_product_names_follow_the_documented_format():
    assert product_name("123", "sku123") == "accounts/123/products/en~US~sku123"
