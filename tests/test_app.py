"""Tests for the Streamlit app, using a fake agent so no model is called."""

from typing import ClassVar

import pytest
from streamlit.testing.v1 import AppTest

from merchant_agent import chat
from merchant_agent.chat import ToolCall, Turn
from merchant_agent.config import PROJECT_ROOT
from merchant_agent.tools import handoff

APP = str(PROJECT_ROOT / "app" / "streamlit_app.py")


class FakeChatSession:
    """Replies with a fixed turn; files a real case when asked to appeal."""

    started: ClassVar[list[str]] = []

    def __init__(self, store_id: str) -> None:
        self.store_id = store_id
        FakeChatSession.started.append(store_id)

    def send(self, text: str) -> Turn:
        calls = [
            ToolCall(
                name="check_feed",
                args={},
                response={"disapproved_products": 13, "limited_products": 5},
            )
        ]
        if "appeal" in text:
            result = handoff.create_handoff_case(
                store_id=self.store_id,
                reason="policy_appeal",
                issues_found=["restricted_product: HG-023"],
                already_tried=[],
                merchant_request="Appeal the CBD candle",
                suggested_next_step="Review HG-023",
                cited_doc_ids=["request-review"],
            )
            args = {"reason": "policy_appeal"}
            calls.append(ToolCall(name="create_handoff_case", args=args, response=result))
        return Turn(reply=f"Reply to: {text}", tool_calls=calls)

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(chat, "ChatSession", FakeChatSession)
    FakeChatSession.started = []


def run_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=10).run()


def go_to(app: AppTest, page: str) -> AppTest:
    app.sidebar.radio(key="page").set_value(page)
    return app.run()


def test_chat_page_offers_both_stores_and_starts_a_conversation():
    app = run_app()
    assert not app.exception
    assert app.sidebar.selectbox(key="store").options == ["sample-store", "suspended-store"]
    assert FakeChatSession.started == ["sample-store"]


def test_sending_a_message_shows_reply_and_what_the_agent_did():
    app = run_app()
    app.chat_input[0].set_value("What happened?").run()
    assert [m.markdown[0].value for m in app.chat_message] == [
        "What happened?",
        "Reply to: What happened?",
    ]
    assert app.expander[0].label == "What the agent did"
    assert "Checked the product feed: 13 disapproved" in app.expander[0].markdown[0].value


def test_history_survives_reruns_and_reset_clears_it():
    app = run_app()
    app.chat_input[0].set_value("Hello").run()
    app.run()
    assert len(app.chat_message) == 2
    app.sidebar.button(key="reset_conversation").click().run()
    assert len(app.chat_message) == 0


def test_switching_store_starts_a_new_conversation():
    app = run_app()
    app.chat_input[0].set_value("Hello").run()
    app.sidebar.selectbox(key="store").set_value("suspended-store").run()
    assert len(app.chat_message) == 0
    assert FakeChatSession.started == ["sample-store", "suspended-store"]


def test_handoff_shows_a_notice_and_the_case_appears_in_the_inbox():
    app = run_app()
    app.chat_input[0].set_value("I want to appeal").run()
    case_id = handoff.list_cases()[0].case_id
    assert case_id in app.success[0].value

    go_to(app, "Specialist inbox")
    app.button(key=f"open_{case_id}").click().run()
    page = "\n".join(m.value for m in app.markdown)
    assert "Policy appeal" in page
    assert "Appeal the CBD candle" in page
    assert "Requesting a review or appealing a decision" in page


def test_inbox_empty_state():
    app = go_to(run_app(), "Specialist inbox")
    assert "No cases yet" in app.info[0].value


def test_simulated_fix_edits_the_demo_copy_and_reset_restores_it():
    from merchant_agent.tools.feed_checker import check_feed

    app = run_app()
    app.sidebar.selectbox(key="fix_issue").set_value("missing_shipping")
    app.sidebar.button(key="apply_fix").click().run()
    assert "HG-019" in app.sidebar.success[0].value
    groups = {g["issue_type"] for g in check_feed("sample-store")["issue_groups"]}
    assert "missing_shipping" not in groups

    app.sidebar.button(key="reset_demo").click().run()
    groups = {g["issue_type"] for g in check_feed("sample-store")["issue_groups"]}
    assert "missing_shipping" in groups


def test_demo_fix_uses_the_chosen_store_on_every_page():
    app = run_app()
    app.sidebar.selectbox(key="store").set_value("suspended-store").run()
    go_to(app, "Specialist inbox")
    app.sidebar.selectbox(key="fix_issue").set_value("missing_shipping")
    app.sidebar.button(key="apply_fix").click().run()
    assert "suspended-store" in app.sidebar.info[0].value
