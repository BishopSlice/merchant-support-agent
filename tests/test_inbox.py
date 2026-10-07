from datetime import UTC, datetime

from merchant_agent.inbox import REASON_LABELS, case_label, format_case
from merchant_agent.models import Case, HandoffReason


def sample_case(**overrides) -> Case:
    fields = {
        "case_id": "CASE-20261007-102336-99664d",
        "store_id": "sample-store",
        "created_at": datetime(2026, 10, 7, 10, 23, tzinfo=UTC),
        "reason": "policy_appeal",
        "issues_found": ["restricted_product: HG-023"],
        "already_tried": ["Merchant fixed missing shipping"],
        "merchant_request": "Appeal the CBD candle disapproval",
        "suggested_next_step": "Review HG-023 under the restricted content policy",
        "cited_doc_ids": ["request-review", "not-a-real-doc"],
    }
    return Case(**(fields | overrides))


def test_every_reason_has_a_plain_label():
    assert set(REASON_LABELS) == set(HandoffReason)


def test_case_label_shows_id_store_reason_and_time():
    assert case_label(sample_case()) == (
        "CASE-20261007-102336-99664d · sample-store · Policy appeal · 7 Oct 2026, 10:23 UTC"
    )


def test_format_case_has_every_section_in_order():
    text = format_case(sample_case())
    headings = [
        "Reason",
        "What the merchant wants",
        "Issues found",
        "Already tried",
        "Suggested next step",
        "Help docs cited",
    ]
    positions = [text.index(f"**{heading}**") for heading in headings]
    assert positions == sorted(positions)
    assert "Policy appeal" in text
    assert "- restricted_product: HG-023" in text
    assert "Review HG-023" in text


def test_cited_docs_become_links_and_unknown_ids_are_flagged():
    text = format_case(sample_case())
    assert (
        "[Requesting a review or appealing a decision]"
        "(https://support.google.com/merchants/answer/13585221)"
    ) in text
    assert "not-a-real-doc (unknown doc)" in text


def test_empty_lists_say_none():
    text = format_case(sample_case(already_tried=[], cited_doc_ids=[]))
    assert text.count("_None_") == 3  # steps tried, docs cited, and no merchant reasons


def test_merchant_reasons_are_shown_right_after_what_the_merchant_wants():
    text = format_case(sample_case(merchant_reasons=["It's just a candle"]))
    assert text.index("**What the merchant wants**") < text.index("**Merchant's reasons**")
    assert text.index("**Merchant's reasons**") < text.index("**Issues found**")
    assert "- It's just a candle" in text
