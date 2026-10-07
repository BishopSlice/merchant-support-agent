"""Compare two eval runs: uv run python -m evals.compare FIRST.json SECOND.json

Shows each PRD metric side by side and lists cases that passed in one run and failed in
the other, which is how we see run-to-run variance.
"""

import sys
from pathlib import Path

from evals.case_format import EvalCase, load_cases
from evals.grader import summarize_grades
from evals.run import RunFile
from evals.scoring import score_case, summarize


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _metrics(run_file: RunFile, cases: dict[str, EvalCase]) -> tuple[dict, dict[str, bool]]:
    runs = [run for case_id, run in run_file.runs.items() if case_id in cases]
    scores = [score_case(cases[run.case_id], run) for run in runs]
    summary = summarize(scores, runs)
    graded = summarize_grades(run_file.grades)
    metrics = {
        "Resolution rate": _pct(summary.resolution_rate),
        "Wrong advice rate": _pct(graded["wrong_advice_rate"]),
        "Handoff precision": _pct(summary.handoff_precision),
        "Handoff recall": _pct(summary.handoff_recall),
        "Case completeness": _pct(graded["case_completeness"]),
        "Handoff reason accuracy": _pct(summary.handoff_reason_accuracy),
        "Cases passing every check": _pct(summary.pass_rate),
        "Cost per case": f"${summary.cost_per_case_usd or 0:.4f}",
        "Total cost (agent + grading)": "$"
        + f"{summary.total_cost_usd + sum(g.cost_usd for g in run_file.grades.values()):.4f}",
    }
    passed = {score.case_id: score.passed for score in scores if not score.errored}
    return metrics, passed


def compare_runs(
    first: RunFile, first_name: str, second: RunFile, second_name: str, cases: list[EvalCase]
) -> str:
    """Markdown comparing two runs' metrics and per-case outcomes."""
    by_id = {case.id: case for case in cases}
    metrics_a, passed_a = _metrics(first, by_id)
    metrics_b, passed_b = _metrics(second, by_id)
    lines = [
        f"# {first_name} vs {second_name}",
        "",
        f"| Metric | {first_name} | {second_name} |",
        "|---|---|---|",
    ]
    lines += [f"| {name} | {metrics_a[name]} | {metrics_b[name]} |" for name in metrics_a]
    both = sorted(set(passed_a) & set(passed_b))
    flips = [case_id for case_id in both if passed_a[case_id] != passed_b[case_id]]
    lines += [
        "",
        f"## Cases with a different outcome ({len(flips)} of {len(both)} run in both)",
        "",
    ]
    for case_id in flips:
        outcome_a = "passed" if passed_a[case_id] else "failed"
        outcome_b = "passed" if passed_b[case_id] else "failed"
        lines.append(f"- {case_id}: {outcome_a} in {first_name}, {outcome_b} in {second_name}")
    if not flips:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Print the comparison of the two run files given on the command line."""
    first, second = (Path(arg) for arg in sys.argv[1:3])
    print(
        compare_runs(
            RunFile.model_validate_json(first.read_text()),
            first.stem,
            RunFile.model_validate_json(second.read_text()),
            second.stem,
            load_cases(),
        )
    )


if __name__ == "__main__":
    main()
