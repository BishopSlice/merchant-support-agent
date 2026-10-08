"""Hand-check sheet and run comparison, built from hand-made run files."""

from evals.compare import compare_runs
from evals.grader import CaseGrade, CompletenessGrade, ReplyVerdict, WrongAdviceGrade
from evals.hand_check import pick_items, render_hand_check
from evals.records import CaseRun, TurnRecord
from evals.run import RunFile
from merchant_agent.config import MODEL_PRICES


def run_file(grades=None, runs=None) -> RunFile:
    return RunFile(
        model="m",
        started_at="2026-10-07T00:00:00Z",
        price=MODEL_PRICES["gemini-3.6-flash"],
        runs=runs or {},
        grades=grades or {},
    )


def advice(*verdicts):
    return WrongAdviceGrade(
        replies=[
            ReplyVerdict(
                turn=i,
                verdict=v,
                unsupported_claims=["claim"] if v == "unsupported" else [],
                evidence=f"evidence | {i}",
            )
            for i, v in enumerate(verdicts, start=1)
        ]
    )


def make_run(case_id, replies=("Reply one", "Reply two")):
    return CaseRun(
        case_id=case_id,
        category="c",
        turns=[TurnRecord(merchant="m", reply=r) for r in replies],
        handoff_cases=[{"reason": "policy_appeal", "merchant_request": "Appeal"}],
    )


def no_handoff(run: CaseRun) -> CaseRun:
    return run.model_copy(update={"handoff_cases": []})


def test_pick_items_mixes_passes_and_fails_and_skips_no_advice():
    grades = {
        f"case-{n}": CaseGrade(
            wrong_advice=advice("supported", "unsupported", "no_advice"),
            completeness=CompletenessGrade(
                verdict="incomplete" if n % 2 else "complete",
                missing=["Why?"] if n % 2 else [],
                evidence="e",
            ),
        )
        for n in range(8)
    }
    items = pick_items(run_file(grades, {k: make_run(k, ("a", "b", "c")) for k in grades}), 10)
    assert len(items) == 10
    verdicts = {item.verdict for item in items}
    assert {"supported", "unsupported", "complete", "incomplete"} <= verdicts
    assert "no_advice" not in verdicts


def test_hand_check_sheet_has_a_blank_agree_column_and_safe_cells():
    grades = {"c1": CaseGrade(wrong_advice=advice("unsupported"))}
    sheet = render_hand_check(
        run_file(grades, {"c1": make_run("c1", ("Line one\nline two",))}), "run-x", 10
    )
    assert "| Agree? |" in sheet
    assert "Line one line two" in sheet  # newlines flattened
    assert "evidence \\| 1" in sheet  # pipes escaped
    assert sheet.rstrip().endswith("|")


def test_compare_runs_reports_metric_changes_and_flipped_cases():
    from evals.case_format import load_cases

    cases = load_cases()
    first = run_file(
        runs={
            "off-topic-bids": no_handoff(
                make_run("off-topic-bids", ("I can only help with products",))
            ),
            "angry-wants-human": make_run("angry-wants-human"),
        }
    )
    second = run_file(
        runs={
            "off-topic-bids": no_handoff(make_run("off-topic-bids", ("Bid $2 per click",))),
            "angry-wants-human": make_run("angry-wants-human"),
        }
    )
    report = compare_runs(first, "run-1", second, "run-2", cases)
    assert "| Handoff recall |" in report
    assert "off-topic-bids: passed in run-1, failed in run-2" in report


def test_compare_refuses_runs_from_different_case_sets(tmp_path, monkeypatch):
    import pytest

    from evals import compare

    main_run, heldout_run = run_file(), run_file()
    heldout_run.case_set = "heldout"
    paths = []
    for name, rf in [("a", main_run), ("b", heldout_run)]:
        path = tmp_path / f"{name}.json"
        path.write_text(rf.model_dump_json())
        paths.append(str(path))
    monkeypatch.setattr("sys.argv", ["compare", *paths])
    with pytest.raises(SystemExit, match="different case sets"):
        compare.main()


def test_v2_hand_check_draws_from_several_runs_and_prefers_v2_categories():
    from evals.hand_check import pick_from_runs

    old = make_run("v1-case")
    new = make_run("v2-case")
    new.category = "automation_routing"
    first = run_file({"v1-case": CaseGrade(wrong_advice=advice("supported"))}, {"v1-case": old})
    second = run_file({"v2-case": CaseGrade(wrong_advice=advice("unsupported"))}, {"v2-case": new})
    items = pick_from_runs([("run-a", first), ("run-b", second)], 2)
    assert [item.case_id for item in items] == ["v2-case (run-b)", "v1-case (run-a)"]
