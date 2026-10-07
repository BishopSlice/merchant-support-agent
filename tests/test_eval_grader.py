"""Grader tests swap the model for a fake, so no API calls are made."""

from evals.grader import (
    CaseGrade,
    CompletenessGrade,
    ReplyVerdict,
    WrongAdviceGrade,
    completeness_prompt,
    grade_case,
    grade_run,
    summarize_grades,
    wrong_advice_prompt,
)
from evals.records import CaseRun, ToolCallRecord, TurnRecord
from merchant_agent.chat import Usage

SEARCH = ToolCallRecord(
    name="search_help_docs",
    args={"query": "missing_shipping"},
    response={"results": [{"doc_id": "shipping", "title": "Shipping costs"}]},
)
FEED = ToolCallRecord(name="check_feed", args={}, response={"disapproved_products": 1})


def make_run(handoff: bool = False) -> CaseRun:
    turns = [
        TurnRecord(
            merchant="What's wrong?",
            reply="Shipping is missing on HG-030.",
            tool_calls=[FEED, SEARCH],
        ),
        TurnRecord(merchant="It's just a candle, I want to appeal.", reply="I've passed this on."),
    ]
    cases = [{"reason": "policy_appeal", "merchant_request": "Appeal"}] if handoff else []
    return CaseRun(case_id="c1", category="handoff_appeal", turns=turns, handoff_cases=cases)


class FakeModel:
    """Returns canned grades and records the prompts it was given."""

    def __init__(self, unsupported_turns=(), complete=True):
        self.prompts: list[str] = []
        self.unsupported_turns = set(unsupported_turns)
        self.complete = complete

    def __call__(self, prompt, schema):
        self.prompts.append(prompt)
        usage = Usage(model_calls=1, input_tokens=1000, output_tokens=100)
        if schema is WrongAdviceGrade:
            replies = [
                ReplyVerdict(
                    turn=n,
                    verdict="unsupported" if n in self.unsupported_turns else "supported",
                    unsupported_claims=["made up"] if n in self.unsupported_turns else [],
                    evidence=f"quote {n}",
                )
                for n in (1, 2)
            ]
            return WrongAdviceGrade(replies=replies), usage
        return CompletenessGrade(
            verdict="complete" if self.complete else "incomplete",
            missing=[] if self.complete else ["Why do they disagree?"],
            evidence="quote",
        ), usage


def test_wrong_advice_prompt_has_rubric_docs_feed_data_and_numbered_replies():
    prompt = wrong_advice_prompt(make_run())
    assert "# Rubric: wrong advice" in prompt
    assert "In the United States and many other countries" in prompt  # full shipping doc text
    assert "https://support.google.com/merchants/answer/6324484" in prompt
    assert '"disapproved_products": 1' in prompt
    assert "Agent reply 1:" in prompt and "Agent reply 2:" in prompt


def test_wrong_advice_prompt_says_when_no_doc_was_retrieved():
    run = make_run()
    for turn in run.turns:
        turn.tool_calls = []
    assert "The agent retrieved no help docs" in wrong_advice_prompt(run)


def test_completeness_prompt_includes_the_case():
    prompt = completeness_prompt(make_run(handoff=True))
    assert "# Rubric: case completeness" in prompt
    assert '"merchant_request": "Appeal"' in prompt
    assert "It's just a candle" in prompt


def test_grade_case_only_grades_completeness_when_there_was_a_handoff():
    model = FakeModel()
    assert grade_case(make_run(), model, price=None).completeness is None
    assert len(model.prompts) == 1
    grade = grade_case(make_run(handoff=True), model, price=None)
    assert grade.completeness.verdict == "complete"
    assert grade.usage.model_calls == 2


def test_summary_rates():
    grades = {
        "a": grade_case(make_run(handoff=True), FakeModel(unsupported_turns=[2]), price=None),
        "b": grade_case(make_run(handoff=True), FakeModel(complete=False), price=None),
        "c": grade_case(make_run(), FakeModel(), price=None),
    }
    summary = summarize_grades(grades)
    assert summary["wrong_advice_rate"] == 1 / 6  # one unsupported reply of six
    assert summary["case_completeness"] == 0.5  # a complete, b incomplete


def test_summary_is_empty_without_grades():
    assert summarize_grades({}) == {"wrong_advice_rate": None, "case_completeness": None}


def test_grade_run_skips_errored_and_already_graded_runs():
    from evals.run import RunFile
    from merchant_agent.config import MODEL_PRICES

    errored = CaseRun(case_id="e", category="easy_fix", status="error", error="x")
    run_file = RunFile(
        model="m",
        started_at="2026-10-07T00:00:00Z",
        price=MODEL_PRICES["gemini-3.6-flash"],
        runs={"a": make_run(), "b": make_run(), "e": errored},
    )
    run_file.grades["b"] = CaseGrade()
    saves = []
    model = FakeModel()
    grade_run(run_file, generate=model, save=lambda: saves.append(1))
    assert set(run_file.grades) == {"a", "b"}
    assert len(model.prompts) == 1 and len(saves) == 1
    assert run_file.grades["a"].cost_usd > 0


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = None


def test_gemini_generate_retries_empty_or_invalid_responses(monkeypatch):
    from evals import grader

    responses = iter(
        [FakeResponse(None), FakeResponse("{not json"), FakeResponse('{"replies": []}')]
    )

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = self

        def generate_content(self, **kwargs):
            return next(responses)

    monkeypatch.setattr(grader.genai, "Client", FakeClient)
    parsed, _ = grader.gemini_generate("m")("prompt", WrongAdviceGrade)
    assert parsed.replies == []


def test_gemini_generate_gives_up_with_a_grading_error(monkeypatch):
    import pytest

    from evals import grader

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = self

        def generate_content(self, **kwargs):
            return FakeResponse(None)

    monkeypatch.setattr(grader.genai, "Client", FakeClient)
    with pytest.raises(grader.GradingFailed):
        grader.gemini_generate("m")("prompt", WrongAdviceGrade)


def test_a_failed_grade_is_recorded_skipped_in_rates_and_retried_later():
    from evals.grader import GradingFailed
    from evals.run import RunFile
    from merchant_agent.config import MODEL_PRICES

    run_file = RunFile(
        model="m",
        started_at="2026-10-07T00:00:00Z",
        price=MODEL_PRICES["gemini-3.6-flash"],
        runs={"a": make_run(), "b": make_run()},
    )
    good = FakeModel()

    def flaky(prompt, schema):
        if "b-marker" in prompt:
            raise GradingFailed("empty response")
        return good(prompt, schema)

    run_file.runs["b"].turns[0].merchant = "b-marker"
    grade_run(run_file, generate=flaky, save=lambda: None)
    assert run_file.grades["b"].error == "empty response"
    assert summarize_grades(run_file.grades)["wrong_advice_rate"] == 0.0  # only "a" counted

    grade_run(run_file, generate=good, save=lambda: None)
    assert run_file.grades["b"].error == ""
