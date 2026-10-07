from types import SimpleNamespace

import pytest

from merchant_agent.agent import build_agent, check_feed, create_handoff_case
from merchant_agent.models import HandoffReason
from merchant_agent.tools.handoff import get_case


def test_check_feed_tool_reads_store_from_session_state():
    context = SimpleNamespace(state={"store_id": "sample-store"})
    result = check_feed(context)
    assert result["store_id"] == "sample-store"
    assert result["total_products"] == 30


def test_agent_has_feed_check_help_search_and_handoff_tools(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    agent = build_agent()
    assert agent.model.model == "test-model"
    assert [tool.__name__ for tool in agent.tools] == [
        "check_feed",
        "search_help_docs",
        "create_handoff_case",
    ]
    assert "{store_id}" in agent.instruction


def test_instructions_require_citing_help_docs():
    instruction = build_agent().instruction
    assert "search_help_docs" in instruction
    assert "source_url" in instruction


def test_model_retries_when_rate_limited():
    retry = build_agent().model.retry_options
    assert retry.attempts >= 3
    assert retry.initial_delay >= 5
    assert retry.max_delay >= retry.initial_delay


def test_instructions_put_disapprovals_before_warnings():
    instruction = build_agent().instruction
    assert "disapproved_products" in instruction
    assert instruction.index("disapproved") < instruction.index("limited")


def test_handoff_tool_files_the_case_under_the_session_store(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    context = SimpleNamespace(state={"store_id": "suspended-store"})
    result = create_handoff_case(
        reason="account_suspended",
        issues_found=["Account suspended for misrepresentation"],
        already_tried=[],
        merchant_request="Get my products showing again",
        merchant_reasons=["I already added a returns page"],
        suggested_next_step="Review the suspension",
        cited_doc_ids=["misrepresentation"],
        tool_context=context,
    )
    assert get_case(result["case_id"]).store_id == "suspended-store"


@pytest.mark.parametrize("reason", [r.value for r in HandoffReason])
def test_instructions_cover_every_handoff_reason(reason):
    assert reason in build_agent().instruction


def test_instructions_cover_the_must_not_hand_off_rule_and_appeal_warning():
    instruction = build_agent().instruction.lower()
    assert "do not hand off" in instruction
    assert "one chance to disagree" in instruction
    assert "repeat" in instruction  # merchant won't need to repeat themselves


def test_model_calls_time_out_instead_of_hanging():
    timeout_ms = build_agent().generate_content_config.http_options.timeout
    assert 30_000 <= timeout_ms <= 300_000
