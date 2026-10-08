"""The eval command line: filters, saving, never overwriting, resuming. No model calls."""

import json

import pytest

from evals import run as eval_run
from evals.case_format import load_cases
from evals.records import CaseRun, ToolCallRecord, TurnRecord


@pytest.fixture
def results_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_run, "RESULTS_DIR", tmp_path)
    monkeypatch.setenv("MODEL_NAME", "gemini-3.6-flash")
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))  # eval traffic events
    return tmp_path


@pytest.fixture
def fake_agent(monkeypatch):
    """Replace the real case runner: every case 'passes' only the checks it can."""
    calls = []

    async def fake_run_case(case, price, runner_factory=None):
        calls.append(case.id)
        handoffs = []
        if case.expect.should_handoff:
            handoffs = [
                {
                    "reason": case.expect.handoff_reason.value,
                    "cited_doc_ids": [],
                    "issues_found": [],
                    "already_tried": [],
                    "merchant_request": "",
                    "suggested_next_step": "",
                }
            ]
        turn = TurnRecord(
            merchant=case.turns[0].merchant,
            reply="ok",
            tool_calls=[ToolCallRecord(name="check_feed", args={}, response={})],
        )
        return CaseRun(
            case_id=case.id,
            category=case.category.value,
            turns=[turn],
            handoff_cases=handoffs,
            cost_usd=0.002,
        )

    monkeypatch.setattr(eval_run, "run_case", fake_run_case)
    return calls


def test_select_cases_by_id_and_category():
    cases = load_cases()
    assert [c.id for c in eval_run.select_cases(cases, ["fix-price-mismatch"], [])] == [
        "fix-price-mismatch"
    ]
    off_topic = eval_run.select_cases(cases, [], ["off_topic"])
    assert {c.category.value for c in off_topic} == {"off_topic"} and len(off_topic) == 3
    with pytest.raises(SystemExit):
        eval_run.select_cases(cases, ["no-such-case"], [])


def test_a_run_saves_json_and_a_scorecard(results_dir, fake_agent):
    eval_run.main(["--category", "off_topic", "--no-grade"])
    [json_path] = results_dir.glob("*.json")
    assert json_path.name.endswith("-gemini-3.6-flash.json")
    saved = json.loads(json_path.read_text())
    assert set(saved["runs"]) == {"off-topic-billing", "off-topic-bids", "off-topic-shopify-steps"}
    assert saved["finished_at"]
    scorecard = json_path.with_suffix(".md").read_text()
    assert "Handoff precision" in scorecard and "off_topic" in scorecard


def test_runs_never_overwrite_an_existing_file(results_dir):
    from datetime import UTC, datetime

    now = datetime(2026, 10, 7, 12, 0, 0, tzinfo=UTC)
    path = eval_run.new_run_path("m", now)
    path.write_text("{}")
    with pytest.raises(FileExistsError):
        eval_run.new_run_path("m", now)


def test_resume_only_reruns_missing_or_errored_cases(results_dir, fake_agent):
    eval_run.main(["--category", "off_topic", "--no-grade"])
    [path] = results_dir.glob("*.json")
    saved = json.loads(path.read_text())
    saved["runs"]["off-topic-bids"]["status"] = "error"
    del saved["runs"]["off-topic-billing"]
    path.write_text(json.dumps(saved))
    fake_agent.clear()

    eval_run.main(["--resume", str(path), "--no-grade"])
    assert sorted(fake_agent) == ["off-topic-bids", "off-topic-billing"]
    assert len(list(results_dir.glob("*.json"))) == 1  # resumed in place
    assert json.loads(path.read_text())["runs"]["off-topic-bids"]["status"] == "ok"


def test_scorecard_lists_failures_and_prd_targets(results_dir, fake_agent):
    eval_run.main(["--case", "fix-price-mismatch", "--no-grade"])
    scorecard = next(results_dir.glob("*.md")).read_text()
    assert "fix-price-mismatch" in scorecard
    assert "did not mention" in scorecard  # the fake reply says only "ok"
    assert "80%" in scorecard  # resolution target from the PRD


def test_grading_feeds_the_scorecard(results_dir, fake_agent, monkeypatch):
    from evals import grader
    from evals.grader import CompletenessGrade, ReplyVerdict, WrongAdviceGrade
    from merchant_agent.chat import Usage

    def fake_generate(prompt, schema):
        usage = Usage(model_calls=1, input_tokens=2000, output_tokens=200)
        if schema is WrongAdviceGrade:
            verdict = ReplyVerdict(
                turn=1, verdict="unsupported", unsupported_claims=["x"], evidence="q"
            )
            return WrongAdviceGrade(replies=[verdict]), usage
        return CompletenessGrade(verdict="complete", evidence="q"), usage

    monkeypatch.setattr(grader, "gemini_generate", lambda model: fake_generate)
    eval_run.main(["--category", "handoff_human"])
    scorecard = next(results_dir.glob("*.md")).read_text()
    assert "| Wrong advice rate (AI graded) | 100% | under 5% | **missed** |" in scorecard
    assert "| Case completeness (AI graded) | 100% | 90% or higher | met |" in scorecard
    assert "Grading cost: $" in scorecard


def test_regrade_clears_old_grades_on_resume(results_dir, fake_agent, monkeypatch):
    from evals import grader

    calls = []

    def fake_generate(prompt, schema):
        from merchant_agent.chat import Usage

        calls.append(schema.__name__)
        if schema is grader.WrongAdviceGrade:
            return grader.WrongAdviceGrade(replies=[]), Usage()
        return grader.CompletenessGrade(verdict="complete", evidence="q"), Usage()

    monkeypatch.setattr(grader, "gemini_generate", lambda model: fake_generate)
    eval_run.main(["--case", "human-asks-at-start"])
    [path] = results_dir.glob("*.json")
    calls.clear()
    eval_run.main(["--resume", str(path)])
    assert calls == []  # already graded
    eval_run.main(["--resume", str(path), "--regrade"])
    assert calls == ["WrongAdviceGrade", "CompletenessGrade"]


def test_scorecard_reports_cases_the_grader_could_not_grade(results_dir, fake_agent, monkeypatch):
    from evals import grader

    def blocked(prompt, schema):
        raise grader.GradingFailed("no valid WrongAdviceGrade after 3 attempts")

    monkeypatch.setattr(grader, "gemini_generate", lambda model: blocked)
    eval_run.main(["--case", "human-asks-at-start"])
    scorecard = next(results_dir.glob("*.md")).read_text()
    assert "Grading failures: 1 (human-asks-at-start), left out of the AI-graded rates" in scorecard


def test_heldout_set_runs_from_its_own_folder_and_is_named_in_the_file(results_dir, fake_agent):
    eval_run.main(["--set", "heldout", "--no-grade"])
    [path] = results_dir.glob("*.json")
    assert path.name.endswith("-gemini-3.6-flash-heldout.json")
    assert fake_agent and all(case_id.startswith("heldout-") for case_id in fake_agent)


def test_parallel_runs_save_every_case_in_the_same_format(results_dir, fake_agent, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    # Worker processes can't see the fake agent, so the test runs the workers as threads.
    monkeypatch.setattr(eval_run, "CaseExecutor", ThreadPoolExecutor)
    eval_run.main(["--category", "off_topic", "--no-grade", "--workers", "3"])
    [json_path] = results_dir.glob("*.json")
    saved = json.loads(json_path.read_text())
    assert set(saved["runs"]) == {"off-topic-billing", "off-topic-bids", "off-topic-shopify-steps"}
    assert saved["workers"] == 3
    assert sorted(fake_agent) == sorted(saved["runs"])


def test_grading_runs_in_parallel_and_saves_every_grade():
    from test_web_api import fake_generate

    from evals.grader import grade_run
    from evals.records import CaseRun, TurnRecord
    from merchant_agent.config import MODEL_PRICES

    run_file = eval_run.RunFile(
        model="m",
        started_at="2026-10-08T00:00:00Z",
        price=MODEL_PRICES["gemini-3.6-flash"],
        runs={
            f"c{i}": CaseRun(
                case_id=f"c{i}", category="easy_fix", turns=[TurnRecord(merchant="m", reply="r")]
            )
            for i in range(6)
        },
    )
    saves = []
    grade_run(run_file, save=lambda: saves.append(1), generate=fake_generate([]), workers=4)
    assert set(run_file.grades) == {f"c{i}" for i in range(6)} and len(saves) == 6


def test_the_default_is_parallel_outside_tests(monkeypatch):
    monkeypatch.delenv("EVAL_WORKERS", raising=False)
    assert eval_run.default_workers() == 5
