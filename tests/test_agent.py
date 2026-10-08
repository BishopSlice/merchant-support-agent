from types import SimpleNamespace

import pytest

from merchant_agent.agent import build_agent, create_handoff_case
from merchant_agent.models import HandoffReason
from merchant_agent.tools.handoff import get_case


def test_agent_has_the_mcp_data_tools_help_search_and_handoff(monkeypatch):
    from merchant_agent.data import BLOCKED_TOOLS

    monkeypatch.setenv("MODEL_NAME", "test-model")
    agent = build_agent()
    assert agent.model.model == "test-model"
    names = [tool.__name__ for tool in agent.tools]
    assert names == [
        "list_products",
        "get_product_by_name",
        "list_account_issues",
        "list_aggregate_product_statuses",
        "get_automatic_improvements",
        "search_help_docs",
        "create_handoff_case",
    ]
    assert not set(names) & BLOCKED_TOOLS  # hard gate: no write or unneeded MCP tools
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
    assert "DISAPPROVED" in instruction and "DEMOTED" in instruction
    assert instruction.index("DISAPPROVED") < instruction.index("DEMOTED")


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


def test_instructions_do_not_state_unsupported_policy_as_fact():
    # Checkpoint D: the agent repeated these lines from its instructions as Google rules,
    # and no help doc supports them.
    instruction = build_agent().instruction.lower()
    assert "no products can show" not in instruction
    assert "only a human can decide an appeal" not in instruction
    # Handoffs are framed as this service's process; bad phrasings appear only as examples.
    assert "never describe it as a google rule" in instruction


def test_instructions_ask_cases_to_carry_the_merchants_reasons_and_policy_doc():
    instruction = build_agent().instruction.lower()
    assert "every reason, argument or detail they gave" in instruction
    assert "including the policy doc" in instruction


def test_instructions_ask_for_every_product_in_an_issue_group():
    assert "name every affected product" in build_agent().instruction.lower()


def test_instructions_say_an_approval_question_is_not_an_appeal():
    # Task 11 follow-up: "can I edit it to get it approved?" was handed off as an appeal.
    instruction = build_agent().instruction.lower()
    assert "is not an appeal" in instruction
    assert "only if the merchant says they want one" in instruction


def test_instructions_ask_suspension_replies_to_cite_the_policy():
    instruction = build_agent().instruction.lower()
    assert "explain that policy with a citation" in instruction


def test_instructions_keep_out_of_scope_redirects_free_of_navigation_details():
    instruction = build_agent().instruction.lower()
    assert "don't name menus, settings or steps in other google products" in instruction


def test_agent_version_is_stable_and_changes_with_what_the_model_sees(monkeypatch):
    from merchant_agent import agent as agent_module

    first = agent_module.agent_version()
    assert first == agent_module.agent_version()
    assert len(first) == 12 and int(first, 16) >= 0

    monkeypatch.setattr(agent_module, "INSTRUCTION", agent_module.INSTRUCTION + " ")
    assert agent_module.agent_version() != first

    monkeypatch.undo()
    monkeypatch.setenv("MODEL_NAME", "another-model")
    assert agent_module.agent_version() != first
