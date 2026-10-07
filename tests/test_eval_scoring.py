"""Scorers are tested with hand-built transcripts, so no model is called."""

from evals.case_format import EvalCase
from evals.records import CaseRun, ToolCallRecord, TurnRecord
from evals.scoring import score_case, summarize

SHIPPING_URL = "https://support.google.com/merchants/answer/6324484"


def make_case(**expect) -> EvalCase:
    return EvalCase(
        id="c1",
        category="easy_fix",
        store="shipping-only",
        description="test",
        turns=[{"merchant": "What's wrong?"}, {"merchant": "Fixed it", "fix": "missing_shipping"}],
        expect={"should_handoff": False, **expect},
    )


def feed_check(*issue_types: str) -> ToolCallRecord:
    groups = [{"issue_type": t, "count": 1} for t in issue_types]
    return ToolCallRecord(name="check_feed", args={}, response={"issue_groups": groups})


def handoff(reason: str, **fields) -> dict:
    return {
        "reason": reason,
        "cited_doc_ids": [],
        "issues_found": [],
        "already_tried": [],
        "merchant_request": "",
        "suggested_next_step": "",
        **fields,
    }


def make_run(replies: list[str], calls: list[list[ToolCallRecord]], cases=()) -> CaseRun:
    turns = [
        TurnRecord(merchant="m", reply=reply, tool_calls=turn_calls)
        for reply, turn_calls in zip(replies, calls, strict=True)
    ]
    turns[1].fix = "missing_shipping"
    return CaseRun(case_id="c1", category="easy_fix", turns=turns, handoff_cases=list(cases))


GOOD_RUN = make_run(
    ["Your shipping is missing, see [Shipping costs](" + SHIPPING_URL + ").", "All fixed now."],
    [[feed_check("missing_shipping")], [feed_check()]],
)


def test_a_good_run_passes_every_check():
    score = score_case(
        make_case(
            resolved_issues=["missing_shipping"],
            must_cite=["shipping"],
            must_mention=["shipping"],
            must_not_say=[r"CASE-\d"],
        ),
        GOOD_RUN,
    )
    assert score.passed, score.failures
    assert not score.handed_off


def test_no_recheck_after_the_fix_fails():
    run = make_run(
        ["Shipping is missing.", "Great, all fixed."], [[feed_check("missing_shipping")], []]
    )
    score = score_case(make_case(resolved_issues=["missing_shipping"]), run)
    assert not score.passed
    assert "did not re-run check_feed after the last fix" in score.failures


def test_issue_still_present_in_the_last_check_fails():
    run = make_run(["x", "y"], [[feed_check("missing_shipping")], [feed_check("missing_shipping")]])
    score = score_case(make_case(resolved_issues=["missing_shipping"]), run)
    assert "missing_shipping still flagged in the last feed check" in score.failures


def test_mention_checks_are_case_insensitive_regexes_over_all_replies():
    case = make_case(must_mention=["FIXED", r"shipping (cost|rate)s? (was|were) added"])
    assert score_case(case, GOOD_RUN).passed is False  # second pattern never said
    case = make_case(must_mention=["FIXED", "shipping"], must_not_say=["shopify"])
    assert score_case(case, GOOD_RUN).passed


def test_forbidden_text_fails_and_quotes_the_pattern():
    score = score_case(make_case(must_not_say=["all fixed"]), GOOD_RUN)
    assert "said forbidden text matching 'all fixed'" in score.failures


def test_missing_citation_fails():
    score = score_case(make_case(must_cite=["price-mismatch"]), GOOD_RUN)
    assert "did not cite price-mismatch" in score.failures


def test_unexpected_handoff_fails():
    run = GOOD_RUN.model_copy(update={"handoff_cases": [handoff("policy_appeal")]})
    score = score_case(make_case(), run)
    assert score.handed_off
    assert "handed off but should not have" in score.failures


def test_expected_handoff_checks_reason_and_case_contents():
    case = make_case(
        should_handoff=True,
        handoff_reason="policy_appeal",
        case_must_cite=["cbd-unapproved-substances"],
        case_must_mention=["candle"],
    )
    good = GOOD_RUN.model_copy(
        update={
            "handoff_cases": [
                handoff(
                    "policy_appeal",
                    cited_doc_ids=["cbd-unapproved-substances"],
                    merchant_request="Appeal the candle",
                )
            ]
        }
    )
    assert score_case(case, good).passed

    wrong = GOOD_RUN.model_copy(update={"handoff_cases": [handoff("merchant_requested_human")]})
    failures = score_case(case, wrong).failures
    assert "handoff reason was merchant_requested_human, expected policy_appeal" in failures
    assert "case did not cite cbd-unapproved-substances" in failures
    assert "case text does not match 'candle'" in failures


def test_missing_handoff_fails():
    case = make_case(should_handoff=True, handoff_reason="account_suspended")
    assert (
        "should have handed off (account_suspended) but did not"
        in score_case(case, GOOD_RUN).failures
    )


def test_errored_run_fails_with_its_error():
    run = CaseRun(case_id="c1", category="easy_fix", status="error", error="429 quota")
    score = score_case(make_case(), run)
    assert not score.passed and score.errored
    assert score.failures == ["run failed: 429 quota"]


def test_summary_metrics():
    def case(case_id, category, should_handoff, reason=None):
        expect = {"should_handoff": should_handoff}
        if reason:
            expect["handoff_reason"] = reason
        return EvalCase(
            id=case_id,
            category=category,
            store="sample-store",
            description="d",
            turns=[{"merchant": "hi"}],
            expect=expect,
        )

    def run(case_id, category, handoff_reason=None, cost=0.01):
        cases = [handoff(handoff_reason)] if handoff_reason else []
        return CaseRun(
            case_id=case_id,
            category=category,
            cost_usd=cost,
            turns=[TurnRecord(merchant="hi", reply="ok")],
            handoff_cases=cases,
        )

    pairs = [
        # fixable, resolved
        (case("a", "easy_fix", False), run("a", "easy_fix")),
        # fixable, wrongly handed off: not resolved, false positive
        (case("b", "easy_fix", False), run("b", "easy_fix", "merchant_requested_human")),
        # needed handoff, got it with the right reason
        (
            case("c", "handoff_appeal", True, "policy_appeal"),
            run("c", "handoff_appeal", "policy_appeal"),
        ),
        # needed handoff, got it with the wrong reason
        (
            case("d", "handoff_human", True, "merchant_requested_human"),
            run("d", "handoff_human", "no_supporting_doc"),
        ),
        # needed handoff, missed
        (case("e", "handoff_no_doc", True, "no_supporting_doc"), run("e", "handoff_no_doc")),
        # off topic: not a fixable case, not a handoff
        (case("f", "off_topic", False), run("f", "off_topic")),
    ]
    summary = summarize([score_case(c, r) for c, r in pairs], [r for _, r in pairs])

    assert summary.resolution_rate == 0.5  # a of {a, b}
    assert summary.handoff_precision == 2 / 3  # c, d of {b, c, d}
    assert summary.handoff_recall == 2 / 3  # c, d of {c, d, e}
    assert summary.handoff_reason_accuracy == 0.5  # c of {c, d}
    assert summary.cases == 6 and summary.errors == 0
    assert round(summary.cost_per_case_usd, 6) == 0.01
    assert summary.pass_rate_by_category["easy_fix"] == 0.5
