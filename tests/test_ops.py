"""The /ops dashboard's numbers: computed from the event store with the shared metrics."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from test_events import Call, Turn

from evals.case_format import load_cases
from evals.records import CaseRun
from evals.runner import log_events
from evals.scoring import score_case, summarize
from merchant_agent.config import MODEL_PRICES, PROJECT_ROOT
from merchant_agent.events import EventStore
from merchant_agent.ops import conversations, summary, trace

PRICE = MODEL_PRICES["gemini-3.6-flash"]


@pytest.fixture
def store(tmp_path):
    return EventStore(tmp_path / "events.sqlite")


def live(store, entry="help", turns=(), checks=None):
    conversation = store.start_conversation(
        source="live", store_id="s", agent_version="v1", model="m", entry_point=entry
    )
    ids = [
        store.record_turn(conversation, "hi", t, cost_usd=0.01, checks=checks or {}) for t in turns
    ]
    return conversation, ids


HANDOFF = Call(
    "create_handoff_case",
    {"reason": "policy_appeal"},
    {"status": "created", "case_id": "CASE-1", "preview": {}},
)


def test_an_empty_store_says_there_is_no_data(store):
    data = summary(store, source="live")
    assert data["conversations"] == 0
    assert data["small_sample"] is True
    assert data["operations"]["latency_p50"] is None


def test_outcomes_count_conversations_handoffs_and_feedback(store):
    _, [turn] = live(store, "issue_row", [Turn("ok", [HANDOFF], seconds=4.0)])
    live(store, "help", [Turn("ok", seconds=6.0)])
    store.record_feedback(turn, 1)
    data = summary(store, source="live")
    outcomes = data["outcomes"]
    assert data["conversations"] == 2
    assert outcomes["by_entry_point"] == {"issue_row": 1, "help": 1}
    assert outcomes["handoff_rate"] == 0.5
    assert outcomes["handoff_reasons"] == {"policy_appeal": 1}
    assert outcomes["feedback"] == {"up": 1, "down": 0}
    # One conversation contained, valued with the business case's stated assumption.
    assert outcomes["cost_avoided"]["contained"] == 1
    assert outcomes["cost_avoided"]["usd"] == pytest.approx(8.01 - 0.01)
    assert "8.01" in outcomes["cost_avoided"]["assumption"]


def test_safety_counts_write_calls_and_behaviour_after_tool_failures(store):
    live(store, turns=[Turn("ok")], checks={"write_calls": ["create_data_source"]})
    live(store, turns=[Turn("ok")], checks={"tool_failed": True, "invented": []})
    live(store, turns=[Turn("ok")], checks={"tool_failed": True, "invented": ["invented count"]})
    safety = summary(store, source="live")["safety"]
    assert safety["write_calls"] == 1
    assert safety["after_tool_failure"] == {"graceful": 1, "invented": 1}


def test_operations_report_latency_cost_and_tool_errors(store):
    failing = Call("list_products", {}, {"error": "429 quota"})
    live(store, turns=[Turn("a", seconds=2.0), Turn("b", [failing], seconds=10.0)])
    ops = summary(store, source="live")["operations"]
    assert (ops["latency_p50"], ops["latency_p95"]) == (2.0, 10.0)
    assert ops["cost_per_conversation"] == pytest.approx(0.02)
    assert ops["tool_errors"] == {"list_products": 1}
    assert ops["agent_versions"] == ["v1"]


def test_traffic_sources_are_kept_apart(store):
    live(store, turns=[Turn("ok")])
    store.start_conversation(source="eval", store_id="s", agent_version="v", model="m")
    assert summary(store, source="live")["conversations"] == 1
    assert summary(store, source="eval")["conversations"] == 1


def test_quality_uses_each_conversations_latest_grade_and_shows_the_sample(store):
    conversation, _ = live(store, turns=[Turn("ok")])
    store.record_grade(conversation, 0.5, None, 0.01)
    store.record_grade(conversation, 0.0, "complete", 0.01)  # regraded after a later turn
    quality = summary(store, source="live")["quality"]
    assert quality["graded"] == 1
    assert quality["wrong_advice_rate"] == 0.0
    assert quality["case_completeness"] == 1.0


def test_alerts_fire_on_write_calls_and_tool_errors(store):
    failing = Call("list_products", {}, {"error": "x"})
    live(store, turns=[Turn("ok", [failing])], checks={"write_calls": ["create_data_source"]})
    alerts = summary(store, source="live")["alerts"]
    assert any("write" in a.lower() for a in alerts)
    assert any("tool errors" in a.lower() for a in alerts)


def test_old_conversations_fall_outside_the_window(store):
    live(store, turns=[Turn("ok")])
    later = datetime.now(UTC) + timedelta(days=10)
    assert summary(store, source="live", days=7, now=later)["conversations"] == 0


def test_conversation_list_and_trace(store):
    conversation, [turn] = live(store, turns=[Turn("Reply", [HANDOFF])])
    store.record_feedback(turn, -1)
    [row] = conversations(store, source="live")
    assert row["id"] == conversation and row["handoffs"] == 1 and row["feedback"] == -1
    detail = trace(store, conversation)
    assert detail["turns"][0]["reply"] == "Reply"
    assert detail["turns"][0]["tool_calls"][0]["name"] == "create_handoff_case"
    assert trace(store, "missing") is None


def test_eval_traffic_metrics_match_the_eval_scorecard(store):
    """A shared definition must give the same number on /ops as in the eval scorecard."""
    results = json.loads(
        (PROJECT_ROOT / "evals/results/20261008-121551-gemini-3.6-flash.json").read_text()
    )
    runs = [CaseRun.model_validate(r) for r in results["runs"].values()]
    for run in runs:
        log_events(store, run, PRICE, run_label="baseline")
    cases = {c.id: c for c in load_cases()}
    scorecard = summarize([score_case(cases[r.case_id], r) for r in runs], runs)
    ops = summary(store, source="eval")
    assert ops["operations"]["latency_p50"] == scorecard.latency_p50_seconds
    assert ops["operations"]["latency_p95"] == scorecard.latency_p95_seconds
    assert ops["safety"]["write_calls"] == scorecard.write_calls
