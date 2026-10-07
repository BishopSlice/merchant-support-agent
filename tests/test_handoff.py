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
        "merchant_reasons": [],
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


def test_clear_cases_deletes_every_case(runtime_dir):
    from merchant_agent.tools.handoff import clear_cases

    make_case()
    make_case()
    assert clear_cases() == 2
    assert list_cases() == []
    assert clear_cases() == 0


def test_get_case_cannot_read_files_outside_the_cases_folder(runtime_dir):
    (runtime_dir / "secret.json").write_text("{}")
    make_case()  # creates the cases folder
    assert get_case("../secret") is None


def test_unknown_store_is_rejected_and_nothing_saved():
    result = make_case(store_id="no-such-store")
    assert result["status"] == "error"
    assert list_cases() == []


def test_list_cases_sorts_by_time_not_by_file_name():
    from datetime import UTC, datetime

    from merchant_agent.models import Case
    from merchant_agent.tools.handoff import save_case

    def case(case_id: str, hour: int) -> Case:
        return Case(
            case_id=case_id,
            store_id="sample-store",
            created_at=datetime(2026, 10, 7, hour, tzinfo=UTC),
            reason="merchant_requested_human",
            merchant_request="Talk to a person",
            suggested_next_step="Call back",
        )

    # Alphabetical order is the reverse of time order.
    for case_id, hour in [("CASE-a", 9), ("CASE-b", 10), ("CASE-c", 11)]:
        save_case(case(case_id, hour))
    assert [c.case_id for c in list_cases()] == ["CASE-c", "CASE-b", "CASE-a"]


def test_a_corrupt_case_file_is_skipped_with_a_warning(runtime_dir, caplog):
    good = make_case()["case_id"]
    (runtime_dir / "cases" / "CASE-broken.json").write_text("{not json")
    assert [case.case_id for case in list_cases()] == [good]
    assert "CASE-broken.json" in caplog.text


def test_merchant_reasons_are_saved_with_the_case():
    case_id = make_case(merchant_reasons=["It's just a candle", "Other shops sell them"])["case_id"]
    assert get_case(case_id).merchant_reasons == ["It's just a candle", "Other shops sell them"]


def test_merchant_reasons_default_to_empty_for_older_case_files(runtime_dir):
    from merchant_agent.models import Case

    old = make_case()
    path = runtime_dir / "cases" / f"{old['case_id']}.json"
    data = path.read_text().replace('"merchant_reasons": [],', "")
    assert Case.model_validate_json(data).merchant_reasons == []


def test_merchant_reasons_reject_contact_details():
    result = make_case(merchant_reasons=["Call me on +1 415 555 0134"])
    assert result["status"] == "error"
