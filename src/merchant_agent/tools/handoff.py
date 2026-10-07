"""Handoff cases for human specialists: create, save, list and fetch them."""

import re
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from merchant_agent.config import get_settings
from merchant_agent.models import Case
from merchant_agent.stores import StoreNotFoundError, load_store

_CASE_ID_PATTERN = re.compile(r"^CASE-[0-9A-Za-z-]+$")


def create_handoff_case(
    store_id: str,
    reason: str,
    issues_found: list[str],
    already_tried: list[str],
    merchant_request: str,
    suggested_next_step: str,
    cited_doc_ids: list[str],
) -> dict:
    """Save a case for a human specialist and return its id, or an error saying what to fix."""
    try:
        load_store(store_id)
    except StoreNotFoundError as error:
        return {"status": "error", "message": str(error)}

    now = datetime.now(UTC)
    try:
        case = Case(
            case_id=f"CASE-{now:%Y%m%d-%H%M%S}-{uuid4().hex[:6]}",
            store_id=store_id,
            created_at=now,
            reason=reason,
            issues_found=issues_found,
            already_tried=already_tried,
            merchant_request=merchant_request,
            suggested_next_step=suggested_next_step,
            cited_doc_ids=cited_doc_ids,
        )
    except ValidationError as error:
        problems = "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in error.errors())
        return {"status": "error", "message": f"Case not saved. {problems}"}

    save_case(case)
    return {"status": "created", "case_id": case.case_id}


def save_case(case: Case) -> None:
    """Write a case to runtime/cases/<case_id>.json."""
    folder = get_settings().cases_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{case.case_id}.json").write_text(case.model_dump_json(indent=2))


def get_case(case_id: str) -> Case | None:
    """Load one case by id, or return None if there is no such case."""
    if not _CASE_ID_PATTERN.match(case_id):
        return None
    path = get_settings().cases_dir / f"{case_id}.json"
    if not path.is_file():
        return None
    return Case.model_validate_json(path.read_text())


def list_cases() -> list[Case]:
    """Load every saved case, newest first."""
    folder = get_settings().cases_dir
    cases = [Case.model_validate_json(path.read_text()) for path in folder.glob("CASE-*.json")]
    return sorted(cases, key=lambda case: case.created_at, reverse=True)
