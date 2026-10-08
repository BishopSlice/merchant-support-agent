"""Runner tests use a fake agent that calls the real tools, so no model is called."""

import asyncio
import os
from typing import ClassVar

import httpx
import pytest
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

    def __init__(self, store_id: str, fail: bool = False, network_error: bool = False) -> None:
        self.network_error = network_error
        self.store_id = store_id
        self.fail = fail
        self.session_service = InMemorySessionService()

    async def run_async(self, *, user_id, session_id, new_message):
        if self.network_error:
            raise httpx.ReadTimeout("timed out")
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
        if "human" in text:
            handoff.create_handoff_case(
                self.store_id, "merchant_requested_human", [], [], "Person", "Call", []
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
        run_case(
            case,
            PRICE,
            runner_factory=lambda: FakeAgentRunner(case.store, **fake_kwargs),
            answer=None,
        )
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


def test_handoff_cases_are_recorded_oldest_first():
    turns = [{"merchant": "I want to appeal"}, {"merchant": "Now get me a human"}]
    record = run(make_case(turns, store="sample-store"))
    assert [c["reason"] for c in record.handoff_cases] == [
        "policy_appeal",
        "merchant_requested_human",
    ]


def test_network_errors_are_recorded_not_raised():
    record = run(make_case([{"merchant": "a"}]), network_error=True)
    assert record.status == "error"
    assert "timed out" in record.error


def test_runs_record_the_agent_version_and_per_turn_timing():
    from merchant_agent.agent import agent_version

    record = run(make_case([{"merchant": "a"}, {"merchant": "b"}]))
    assert record.agent_version == agent_version()
    assert all(turn.seconds >= 0 for turn in record.turns)


class StateCapturingRunner(FakeAgentRunner):
    """Records the session state the agent would see, and what the data tools return."""

    seen_state: ClassVar[dict] = {}
    seen_data: ClassVar[dict] = {}

    async def run_async(self, *, user_id, session_id, new_message):
        from merchant_agent.tools import merchant_tools

        session = await self.session_service.get_session(
            app_name="merchant_support", user_id=user_id, session_id=session_id
        )
        StateCapturingRunner.seen_state = dict(session.state)
        StateCapturingRunner.seen_data = merchant_tools.merchant_data.call(
            "list_account_issues", account=self.store_id
        )
        async for event in super().run_async(
            user_id=user_id, session_id=session_id, new_message=new_message
        ):
            yield event


def run_with(case):
    return asyncio.run(
        run_case(case, PRICE, runner_factory=lambda: StateCapturingRunner(case.store), answer=None)
    )


def test_entry_context_reaches_the_session_state():
    case = make_case([{"merchant": "How do I fix this?"}], store="price-only")
    case.entry_context = {"product": "HG-004", "issue_code": "price_mismatch"}
    case = EvalCase.model_validate(case.model_dump())
    run_with(case)
    assert StateCapturingRunner.seen_state["entry_context"] == {
        "product_name": "accounts/price-only/products/en~US~HG-004",
        "issue_code": "price_mismatch",
    }
    note = StateCapturingRunner.seen_state["entry_note"]
    assert "accounts/price-only/products/en~US~HG-004" in note
    assert "price_mismatch" in note


def test_sessions_without_entry_context_say_the_chat_came_from_help():
    run_with(make_case([{"merchant": "Hello"}], store="price-only"))
    assert "Help" in StateCapturingRunner.seen_state["entry_note"]


@pytest.mark.parametrize(
    ("kind", "check"),
    [
        ("quota", lambda r: "429" in r["error"]),
        ("timeout", lambda r: "timed out" in r["error"]),
        ("error", lambda r: "error" in r),
        ("empty", lambda r: r == {"accountIssues": []}),
        ("malformed", lambda r: not isinstance(r.get("accountIssues", []), list)),
    ],
)
def test_data_failures_are_injected_for_one_tool_only(kind, check):
    from merchant_agent.tools import merchant_tools

    case = make_case([{"merchant": "hi"}], store="suspended-store")
    case.data_failure = {"tool": "list_account_issues", "kind": kind}
    case = EvalCase.model_validate(case.model_dump())
    record = run_with(case)
    assert check(StateCapturingRunner.seen_data)
    # Other tools keep working inside the case...
    assert record.turns[0].tool_calls[0].response["issue_groups"] is not None
    # ...and the normal data source is back afterwards.
    issues = merchant_tools.merchant_data.call("list_account_issues", account="suspended-store")
    assert issues["accountIssues"][0]["severity"] == "CRITICAL"


def test_eval_runs_are_logged_as_eval_traffic(tmp_path):
    import sqlite3

    from evals.runner import log_events
    from merchant_agent.events import EventStore

    record = run_with(make_case([{"merchant": "Hello"}, {"merchant": "Again"}], store="price-only"))
    store = EventStore(tmp_path / "events.sqlite")
    log_events(store, record, PRICE, run_label="20261008-test")
    with sqlite3.connect(store.path) as db:
        assert db.execute("select source, label from conversations").fetchall() == [
            ("eval", f"20261008-test/{record.case_id}")
        ]
        assert db.execute("select count(*) from turns").fetchone() == (2,)
