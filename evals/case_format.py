"""The eval case file format, and loading and checking every case in a folder.

Each case is one TOML file in evals/cases/ named after its id. See evals/README.md.
"""

import re
import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from merchant_agent.config import PROJECT_ROOT
from merchant_agent.demo import FIXABLE_ISSUE_TYPES
from merchant_agent.models import HandoffReason, IssueType
from merchant_agent.tools.help_search import load_help_docs

CASES_DIR = PROJECT_ROOT / "evals" / "cases"
EVAL_STORES_DIR = PROJECT_ROOT / "evals" / "stores"
DATA_STORES_DIR = PROJECT_ROOT / "data" / "stores"


class Category(StrEnum):
    """What kind of conversation a case tests. Used to group results."""

    EASY_FIX = "easy_fix"
    MULTI_ISSUE = "multi_issue"
    WARNINGS = "warnings"
    HANDOFF_SUSPENDED = "handoff_suspended"
    HANDOFF_APPEAL = "handoff_appeal"
    HANDOFF_HUMAN = "handoff_human"
    HANDOFF_FRUSTRATION = "handoff_frustration"
    HANDOFF_NO_DOC = "handoff_no_doc"
    NO_HANDOFF_DATA_FIX = "no_handoff_data_fix"
    ANGRY_MERCHANT = "angry_merchant"
    OFF_TOPIC = "off_topic"
    PROMPT_INJECTION = "prompt_injection"


class ScriptedTurn(BaseModel):
    """One merchant message, optionally after the merchant fixes an issue in their feed."""

    merchant: str
    fix: IssueType | None = None


class Expectations(BaseModel):
    """What a correct conversation looks like. Patterns are case-insensitive regexes."""

    should_handoff: bool
    handoff_reason: HandoffReason | None = None
    resolved_issues: list[IssueType] = Field(default_factory=list)
    must_mention: list[str] = Field(default_factory=list)
    must_not_say: list[str] = Field(default_factory=list)
    must_cite: list[str] = Field(default_factory=list)
    case_must_cite: list[str] = Field(default_factory=list)
    case_must_mention: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _handoff_fields_agree(self) -> "Expectations":
        if self.should_handoff and self.handoff_reason is None:
            raise ValueError("should_handoff = true needs a handoff_reason")
        if not self.should_handoff and self.handoff_reason is not None:
            raise ValueError("handoff_reason only makes sense when should_handoff = true")
        if not self.should_handoff and (self.case_must_cite or self.case_must_mention):
            raise ValueError("case_must_* checks need should_handoff = true")
        return self


class EvalCase(BaseModel):
    """One scripted conversation and what should happen in it."""

    id: str
    category: Category
    store: str
    description: str
    turns: list[ScriptedTurn] = Field(min_length=1)
    expect: Expectations


class CaseError(ValueError):
    """Raised with every problem found across a folder of case files."""


def known_stores() -> set[str]:
    """Store ids available to evals: the app's stores plus eval-only stores."""
    folders = [DATA_STORES_DIR, EVAL_STORES_DIR]
    return {p.name for folder in folders if folder.is_dir() for p in folder.iterdir() if p.is_dir()}


def _problems(case: EvalCase, file_name: str, stores: set[str], docs: set[str]) -> list[str]:
    """Checks a schema can't express: names that must exist and patterns that must compile."""
    problems = []
    if case.id != Path(file_name).stem:
        problems.append(f"id {case.id!r} does not match file name")
    if case.store not in stores:
        problems.append(f"unknown store {case.store!r}")
    for turn in case.turns:
        if turn.fix and turn.fix not in FIXABLE_ISSUE_TYPES:
            problems.append(f"fix {turn.fix.value!r} can't be simulated")
    for doc_id in case.expect.must_cite + case.expect.case_must_cite:
        if doc_id not in docs:
            problems.append(f"unknown help doc {doc_id!r}")
    patterns = case.expect.must_mention + case.expect.must_not_say + case.expect.case_must_mention
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as error:
            problems.append(f"bad pattern {pattern!r}: {error}")
    return problems


def load_cases(folder: Path = CASES_DIR) -> list[EvalCase]:
    """Load and check every case file in a folder, raising CaseError listing all problems."""
    stores = known_stores()
    docs = {doc.doc_id for doc in load_help_docs()}
    cases, problems = [], []
    for path in sorted(folder.glob("*.toml")):
        try:
            case = EvalCase(**tomllib.loads(path.read_text()))
        except (tomllib.TOMLDecodeError, ValidationError) as error:
            problems.append(f"{path.name}: {error}")
            continue
        problems += [f"{path.name}: {p}" for p in _problems(case, path.name, stores, docs)]
        cases.append(case)
    if problems:
        raise CaseError("\n".join(problems))
    return sorted(cases, key=lambda case: case.id)
