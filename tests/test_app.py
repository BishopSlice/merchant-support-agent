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


def run_app(page: str = "Merchant chat") -> AppTest:
    """Start the app and open a page (the app itself opens on "Start here")."""
    app = AppTest.from_file(APP, default_timeout=10).run()
    if page != "Start here":
        app.sidebar.radio(key="page").set_value(page).run()
    return app


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


# --- Guided walkthrough (Task 12a) ---


def test_the_app_opens_on_a_landing_page_that_explains_itself():
    app = run_app("Start here")
    assert app.sidebar.radio(key="page").value == "Start here"
    page = "\n".join(m.value for m in app.markdown)
    assert "Google Shopping" in page
    for role in ("Merchant", "Demo operator", "Specialist"):
        assert role in page
    assert app.button(key="start_guide").label == "Start the guided demo"
    assert FakeChatSession.started == []  # no agent session until the chat is opened


def test_starting_the_guide_opens_step_one_as_the_merchant_on_sample_store():
    app = run_app("Start here")
    app.button(key="start_guide").click().run()
    assert app.sidebar.radio(key="page").value == "Merchant chat"
    assert app.sidebar.selectbox(key="store").value == "sample-store"
    panel = "\n".join([m.value for m in app.markdown] + [c.value for c in app.caption])
    assert "Step 1 of 6" in panel and "You are the Merchant" in panel


def test_send_this_message_sends_the_suggested_text():
    app = run_app("Start here")
    app.button(key="start_guide").click().run()
    app.button(key="guide_send").click().run()
    texts = [m.markdown[0].value for m in app.chat_message]
    assert texts[0] == "Half my products got disapproved yesterday, what happened?"
    assert texts[1].startswith("Reply to: Half my products")


def test_the_fix_step_applies_the_fix_to_the_demo_data():
    from merchant_agent.tools.feed_checker import check_feed

    app = run_app("Start here")
    app.button(key="start_guide").click().run()
    app.button(key="guide_next").click().run()
    app.button(key="guide_next").click().run()
    assert "Step 3 of 6" in "\n".join(m.value for m in app.caption)
    app.button(key="guide_fix").click().run()
    groups = {g["issue_type"] for g in check_feed("sample-store")["issue_groups"]}
    assert "missing_shipping" not in groups


def test_the_guide_moves_to_the_inbox_for_the_specialist_steps_and_can_go_back():
    app = run_app("Start here")
    app.button(key="start_guide").click().run()
    for _ in range(4):
        app.button(key="guide_next").click().run()
    assert app.sidebar.radio(key="page").value == "Specialist inbox"
    assert "You are the Specialist" in "\n".join(m.value for m in app.caption)
    app.button(key="guide_back").click().run()
    assert app.sidebar.radio(key="page").value == "Merchant chat"


def test_exiting_the_guide_removes_the_step_panel():
    app = run_app("Start here")
    app.button(key="start_guide").click().run()
    app.button(key="guide_exit").click().run()
    assert not any("Step 1 of 6" in c.value for c in app.caption)


def test_every_page_says_which_role_you_are_playing():
    assert any("You are the merchant" in c.value for c in run_app("Merchant chat").caption)
    assert any("You are a support specialist" in c.value for c in run_app("Specialist inbox").caption)
