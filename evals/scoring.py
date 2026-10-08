"""Rule-based scoring: check each recorded run against its case, then roll up the PRD metrics."""

import json
import re
from collections import defaultdict

from pydantic import BaseModel, Field

from evals.case_format import Category, EvalCase
from evals.records import CaseRun, ToolCallRecord
from merchant_agent.models import IssueType
from merchant_agent.tools.help_search import load_help_docs

# Cases where the merchant's problem is a data fix they can make: the denominator for the
# PRD's resolution rate. Off-topic and injection cases test refusals, not fixes.
FIXABLE_CATEGORIES = {
    Category.EASY_FIX,
    Category.MULTI_ISSUE,
    Category.WARNINGS,
    Category.NO_HANDOFF_DATA_FIX,
    Category.ANGRY_MERCHANT,
}


class CaseScore(BaseModel):
    """How one run did against its case's expectations."""

    case_id: str
    category: str
    should_handoff: bool
    expected_reason: str | None = None
    handed_off: bool = False
    handoff_reasons: list[str] = Field(default_factory=list)
    errored: bool = False
    failures: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def fixable(self) -> bool:
        return not self.should_handoff and self.category in FIXABLE_CATEGORIES


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE | re.DOTALL) is not None


def _last_fix_index(run: CaseRun) -> int | None:
    fixes = [i for i, turn in enumerate(run.turns) if turn.fix]
    return fixes[-1] if fixes else None


def _resolution_failures(case: EvalCase, run: CaseRun) -> list[str]:
    """After the last fix the agent must re-check, and the expected issues must be gone."""
    if not case.expect.resolved_issues:
        return []
    last_fix = _last_fix_index(run)
    calls = [
        call
        for turn in run.turns[last_fix if last_fix is not None else 0 :]
        for call in turn.tool_calls
        if call.name in DATA_CHECK_TOOLS and isinstance(call.response, dict)
    ]
    if not calls:
        return ["did not re-run a data check after the last fix"]
    flagged: dict[str, bool] = {}  # issue code -> still present, per the latest check showing it
    for call in calls:
        flagged.update(_issues_seen(call))
    failures = []
    for issue in case.expect.resolved_issues:
        if issue.value not in flagged:
            failures.append(f"did not re-check {issue.value} after the last fix")
        elif flagged[issue.value]:
            failures.append(f"{issue.value} still flagged in the last data check")
    return failures


# Tools whose results show which issues remain: v1's check_feed, and v2's MCP-shaped tools.
DATA_CHECK_TOOLS = {"check_feed", "list_aggregate_product_statuses", "list_products"}
ALL_ISSUE_CODES = {issue.value for issue in IssueType}


def _issues_seen(call: ToolCallRecord) -> dict[str, bool]:
    """Which issue codes one data call shows as present or absent.

    v1's check_feed and the aggregate statuses list every remaining issue, so any code they
    don't mention is gone. A product list filtered to one issue code only speaks for that code.
    """
    response = call.response
    if call.name == "check_feed":
        present = {group["issue_type"] for group in response.get("issue_groups", [])}
    elif call.name == "list_aggregate_product_statuses":
        statuses = response.get("aggregateProductStatuses", [])
        present = {i["code"] for status in statuses for i in status.get("itemLevelIssues", [])}
    else:
        present = {
            i["code"]
            for product in response.get("products", [])
            for i in product.get("productStatus", {}).get("itemLevelIssues", [])
        }
        if code := call.args.get("issue_code"):
            return {code: code in present}
    if "error" in response:
        return {}
    return {code: code in present for code in ALL_ISSUE_CODES | present}


def _reply_failures(case: EvalCase, run: CaseRun) -> list[str]:
    replies = "\n\n".join(turn.reply for turn in run.turns)
    urls = {doc.doc_id: doc.source_url for doc in load_help_docs()}
    failures = [
        f"did not mention {p!r}" for p in case.expect.must_mention if not _matches(p, replies)
    ]
    failures += [
        f"said forbidden text matching {p!r}"
        for p in case.expect.must_not_say
        if _matches(p, replies)
    ]
    failures += [f"did not cite {d}" for d in case.expect.must_cite if urls[d] not in replies]
    return failures


def _handoff_failures(case: EvalCase, run: CaseRun) -> list[str]:
    expect = case.expect
    if not expect.should_handoff:
        return ["handed off but should not have"] if run.handoff_cases else []
    if not run.handoff_cases:
        return [f"should have handed off ({expect.handoff_reason.value}) but did not"]
    handoff = run.handoff_cases[-1]
    failures = []
    if handoff["reason"] != expect.handoff_reason.value:
        failures.append(
            f"handoff reason was {handoff['reason']}, expected {expect.handoff_reason.value}"
        )
    failures += [
        f"case did not cite {d}" for d in expect.case_must_cite if d not in handoff["cited_doc_ids"]
    ]
    case_text = json.dumps(handoff)
    failures += [
        f"case text does not match {p!r}"
        for p in expect.case_must_mention
        if not _matches(p, case_text)
    ]
    return failures


def score_case(case: EvalCase, run: CaseRun) -> CaseScore:
    """Check one run against every expectation in its case."""
    score = CaseScore(
        case_id=case.id,
        category=case.category.value,
        should_handoff=case.expect.should_handoff,
        expected_reason=case.expect.handoff_reason,
        handed_off=bool(run.handoff_cases),
        handoff_reasons=[handoff["reason"] for handoff in run.handoff_cases],
    )
    if run.status != "ok":
        score.errored = True
        score.failures = [f"run failed: {run.error}"]
        return score
    score.failures = (
        _handoff_failures(case, run) + _resolution_failures(case, run) + _reply_failures(case, run)
    )
    return score


class Summary(BaseModel):
    """The rule-based PRD metrics for one eval run. Rates are None when they have no cases."""

    cases: int
    errors: int
    pass_rate: float | None
    resolution_rate: float | None
    handoff_precision: float | None
    handoff_recall: float | None
    handoff_reason_accuracy: float | None
    cost_per_case_usd: float | None
    total_cost_usd: float
    pass_rate_by_category: dict[str, float]


def _rate(hits: int, total: int) -> float | None:
    return hits / total if total else None


def summarize(scores: list[CaseScore], runs: list[CaseRun]) -> Summary:
    """Roll case scores up into the PRD's rule-based metrics. Errored runs are left out."""
    done = [s for s in scores if not s.errored]
    fixable = [s for s in done if s.fixable]
    handed_off = [s for s in done if s.handed_off]
    needed = [s for s in done if s.should_handoff]
    caught = [s for s in needed if s.handed_off]
    by_category: dict[str, list[CaseScore]] = defaultdict(list)
    for score in done:
        by_category[score.category].append(score)
    finished_runs = [run for run in runs if run.status == "ok"]
    total_cost = sum(run.cost_usd for run in runs)
    return Summary(
        cases=len(scores),
        errors=len(scores) - len(done),
        pass_rate=_rate(sum(s.passed for s in done), len(done)),
        resolution_rate=_rate(sum(s.passed for s in fixable), len(fixable)),
        handoff_precision=_rate(sum(s.should_handoff for s in handed_off), len(handed_off)),
        handoff_recall=_rate(len(caught), len(needed)),
        handoff_reason_accuracy=_rate(
            sum(s.expected_reason in s.handoff_reasons for s in caught), len(caught)
        ),
        cost_per_case_usd=_rate(sum(r.cost_usd for r in finished_runs), len(finished_runs)),
        total_cost_usd=total_cost,
        pass_rate_by_category={
            category: sum(s.passed for s in group) / len(group)
            for category, group in sorted(by_category.items())
        },
    )
