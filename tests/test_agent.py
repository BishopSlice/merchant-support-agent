from types import SimpleNamespace

from merchant_agent.agent import build_agent, check_feed


def test_check_feed_tool_reads_store_from_session_state():
    context = SimpleNamespace(state={"store_id": "sample-store"})
    result = check_feed(context)
    assert result["store_id"] == "sample-store"
    assert result["total_products"] == 30


def test_agent_has_only_the_check_feed_tool(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    agent = build_agent()
    assert agent.model == "test-model"
    assert [tool.__name__ for tool in agent.tools] == ["check_feed"]
    assert "{store_id}" in agent.instruction
