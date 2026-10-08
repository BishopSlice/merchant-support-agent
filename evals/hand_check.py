"""Build a sheet of AI-graded items for a person to check: uv run python -m evals.hand_check RUN.json

Picks a mix of passes and fails from both graders and writes evals/hand-check.md with an
empty "Agree?" column, so we can measure how often a person agrees with the grader.
"""

import json
import sys
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from evals.run import RunFile

HAND_CHECK_PATH = Path(__file__).parent / "hand-check.md"


@dataclass
class HandCheckItem:
    case_id: str
    metric: str
    graded: str
    verdict: str
    detail: str
    evidence: str
    category: str = ""


def _cell(text: str, limit: int = 400) -> str:
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


V2_CATEGORIES = {
    "automation_routing",
    "triage_order",
    "data_tool_failure",
    "entry_context",
    "case_preview",
}


def pick_items(run_file: RunFile, count: int = 10) -> list[HandCheckItem]:
    """Take graded items in turn from four pools (advice fails, case fails, advice passes,
    case passes), so the sheet mixes both graders and both outcomes."""
    return pick_from_runs([("", run_file)], count)


def pick_from_runs(runs: list[tuple[str, RunFile]], count: int = 10) -> list[HandCheckItem]:
    """The same mix, drawn from several runs (each item labelled with its run). Within each
    pool, cases from the v2 categories come first, so the new behaviour gets checked."""
    pools: dict[str, list[HandCheckItem]] = {
        "advice_fail": [],
        "case_fail": [],
        "advice_pass": [],
        "case_pass": [],
    }
    for run_name, run_file in runs:
        _add_items(pools, run_name, run_file)
    for pool in pools.values():
        pool.sort(key=lambda item: item.category not in V2_CATEGORIES)
    mixed = [item for group in zip_longest(*pools.values()) for item in group if item]
    return mixed[:count]


def _add_items(pools: dict, run_name: str, run_file: RunFile) -> None:
    def label(case_id: str) -> str:
        return f"{case_id} ({run_name})" if run_name else case_id

    for case_id in sorted(run_file.grades):
        grade, run = run_file.grades[case_id], run_file.runs.get(case_id)
        if grade.wrong_advice and run:
            for reply in grade.wrong_advice.replies:
                if reply.verdict == "no_advice" or not 0 < reply.turn <= len(run.turns):
                    continue
                pool = "advice_fail" if reply.verdict == "unsupported" else "advice_pass"
                pools[pool].append(
                    HandCheckItem(
                        label(case_id),
                        f"Wrong advice, reply {reply.turn}",
                        run.turns[reply.turn - 1].reply,
                        reply.verdict,
                        "; ".join(reply.unsupported_claims),
                        reply.evidence,
                        run.category,
                    )
                )
        if grade.completeness and run and run.handoff_cases:
            verdict = grade.completeness.verdict
            pools["case_fail" if verdict == "incomplete" else "case_pass"].append(
                HandCheckItem(
                    label(case_id),
                    "Case completeness",
                    json.dumps(run.handoff_cases[-1]),
                    verdict,
                    "; ".join(grade.completeness.missing),
                    grade.completeness.evidence,
                    run.category,
                )
            )


def render_hand_check(run_file: RunFile, run_name: str, count: int = 10) -> str:
    """The hand-check sheet as markdown."""
    lines = [
        "# Hand check of the AI grader",
        "",
        (
            f"Run: `{run_name}` (model `{run_file.model}`). {count} graded items, mixing passes "
            "and fails from both graders. For each row, read what was graded and the grader's "
            "evidence, then fill in **Agree?** with yes or no, and add a note when you disagree. "
            "The share of yes answers tells us how far to trust the AI-graded metrics."
        ),
        "",
        (
            "| # | Case | Metric | What was graded | Grader verdict | Claims or gaps "
            "| Grader evidence | Agree? | Notes |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for number, item in enumerate(pick_items(run_file, count), start=1):
        lines.append(
            f"| {number} | {item.case_id} | {item.metric} | {_cell(item.graded)} | "
            f"{item.verdict} | {_cell(item.detail, 200)} | {_cell(item.evidence)} |  |  |"
        )
    return "\n".join(lines) + "\n"


def render_from_runs(runs: list[tuple[str, RunFile]], count: int = 10) -> str:
    """A hand-check sheet drawn from several runs."""
    names = ", ".join(f"`{name}` (agent `{run.model}`)" for name, run in runs)
    lines = [
        "# Hand check of the AI grader (v2)",
        "",
        (
            f"Runs: {names}. {count} graded items, mixing passes and fails from both graders, "
            "with the v2 categories first. Each case is labelled with its run. For each row, "
            "read what was graded and the grader's evidence, then fill in **Agree?** with yes "
            "or no, and add a note when you disagree."
        ),
        "",
        (
            "| # | Case | Metric | What was graded | Grader verdict | Claims or gaps "
            "| Grader evidence | Agree? | Notes |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for number, item in enumerate(pick_from_runs(runs, count), start=1):
        lines.append(
            f"| {number} | {item.case_id} | {item.metric} | {_cell(item.graded)} | "
            f"{item.verdict} | {_cell(item.detail, 200)} | {_cell(item.evidence)} |  |  |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    """One run: write evals/hand-check.md. Several runs, with --out PATH first: write PATH."""
    args = sys.argv[1:]
    if args[:1] == ["--out"]:
        out, paths = Path(args[1]), [Path(a) for a in args[2:]]
        runs = [(p.stem, RunFile.model_validate_json(p.read_text())) for p in paths]
        out.write_text(render_from_runs(runs))
        print(f"Wrote {out}")
        return
    path = Path(args[0])
    sheet = render_hand_check(RunFile.model_validate_json(path.read_text()), path.stem)
    HAND_CHECK_PATH.write_text(sheet)
    print(f"Wrote {HAND_CHECK_PATH}")


if __name__ == "__main__":
    main()
