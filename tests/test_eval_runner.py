"""Runner tests use a fake agent that calls the real tools, so no model is called."""

import asyncio
import os

from google.adk import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import ClientError

from evals.case_format import EvalCase
from evals.runner import run_case
from merchant_agent.config import PROJECT_ROOT, ModelPrice
from merchant_agent.tools import handoff
from merchant_agent.tools.feed_checker import check_feed

PRICE = ModelPrice(input_per_million=1.0, cached_input_per_million=0.1, output_per_million=2.0)
ORIGINAL_FEED = PROJECT_ROOT / "evals" / "stores" / "shipping-only" / "feed.csv"


class FakeAgentRunner:
    """Checks the feed on every message; files an appeal case when asked to appeal."""

    def __init__(self, store_id: str, fail: bool = False) -> None:
        self.store_id = store_id
        self.fail = fail
        self.session_service = InMemorySessionService()

    async def run_async(self, *, user_id, session_id, new_message):
        if self.fail:
            raise ClientError(429, {"error": {"message": "quota exhausted"}})
        text = new_message.parts[0].text
        call = types.FunctionCall(id="1", name="check_feed", args={})
        yield Event(
            author="agent",
            content=types.Content(role="model", parts=[types.Part(function_call=call)]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=1000, candidates_token_count=100
            ),
        )
        result = types.FunctionResponse(
            id="1", name="check_feed", response=check_feed(self.store_id)
        )
        yield Event(
            author="agent",
            content=types.Content(role="user", parts=[types.Part(function_response=result)]),
        )
        if "appeal" in text:
            handoff.create_handoff_case(
                self.store_id, "policy_appeal", [], [], "Appeal", "Review", []
            )
        yield Event(
            author="agent",
            content=types.Content(role="model", parts=[types.Part(text=f"Re: {text}")]),
        )

    async def close(self):
        pass


def make_case(turns, store="shipping-only") -> EvalCase:
    return EvalCase(
        id="c1",
        category="easy_fix",
        store=store,
        description="d",
        turns=turns,
        expect={"should_handoff": False},
    )


def run(case, **fake_kwargs):
    return asyncio.run(
        run_case(case, PRICE, runner_factory=lambda: FakeAgentRunner(case.store, **fake_kwargs))
    )


def test_records_turns_tool_calls_and_fixes():
    case = make_case(
        [{"merchant": "What's wrong?"}, {"merchant": "Fixed", "fix": "missing_shipping"}]
    )
    record = run(case)
    assert record.status == "ok"
    assert [turn.reply for turn in record.turns] == ["Re: What's wrong?", "Re: Fixed"]
    assert record.turns[1].fixed_product_ids == ["HG-030"]
    first, second = (turn.tool_calls[0].response for turn in record.turns)
    assert [g["issue_type"] for g in first["issue_groups"]] == ["missing_shipping"]
    assert second["issue_groups"] == []


def test_each_case_runs_on_a_throwaway_copy_and_restores_settings():
    before = ORIGINAL_FEED.read_text()
    env_before = (os.environ.get("DATA_DIR"), os.environ.get("RUNTIME_DIR"))
    run(make_case([{"merchant": "Fixed", "fix": "missing_shipping"}]))
    assert ORIGINAL_FEED.read_text() == before
    assert (os.environ.get("DATA_DIR"), os.environ.get("RUNTIME_DIR")) == env_before


def test_cases_created_during_the_run_are_recorded_and_do_not_leak():
    record = run(make_case([{"merchant": "I want to appeal"}], store="sample-store"))
    assert [c["reason"] for c in record.handoff_cases] == ["policy_appeal"]
    assert run(make_case([{"merchant": "hello"}], store="sample-store")).handoff_cases == []


def test_usage_and_cost_are_totalled():
    record = run(make_case([{"merchant": "a"}, {"merchant": "b"}]))
    assert record.usage.model_calls == 2
    assert record.usage.input_tokens == 2000 and record.usage.output_tokens == 200
    assert record.cost_usd == (2000 * 1.0 + 200 * 2.0) / 1_000_000


def test_api_errors_are_recorded_not_raised():
    record = run(make_case([{"merchant": "a"}]), fail=True)
    assert record.status == "error"
    assert "quota exhausted" in record.error
