"""Turn a scored eval run into a markdown scorecard against the PRD's targets."""

from evals.scoring import CaseScore, Summary


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _verdict(value: float | None, target: float, higher_is_better: bool = True) -> str:
    if value is None:
        return "not measured"
    met = value >= target if higher_is_better else value < target
    return "met" if met else "**missed**"


def _row(name: str, value: float | None, target: str, bar: float, higher: bool = True) -> str:
    return f"| {name} | {_pct(value)} | {target} | {_verdict(value, bar, higher)} |"


DEFINITIONS = [
    (
        "- **Resolution rate:** of cases that are plain data fixes (easy fixes, multi-issue, "
        "warnings, must-not-hand-off and angry merchants), the share that passed every check: "
        "no handoff, a re-check after the last fix with the issue gone, required text and "
        "citations present, forbidden text absent."
    ),
    (
        "- **Handoff precision and recall:** a handoff is any case saved during the "
        "conversation. Precision: of conversations that handed off, the share that should "
        "have. Recall: of conversations that should have, the share that did."
    ),
    (
        "- **Wrong advice and case completeness:** graded by a second model call against the "
        "rubrics in `evals/rubrics/`."
    ),
    "- **Cost:** token counts times the prices in `merchant_agent.config.MODEL_PRICES`.",
]


def render_scorecard(
    header: dict[str, str],
    summary: Summary,
    scores: list[CaseScore],
    graded: dict[str, float | None] | None = None,
) -> str:
    """Render the scorecard: PRD metrics with targets, results by category, and every failure."""
    graded = graded or {}
    wrong_advice = graded.get("wrong_advice_rate")
    completeness = graded.get("case_completeness")
    cost = "n/a" if summary.cost_per_case_usd is None else f"${summary.cost_per_case_usd:.4f}"
    lines = ["# Eval scorecard", ""]
    lines += [f"- {key}: {value}" for key, value in header.items()]
    lines += [
        f"- Cases: {summary.cases} ({summary.errors} errored)",
        f"- Total cost: ${summary.total_cost_usd:.4f}",
        "",
        "## PRD metrics",
        "",
        "| Metric | Result | Target | Verdict |",
        "|---|---|---|---|",
        _row("Resolution rate", summary.resolution_rate, "80% or higher", 0.80),
        _row("Wrong advice rate (AI graded)", wrong_advice, "under 5%", 0.05, higher=False),
        _row("Handoff precision", summary.handoff_precision, "90% or higher", 0.90),
        _row("Handoff recall", summary.handoff_recall, "95% or higher", 0.95),
        _row("Case completeness (AI graded)", completeness, "90% or higher", 0.90),
        f"| Cost per case | {cost} | tracked, no target | n/a |",
        "",
        (
            f"Also: {_pct(summary.pass_rate)} of cases passed every check, and "
            f"{_pct(summary.handoff_reason_accuracy)} of correct handoffs gave the expected "
            "reason."
        ),
        "",
        "## By category",
        "",
        "| Category | Pass rate |",
        "|---|---|",
    ]
    lines += [f"| {cat} | {_pct(rate)} |" for cat, rate in summary.pass_rate_by_category.items()]
    failing = [score for score in scores if not score.passed]
    lines += ["", f"## Failures ({len(failing)})", ""]
    if not failing:
        lines.append("None.")
    for score in failing:
        lines.append(f"**{score.case_id}** ({score.category})")
        lines += [f"- {failure}" for failure in score.failures]
        lines.append("")
    lines += ["## How these are measured", "", *DEFINITIONS]
    return "\n".join(lines) + "\n"
