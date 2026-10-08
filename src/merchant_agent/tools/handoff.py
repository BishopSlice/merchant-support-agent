"""Handoff cases for human specialists: create, save, list and fetch them."""

import logging
import re
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from merchant_agent.config import get_settings
from merchant_agent.models import AutomationSettings, Case
from merchant_agent.stores import StoreNotFoundError, load_store
from merchant_agent.tools import merchant_tools

_CASE_ID_PATTERN = re.compile(r"^CASE-[0-9A-Za-z-]+$")
# What the merchant is shown before the case goes to a specialist: everything but bookkeeping.
PREVIEW_EXCLUDE = {"case_id", "store_id", "created_at"}
logger = logging.getLogger(__name__)


def _account_issues(store_id: str) -> list[str]:
    """Each account issue's detail as the data states it, or [] if it can't be loaded."""
    response = merchant_tools.merchant_data.call("list_account_issues", account=store_id)
    try:
        return [i.get("detail") or i["title"] for i in response.get("accountIssues", [])]
    except (AttributeError, KeyError, TypeError):
        return []


def _automation(store_id: str) -> AutomationSettings | None:
    """The account's automatic improvements, or None if they can't be loaded."""
    response = merchant_tools.merchant_data.call("get_automatic_improvements", account=store_id)
    try:
        items = response["itemUpdates"]
        return AutomationSettings(
            price_updates=items["effectiveAllowPriceUpdates"],
            availability_updates=items["effectiveAllowAvailabilityUpdates"],
            image_improvements=response["imageImprovements"]["effectiveAllowAutomaticImageImprovements"],
            shipping_improvements=response["shippingImprovements"]["allowShippingImprovements"],
        )
    except (KeyError, TypeError, ValidationError):
        return None


def create_handoff_case(
    store_id: str,
    reason: str,
    issues_found: list[str],
    already_tried: list[str],
    merchant_request: str,
    suggested_next_step: str,
    cited_doc_ids: list[str],
    merchant_reasons: list[str] | None = None,
) -> dict:
    """Save a case for a human specialist.

    Returns the case id and a preview of exactly what the specialist will see, or an error
    saying what to fix. The account issues and automation state come from the store data.
    """
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
            merchant_reasons=merchant_reasons or [],
            suggested_next_step=suggested_next_step,
            cited_doc_ids=cited_doc_ids,
            account_issues=_account_issues(store_id),
            automation=_automation(store_id),
        )
    except ValidationError as error:
        problems = "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in error.errors())
        return {"status": "error", "message": f"Case not saved. {problems}"}

    save_case(case)
    preview = case.model_dump(mode="json", exclude=PREVIEW_EXCLUDE)
    return {"status": "created", "case_id": case.case_id, "preview": preview}


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
    """Load every saved case, newest first. Unreadable files are skipped with a warning."""
    cases = []
    for path in get_settings().cases_dir.glob("CASE-*.json"):
        try:
            cases.append(Case.model_validate_json(path.read_text()))
        except ValidationError as error:
            logger.warning("Skipping unreadable case file %s: %s", path.name, error)
    return sorted(cases, key=lambda case: case.created_at, reverse=True)


def clear_cases() -> int:
    """Delete every saved case (used to reset a demo) and return how many were removed."""
    paths = list(get_settings().cases_dir.glob("CASE-*.json"))
    for path in paths:
        path.unlink()
    return len(paths)
