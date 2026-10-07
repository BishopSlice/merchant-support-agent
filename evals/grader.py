"""AI grader for the two PRD metrics a rule can't check: wrong advice and case completeness.

A second model call reads the conversation against a fixed rubric in evals/rubrics/ and
returns a structured verdict that quotes its evidence. The grader uses the same model as the
agent (MODEL_NAME); SPEC.md asks for approval before using a different one.
"""

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from evals.records import CaseRun, TokenUsage
from merchant_agent.chat import Usage
from merchant_agent.config import PROJECT_ROOT, ModelPrice, cost_usd, get_settings
from merchant_agent.tools.help_search import load_help_docs

if TYPE_CHECKING:
    from evals.run import RunFile

RUBRICS_DIR = PROJECT_ROOT / "evals" / "rubrics"


class ReplyVerdict(BaseModel):
    """The grader's verdict on one agent reply."""

    turn: int = Field(description="Agent reply number, starting at 1")
    verdict: Literal["no_advice", "supported", "unsupported"]
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence: str = Field(description="Quotes from the reply and docs the verdict rests on")


class WrongAdviceGrade(BaseModel):
    replies: list[ReplyVerdict]


class CompletenessGrade(BaseModel):
    verdict: Literal["complete", "incomplete"]
    missing: list[str] = Field(
        default_factory=list, description="Questions the specialist would still have to ask"
    )
    evidence: str = Field(description="Quotes from the conversation and case")


class CaseGrade(BaseModel):
    """Both grades for one case, plus what grading it cost."""

    wrong_advice: WrongAdviceGrade | None = None
    completeness: CompletenessGrade | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0


# A model call: (prompt, response schema) -> (parsed response, token usage).
Generate = Callable[[str, type[BaseModel]], tuple[BaseModel, Usage]]


def _rubric(name: str) -> str:
    return (RUBRICS_DIR / f"{name}.md").read_text()


def _conversation(run: CaseRun) -> str:
    lines = []
    for number, turn in enumerate(run.turns, start=1):
        lines += [f"Merchant: {turn.merchant}", "", f"Agent reply {number}: {turn.reply}", ""]
    return "\n".join(lines)


def retrieved_doc_ids(run: CaseRun) -> list[str]:
    """Ids of every help doc that search_help_docs returned during the conversation, in order."""
    ids = [
        result["doc_id"]
        for turn in run.turns
        for call in turn.tool_calls
        if call.name == "search_help_docs" and isinstance(call.response, dict)
        for result in call.response.get("results", [])
    ]
    return list(dict.fromkeys(ids))


def wrong_advice_prompt(run: CaseRun) -> str:
    """Rubric, the full text of every retrieved doc, the feed check data and the conversation."""
    docs = {doc.doc_id: doc for doc in load_help_docs()}
    doc_ids = [doc_id for doc_id in retrieved_doc_ids(run) if doc_id in docs]
    doc_text = "\n\n".join(
        f"### {docs[i].title} ({i})\nSource: {docs[i].source_url}\n\n"
        + "\n\n".join(docs[i].passages)
        for i in doc_ids
    )
    feed_data = [
        call.response for turn in run.turns for call in turn.tool_calls if call.name == "check_feed"
    ]
    return "\n\n".join(
        [
            _rubric("wrong_advice"),
            "## Help docs the agent retrieved",
            doc_text or "The agent retrieved no help docs in this conversation.",
            "## Feed check data the agent received",
            json.dumps(feed_data, indent=1) if feed_data else "None.",
            "## Conversation",
            _conversation(run),
        ]
    )


def completeness_prompt(run: CaseRun) -> str:
    """Rubric, the conversation and the most recent handoff case."""
    return "\n\n".join(
        [
            _rubric("case_completeness"),
            "## Conversation",
            _conversation(run),
            "## Case",
            json.dumps(run.handoff_cases[-1], indent=1),
        ]
    )


def grade_case(run: CaseRun, generate: Generate, price: ModelPrice | None) -> CaseGrade:
    """Grade wrong advice for every run, and completeness for runs that handed off."""
    grade = CaseGrade()
    total = Usage()
    grade.wrong_advice, usage = generate(wrong_advice_prompt(run), WrongAdviceGrade)
    total += usage
    if run.handoff_cases:
        grade.completeness, usage = generate(completeness_prompt(run), CompletenessGrade)
        total += usage
    grade.usage = TokenUsage(**asdict(total))
    grade.cost_usd = cost_usd(total, price) if price else 0.0
    return grade


def gemini_generate(model: str) -> Generate:
    """A Generate function backed by Gemini with JSON output and retries on rate limits."""
    retry = types.HttpRetryOptions(attempts=5, initial_delay=10, max_delay=60)
    client = genai.Client(http_options=types.HttpOptions(retry_options=retry))

    def generate(prompt: str, schema: type[BaseModel]) -> tuple[BaseModel, Usage]:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        usage = Usage.from_metadata(response.usage_metadata) if response.usage_metadata else Usage()
        return schema.model_validate_json(response.text), usage

    return generate


def grade_run(
    run_file: "RunFile", save: Callable[[], None], generate: Generate | None = None
) -> None:
    """Grade every finished, ungraded case in a run, saving after each one."""
    generate = generate or gemini_generate(get_settings().model_name)
    pending = [
        (case_id, run)
        for case_id, run in run_file.runs.items()
        if run.status == "ok" and case_id not in run_file.grades
    ]
    for number, (case_id, run) in enumerate(pending, start=1):
        run_file.grades[case_id] = grade_case(run, generate, run_file.price)
        save()
        print(f"[graded {number}/{len(pending)}] {case_id}")


def summarize_grades(grades: dict[str, CaseGrade]) -> dict[str, float | None]:
    """Wrong advice rate (over every graded reply) and case completeness (over handoffs)."""
    verdicts = [
        reply.verdict
        for grade in grades.values()
        if grade.wrong_advice
        for reply in grade.wrong_advice.replies
    ]
    completeness = [g.completeness.verdict for g in grades.values() if g.completeness]
    return {
        "wrong_advice_rate": verdicts.count("unsupported") / len(verdicts) if verdicts else None,
        "case_completeness": (
            completeness.count("complete") / len(completeness) if completeness else None
        ),
    }
