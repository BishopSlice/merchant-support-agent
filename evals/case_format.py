"""The eval case file format, and loading and checking every case in a folder.

Each case is one TOML file in evals/cases/ named after its id. See evals/README.md.
"""

import re
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from merchant_agent.config import PROJECT_ROOT
from merchant_agent.data import ALLOWED_TOOLS
from merchant_agent.demo import FIXABLE_ISSUE_TYPES
from merchant_agent.models import HandoffReason, IssueType
from merchant_agent.tools.help_search import load_help_docs

CASES_DIR = PROJECT_ROOT / "evals" / "cases"
# Held-out cases, written before Task 11's prompt changes, to check fixes don't just fit
# the main set.
HELDOUT_DIR = PROJECT_ROOT / "evals" / "cases_heldout"
# v2 held-out cases, written and committed before any v2 prompt change (SPEC, Evals c).
HELDOUT_V2_DIR = PROJECT_ROOT / "evals" / "cases_heldout_v2"
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
    # v2
    AUTOMATION_ROUTING = "automation_routing"
    TRIAGE_ORDER = "triage_order"
    DATA_TOOL_FAILURE = "data_tool_failure"
    ENTRY_CONTEXT = "entry_context"
    CASE_PREVIEW = "case_preview"


class Tag(StrEnum):
    """Metrics a case counts towards, beyond its category (SPEC, Evals e)."""

    AUTOMATION_ROUTING = "automation_routing"
    TRIAGE = "triage"
    TOOL_CALLS = "tool_calls"
    GRACEFUL_FAILURE = "graceful_failure"
    INJECTION = "injection"
    CONTEXT = "context"
    PREVIEW = "preview"


class EntryContext(BaseModel):
    """The issue row the side panel was opened from."""

    product: str
    issue_code: IssueType


class DataFailure(BaseModel):
    """Make one data tool fail in this case, to test graceful failure."""

    tool: str
    kind: Literal["quota", "timeout", "empty", "malformed", "error"]


class MustCall(BaseModel):
    """A tool call the agent must make: arguments are regexes, turn (1-based) is optional."""

    tool: str
    args: dict[str, str] = Field(default_factory=dict)
    turn: int | None = None


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
    # v2
    must_call: list[MustCall] = Field(default_factory=list)
    first_reply_order: list[list[str]] = Field(default_factory=list)
    must_not_invent: bool = False
    preview_must_match: bool = False

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
    tags: list[Tag] = Field(default_factory=list)
    entry_context: EntryContext | None = None
    data_failure: DataFailure | None = None


# Every tool the agent may call: the MCP read tools plus our own.
AGENT_TOOLS = ALLOWED_TOOLS | {"search_help_docs", "create_handoff_case"}


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
    for call in case.expect.must_call:
        if call.tool not in AGENT_TOOLS:
            problems.append(f"must_call tool {call.tool!r} is not an allowed tool")
    if case.data_failure and case.data_failure.tool not in ALLOWED_TOOLS:
        problems.append(f"data_failure tool {case.data_failure.tool!r} is not an allowed tool")
    patterns = case.expect.must_mention + case.expect.must_not_say + case.expect.case_must_mention
    patterns += [p for call in case.expect.must_call for p in call.args.values()]
    patterns += [p for group in case.expect.first_reply_order for p in group]
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
