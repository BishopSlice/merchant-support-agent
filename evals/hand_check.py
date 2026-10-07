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


def _cell(text: str, limit: int = 400) -> str:
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def pick_items(run_file: RunFile, count: int = 10) -> list[HandCheckItem]:
    """Take graded items in turn from four pools (advice fails, case fails, advice passes,
    case passes), so the sheet mixes both graders and both outcomes."""
    pools: dict[str, list[HandCheckItem]] = {
        "advice_fail": [],
        "case_fail": [],
        "advice_pass": [],
        "case_pass": [],
    }
    for case_id in sorted(run_file.grades):
        grade, run = run_file.grades[case_id], run_file.runs.get(case_id)
        if grade.wrong_advice and run:
            for reply in grade.wrong_advice.replies:
                if reply.verdict == "no_advice" or not 0 < reply.turn <= len(run.turns):
                    continue
                pool = "advice_fail" if reply.verdict == "unsupported" else "advice_pass"
                pools[pool].append(
                    HandCheckItem(
                        case_id,
                        f"Wrong advice, reply {reply.turn}",
                        run.turns[reply.turn - 1].reply,
                        reply.verdict,
                        "; ".join(reply.unsupported_claims),
                        reply.evidence,
                    )
                )
        if grade.completeness and run and run.handoff_cases:
            verdict = grade.completeness.verdict
            pools["case_fail" if verdict == "incomplete" else "case_pass"].append(
                HandCheckItem(
                    case_id,
                    "Case completeness",
                    json.dumps(run.handoff_cases[-1]),
                    verdict,
                    "; ".join(grade.completeness.missing),
                    grade.completeness.evidence,
                )
            )
    mixed = [item for group in zip_longest(*pools.values()) for item in group if item]
    return mixed[:count]


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


def main() -> None:
    """Write evals/hand-check.md from the run file given on the command line."""
    path = Path(sys.argv[1])
    sheet = render_hand_check(RunFile.model_validate_json(path.read_text()), path.stem)
    HAND_CHECK_PATH.write_text(sheet)
    print(f"Wrote {HAND_CHECK_PATH}")


if __name__ == "__main__":
    main()
