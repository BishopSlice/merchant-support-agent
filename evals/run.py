"""Run eval cases against the agent and save a scored result.

uv run python -m evals.run [--case ID ...] [--category NAME ...] [--resume PATH [--regrade]]
                           [--no-grade]

Each run is saved to evals/results/<timestamp>-<model>.json after every case, with a
markdown scorecard next to it. Earlier runs are never overwritten; --resume continues a
partial run in place, rerunning only cases that are missing or errored.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from evals.case_format import Category, EvalCase, load_cases
from evals.grader import CaseGrade, grade_run, summarize_grades
from evals.records import CaseRun
from evals.report import render_scorecard
from evals.runner import run_case
from evals.scoring import score_case, summarize
from merchant_agent.config import MODEL_PRICES, PROJECT_ROOT, ModelPrice, get_settings

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"


class RunFile(BaseModel):
    """Everything saved for one eval run."""

    model: str
    started_at: datetime
    finished_at: datetime | None = None
    price: ModelPrice
    case_filter: list[str] = Field(default_factory=list)
    category_filter: list[str] = Field(default_factory=list)
    runs: dict[str, CaseRun] = Field(default_factory=dict)
    grades: dict[str, CaseGrade] = Field(default_factory=dict)


def new_run_path(model: str, now: datetime) -> Path:
    """Path for a new run's results. Refuses to reuse a path, so runs are never overwritten."""
    path = RESULTS_DIR / f"{now:%Y%m%d-%H%M%S}-{model}.json"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    return path


def save(run_file: RunFile, path: Path) -> None:
    """Write the run file atomically, so a crash mid-write can't corrupt earlier progress."""
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(run_file.model_dump_json(indent=2))
    temporary.replace(path)


def select_cases(
    cases: list[EvalCase], case_ids: list[str], categories: list[str]
) -> list[EvalCase]:
    """Keep the cases named by id or category; with neither, keep them all."""
    unknown = set(case_ids) - {case.id for case in cases}
    if unknown:
        sys.exit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
    if not case_ids and not categories:
        return cases
    return [case for case in cases if case.id in case_ids or case.category.value in categories]


def write_scorecard(run_file: RunFile, cases: list[EvalCase], path: Path) -> str:
    """Score every finished case, save the markdown scorecard next to the JSON and return it."""
    by_id = {case.id: case for case in cases}
    runs = [run for case_id, run in run_file.runs.items() if case_id in by_id]
    scores = [score_case(by_id[run.case_id], run) for run in runs]
    graded = summarize_grades({k: g for k, g in run_file.grades.items() if k in by_id})
    header = {
        "Run": path.stem,
        "Model": run_file.model,
        "Started": f"{run_file.started_at:%Y-%m-%d %H:%M} UTC",
    }
    if run_file.grades:
        grading_cost = sum(grade.cost_usd for grade in run_file.grades.values())
        header["Grading cost"] = f"${grading_cost:.4f} (same model, not included in total cost)"
    scorecard = render_scorecard(header, summarize(scores, runs), scores, graded)
    path.with_suffix(".md").write_text(scorecard)
    return scorecard


def main(argv: list[str] | None = None) -> None:
    """Run the selected cases, saving after each one, then write the scorecard."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--case", action="append", default=[], help="run only this case id")
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        choices=[c.value for c in Category],
        help="run only this category",
    )
    parser.add_argument("--resume", type=Path, help="continue a partial run in this file")
    parser.add_argument("--no-grade", action="store_true", help="skip the AI grader")
    parser.add_argument(
        "--regrade", action="store_true", help="with --resume: drop old grades and grade again"
    )
    args = parser.parse_args(argv)

    model = get_settings().model_name
    if model not in MODEL_PRICES:
        sys.exit(f"No price for {model}; add it to MODEL_PRICES in merchant_agent/config.py")
    all_cases = load_cases()

    if args.resume:
        path = args.resume
        run_file = RunFile.model_validate_json(path.read_text())
        if args.regrade:
            run_file.grades = {}
        case_ids = args.case or run_file.case_filter
        categories = args.category or run_file.category_filter
    else:
        now = datetime.now(UTC)
        path = new_run_path(model, now)
        case_ids, categories = args.case, args.category
        run_file = RunFile(
            model=model,
            started_at=now,
            price=MODEL_PRICES[model],
            case_filter=case_ids,
            category_filter=categories,
        )
    cases = select_cases(all_cases, case_ids, categories)
    pending = [c for c in cases if c.id not in run_file.runs or run_file.runs[c.id].status != "ok"]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Running {len(pending)} of {len(cases)} case(s) with {model} -> {path.name}")
    for number, case in enumerate(pending, start=1):
        record = asyncio.run(run_case(case, run_file.price))
        run_file.runs[case.id] = record
        save(run_file, path)
        status = "ok" if record.status == "ok" else f"ERROR {record.error[:80]}"
        cost = f"${record.cost_usd:.4f}"
        print(f"[{number}/{len(pending)}] {case.id}: {status} ({record.seconds}s, {cost})")

    if not args.no_grade:
        grade_run(run_file, save=lambda: save(run_file, path))
    run_file.finished_at = datetime.now(UTC)
    save(run_file, path)
    scorecard = write_scorecard(run_file, cases, path)
    print(scorecard)


if __name__ == "__main__":
    main()
