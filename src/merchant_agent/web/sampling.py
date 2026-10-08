"""Sampled AI grading of live conversations (SPEC, Observability).

About 10% of live conversations are chosen when they start. After each of their turns, the
whole conversation so far is graded with the eval grader's rubrics, in the background, until
the day's grading budget is spent. The dashboard uses each conversation's latest grade and
shows how many conversations were graded.
"""

import json
import secrets
from datetime import UTC, datetime

from evals.grader import Generate, GradingFailed, grade_case
from evals.records import CaseRun, TurnRecord
from merchant_agent.config import ModelPrice
from merchant_agent.events import EventStore
from merchant_agent.tools.handoff import get_case


class SampledGrader:
    def __init__(self, events: EventStore, rate: float, daily_budget_usd: float) -> None:
        self.events = events
        self.rate = rate
        self.daily_budget_usd = daily_budget_usd
        self.spend: dict[str, float] = {}

    def sample(self) -> bool:
        """Decide, when a conversation starts, whether it will be graded."""
        return secrets.randbelow(10_000) < self.rate * 10_000

    def _today(self) -> str:
        return datetime.now(UTC).date().isoformat()

    def grade(
        self,
        conversation_id: str,
        turns: list[TurnRecord],
        generate: Generate,
        price: ModelPrice | None,
    ) -> None:
        """Grade the conversation so far and store the result, unless today's budget is spent."""
        today = self._today()
        if self.spend.get(today, 0.0) >= self.daily_budget_usd:
            return
        case_ids = [
            c.response["case_id"]
            for t in turns
            for c in t.tool_calls
            if c.name == "create_handoff_case"
            and isinstance(c.response, dict)
            and c.response.get("status") == "created"
        ]
        cases = [case for case_id in case_ids if (case := get_case(case_id))]
        run = CaseRun(
            case_id=conversation_id,
            category="live",
            turns=turns,
            handoff_cases=[json.loads(c.model_dump_json()) for c in cases],
        )
        try:
            result = grade_case(run, generate, price)
        except GradingFailed:
            return
        self.spend = {today: self.spend.get(today, 0.0) + result.cost_usd}
        replies = result.wrong_advice.replies if result.wrong_advice else []
        wrong_rate = (
            sum(r.verdict == "unsupported" for r in replies) / len(replies) if replies else None
        )
        completeness = result.completeness.verdict if result.completeness else None
        self.events.record_grade(conversation_id, wrong_rate, completeness, result.cost_usd)
