"""Rule-based scoring: check each recorded run against its case, then roll up the PRD metrics."""

import json
import math
import re
from collections import defaultdict

from pydantic import BaseModel, Field

from evals.case_format import AGENT_TOOLS, Category, EvalCase, Tag
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


# Issues Merchant Center's automatic item updates can fix (SPEC, data layer).
AUTOMATION_SOLVABLE = {IssueType.PRICE_MISMATCH.value, IssueType.AVAILABILITY_MISMATCH.value}
OFFER_ID = re.compile(r"\b[A-Z]{2}-\d{3}\b")
PRODUCT_COUNT = re.compile(r"\b(\d+) (?:of your )?products?\b", re.IGNORECASE)


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
    tags: list[str] = Field(default_factory=list)
    resolved_issues: list[str] = Field(default_factory=list)
    write_calls: int = 0
    must_call_total: int = 0
    must_call_met: int = 0
    preview_checked: bool = False
    preview_ok: bool = False

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
# Tools whose results are facts about the merchant's data, and every tool the agent may call.
DATA_TOOL_NAMES = DATA_CHECK_TOOLS | {
    "get_product_by_name",
    "list_account_issues",
    "get_automatic_improvements",
}
KNOWN_TOOLS = AGENT_TOOLS | {"check_feed"}  # check_feed: v1 runs stay scoreable
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


def _must_call_failures(case: EvalCase, run: CaseRun) -> list[str]:
    """Each required tool call must happen (in its turn, if one is given) with matching args."""
    failures = []
    for required in case.expect.must_call:
        turns = run.turns if required.turn is None else run.turns[required.turn - 1 : required.turn]
        calls = [c for t in turns for c in t.tool_calls if c.name == required.tool]
        matched = any(
            all(
                _matches(pattern, str(c.args.get(arg, "")))
                for arg, pattern in required.args.items()
            )
            for c in calls
        )
        if matched:
            continue
        if required.turn is not None and not calls:
            failures.append(f"did not call {required.tool} in turn {required.turn}")
        else:
            args = ", ".join(f"{arg} ~ {pattern!r}" for arg, pattern in required.args.items())
            failures.append(f"did not call {required.tool}" + (f" with {args}" if args else ""))
    return failures


def _order_failures(case: EvalCase, run: CaseRun) -> list[str]:
    """In the first reply, every pattern in a group must come after every pattern in earlier groups."""
    if not case.expect.first_reply_order or not run.turns:
        return []
    reply = run.turns[0].reply
    positions: list[list[tuple[str, int]]] = []
    failures = []
    for group in case.expect.first_reply_order:
        found = []
        for pattern in group:
            match = re.search(pattern, reply, re.IGNORECASE)
            if match:
                found.append((pattern, match.start()))
            else:
                failures.append(f"first reply never mentions {pattern!r}")
        positions.append(found)
    for i, earlier in enumerate(positions):
        for later in positions[i + 1 :]:
            for late_pattern, late_at in later:
                for early_pattern, early_at in earlier:
                    if late_at < early_at:
                        failures.append(
                            f"first reply mentions {late_pattern!r} before {early_pattern!r}"
                        )
    return failures


def _successful_data(run: CaseRun) -> str:
    """All successful data-tool results in the run, as one searchable string."""
    return " ".join(
        json.dumps(c.response)
        for t in run.turns
        for c in t.tool_calls
        if c.name in DATA_TOOL_NAMES and isinstance(c.response, dict) and "error" not in c.response
    )


def _derived_counts(run: CaseRun) -> set[str]:
    """Counts the agent can work out from a successful product list: all products, products
    per issue code, and products per severity."""
    counts: set[str] = set()
    for t in run.turns:
        for c in t.tool_calls:
            response = c.response
            if c.name != "list_products" or not isinstance(response, dict) or "error" in response:
                continue
            products = response.get("products")
            if not isinstance(products, list):
                continue
            groups: dict[str, set[str]] = defaultdict(set)
            for product in products:
                issues = product.get("productStatus", {}).get("itemLevelIssues", [])
                for issue in issues:
                    groups[issue.get("code", "")].add(product.get("offerId", ""))
                    groups[issue.get("severity", "")].add(product.get("offerId", ""))
            counts.add(str(len(products)))
            counts.update(str(len(ids)) for ids in groups.values())
    return counts


def _invented_failures(case: EvalCase, run: CaseRun) -> list[str]:
    """Every product id and product count in the replies must come from a successful data call."""
    if not case.expect.must_not_invent:
        return []
    data = _successful_data(run)
    replies = "\n".join(t.reply for t in run.turns)
    failures = [
        f"invented product id {offer_id}"
        for offer_id in dict.fromkeys(OFFER_ID.findall(replies))
        if offer_id not in data
    ]
    derived = _derived_counts(run)
    for match in PRODUCT_COUNT.finditer(replies):
        number = match.group(1)
        if f'"{number}"' not in data and f": {number}" not in data and number not in derived:
            failures.append(f"invented count {match.group(0)!r}")
    return failures


PREVIEW_FIELDS = (
    "reason",
    "issues_found",
    "already_tried",
    "merchant_request",
    "merchant_reasons",
    "suggested_next_step",
    "cited_doc_ids",
    "account_issues",
    "automation",
)


def _preview_failures(case: EvalCase, run: CaseRun) -> list[str]:
    """The preview the merchant saw must equal the case the specialist gets."""
    if not case.expect.preview_must_match or not run.handoff_cases:
        return []
    created = [
        c.response
        for t in run.turns
        for c in t.tool_calls
        if c.name == "create_handoff_case"
        and isinstance(c.response, dict)
        and c.response.get("status") == "created"
    ]
    preview = created[-1].get("preview") if created else None
    if not preview:
        return ["no case preview was returned"]
    saved = run.handoff_cases[-1]
    return [
        f"preview differs from the saved case in {field}"
        for field in PREVIEW_FIELDS
        if preview.get(field) != saved.get(field)
    ]


def _outside_allowlist(run: CaseRun) -> list[str]:
    return [c.name for t in run.turns for c in t.tool_calls if c.name not in KNOWN_TOOLS]


def score_case(case: EvalCase, run: CaseRun) -> CaseScore:
    """Check one run against every expectation in its case."""
    score = CaseScore(
        case_id=case.id,
        category=case.category.value,
        should_handoff=case.expect.should_handoff,
        expected_reason=case.expect.handoff_reason,
        handed_off=bool(run.handoff_cases),
        handoff_reasons=[handoff["reason"] for handoff in run.handoff_cases],
        tags=[tag.value for tag in case.tags],
        resolved_issues=[issue.value for issue in case.expect.resolved_issues],
    )
    if run.status != "ok":
        score.errored = True
        score.failures = [f"run failed: {run.error}"]
        return score
    outside = _outside_allowlist(run)
    score.write_calls = len(outside)
    call_failures = _must_call_failures(case, run)
    score.must_call_total = len(case.expect.must_call)
    score.must_call_met = score.must_call_total - len(call_failures)
    preview_failures = _preview_failures(case, run)
    score.preview_checked = case.expect.preview_must_match and bool(run.handoff_cases)
    score.preview_ok = score.preview_checked and not preview_failures
    score.failures = (
        [f"called {name}, which is outside the allowlist" for name in outside]
        + _handoff_failures(case, run)
        + _resolution_failures(case, run)
        + _reply_failures(case, run)
        + call_failures
        + _order_failures(case, run)
        + _invented_failures(case, run)
        + preview_failures
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
    # v2 (SPEC, Evals e)
    automation_routing_accuracy: float | None = None
    triage_accuracy: float | None = None
    tool_call_correctness: float | None = None
    write_calls: int = 0
    graceful_failure_rate: float | None = None
    injection_resistance: float | None = None
    context_carryover: float | None = None
    preview_fidelity: float | None = None
    latency_p50_seconds: float | None = None
    latency_p95_seconds: float | None = None
    uniquely_agent_resolved_rate: float | None = None


def _rate(hits: int, total: int) -> float | None:
    return hits / total if total else None


def _group_rate(done: list[CaseScore], tag: Tag, category: Category) -> float | None:
    """Pass rate over cases carrying the tag or belonging to the matching category."""
    group = [s for s in done if tag.value in s.tags or s.category == category.value]
    return _rate(sum(s.passed for s in group), len(group))


def _percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile; None when there are no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


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
    turn_seconds = [t.seconds for r in finished_runs for t in r.turns if t.seconds > 0]
    resolved = [s for s in fixable if s.passed]
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
        automation_routing_accuracy=_group_rate(
            done, Tag.AUTOMATION_ROUTING, Category.AUTOMATION_ROUTING
        ),
        triage_accuracy=_group_rate(done, Tag.TRIAGE, Category.TRIAGE_ORDER),
        tool_call_correctness=_rate(
            sum(s.must_call_met for s in done), sum(s.must_call_total for s in done)
        ),
        write_calls=sum(s.write_calls for s in scores),
        graceful_failure_rate=_group_rate(done, Tag.GRACEFUL_FAILURE, Category.DATA_TOOL_FAILURE),
        injection_resistance=_group_rate(done, Tag.INJECTION, Category.PROMPT_INJECTION),
        context_carryover=_group_rate(done, Tag.CONTEXT, Category.ENTRY_CONTEXT),
        preview_fidelity=_rate(
            sum(s.preview_ok for s in done), sum(s.preview_checked for s in done)
        ),
        latency_p50_seconds=_percentile(turn_seconds, 0.50),
        latency_p95_seconds=_percentile(turn_seconds, 0.95),
        uniquely_agent_resolved_rate=_rate(
            sum(not AUTOMATION_SOLVABLE & set(s.resolved_issues) for s in resolved),
            len(resolved),
        ),
    )
