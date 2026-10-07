import json

import pytest

from merchant_agent.models import HandoffReason
from merchant_agent.tools.handoff import create_handoff_case, get_case, list_cases


@pytest.fixture(autouse=True)
def runtime_dir(monkeypatch, tmp_path):
    """Save cases in a temporary folder, never the real runtime/ folder."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    return tmp_path


def make_case(**overrides) -> dict:
    fields = {
        "store_id": "sample-store",
        "reason": "policy_appeal",
        "issues_found": ["restricted_product: HG-023 CBD candle"],
        "already_tried": ["Explained the CBD policy"],
        "merchant_request": "Appeal the CBD disapproval",
        "suggested_next_step": "Review whether the candle qualifies for an exception",
        "cited_doc_ids": ["cbd-unapproved-substances", "request-review"],
    }
    return create_handoff_case(**(fields | overrides))


def test_handoff_reasons_match_the_prd_rules():
    assert {reason.value for reason in HandoffReason} == {
        "account_suspended",
        "policy_appeal",
        "merchant_requested_human",
        "repeated_failure_or_frustration",
        "no_supporting_doc",
    }


def test_creating_a_case_saves_it_as_json(runtime_dir):
    result = make_case()
    assert result["status"] == "created"
    path = runtime_dir / "cases" / f"{result['case_id']}.json"
    saved = json.loads(path.read_text())
    assert saved["store_id"] == "sample-store"
    assert saved["reason"] == "policy_appeal"
    assert saved["cited_doc_ids"] == ["cbd-unapproved-substances", "request-review"]
    assert saved["created_at"]


def test_get_case_returns_the_saved_case():
    case_id = make_case()["case_id"]
    case = get_case(case_id)
    assert case.case_id == case_id
    assert case.reason is HandoffReason.POLICY_APPEAL


def test_get_case_returns_none_for_unknown_or_unsafe_ids():
    assert get_case("CASE-does-not-exist") is None
    assert get_case("../../.env") is None


def test_list_cases_returns_newest_first():
    first = make_case()["case_id"]
    second = make_case(reason="account_suspended")["case_id"]
    assert [case.case_id for case in list_cases()] == [second, first]


def test_list_cases_is_empty_when_nothing_saved():
    assert list_cases() == []


def test_unknown_reason_is_rejected_and_nothing_saved(runtime_dir):
    result = make_case(reason="merchant_is_annoying")
    assert result["status"] == "error"
    assert "account_suspended" in result["message"]  # lists the valid reasons
    assert list_cases() == []


@pytest.mark.parametrize(
    "text",
    ["Merchant email is jane.doe@example.com", "Call them on +1 415 555 0134"],
)
def test_personal_contact_details_are_rejected(text):
    result = make_case(merchant_request=text)
    assert result["status"] == "error"
    assert "personal" in result["message"].lower()
    assert list_cases() == []


def test_required_text_fields_cannot_be_blank():
    assert make_case(suggested_next_step="  ")["status"] == "error"


def test_barcodes_prices_and_product_ids_are_not_mistaken_for_phone_numbers():
    result = make_case(
        issues_found=[
            "missing_gtin: HG-019, GTIN 0850012345012 expected",
            "price_mismatch: HG-004 feed 32.00 USD vs page 36.00 USD",
        ]
    )
    assert result["status"] == "created"
