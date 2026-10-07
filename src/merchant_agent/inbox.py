"""Lay out handoff cases for the specialist inbox."""

from merchant_agent.models import Case, HandoffReason
from merchant_agent.tools.help_search import load_help_docs

REASON_LABELS = {
    HandoffReason.ACCOUNT_SUSPENDED: "Account suspended",
    HandoffReason.POLICY_APPEAL: "Policy appeal",
    HandoffReason.MERCHANT_REQUESTED_HUMAN: "Merchant asked for a person",
    HandoffReason.REPEATED_FAILURE_OR_FRUSTRATION: "Repeated failure or frustration",
    HandoffReason.NO_SUPPORTING_DOC: "No help doc covers it",
}


def case_label(case: Case) -> str:
    """One line naming a case, for the inbox list."""
    created = f"{case.created_at:%-d %b %Y, %H:%M} UTC"
    return f"{case.case_id} · {case.store_id} · {REASON_LABELS[case.reason]} · {created}"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "_None_"


def _doc_links(doc_ids: list[str]) -> list[str]:
    docs = {doc.doc_id: doc for doc in load_help_docs()}
    return [
        f"[{docs[doc_id].title}]({docs[doc_id].source_url})"
        if doc_id in docs
        else f"{doc_id} (unknown doc)"
        for doc_id in doc_ids
    ]


def format_case(case: Case) -> str:
    """Lay out a full case as markdown, in the order a specialist reads it."""
    return "\n\n".join(
        [
            f"**Reason**\n\n{REASON_LABELS[case.reason]}",
            f"**What the merchant wants**\n\n{case.merchant_request}",
            f"**Issues found**\n\n{_bullets(case.issues_found)}",
            f"**Already tried**\n\n{_bullets(case.already_tried)}",
            f"**Suggested next step**\n\n{case.suggested_next_step}",
            f"**Help docs cited**\n\n{_bullets(_doc_links(case.cited_doc_ids))}",
        ]
    )
