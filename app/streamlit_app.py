"""Merchant Support Agent demo app. Run: uv run streamlit run app/streamlit_app.py

Three pages: a landing page with a guided demo, the merchant chat and the specialist inbox.
The app works on a demo copy of data/ (in runtime/demo-data), so simulated fixes can be
undone with "Reset demo". All logic lives in src/merchant_agent; this file is layout only.
"""

import os

import streamlit as st
from conversation import current_chat, end_conversation, reset_demo
from google.genai.errors import APIError
from guided_demo import guide_panel, landing_page

from merchant_agent import chat, demo
from merchant_agent.chat import describe_tool_call
from merchant_agent.guide import PAGES, ROLES
from merchant_agent.inbox import case_label, format_case
from merchant_agent.models import IssueType
from merchant_agent.stores import list_stores
from merchant_agent.tools.handoff import get_case, list_cases

st.set_page_config(page_title="Merchant Support Agent", page_icon="🛍️", layout="wide")
os.environ["DATA_DIR"] = str(demo.prepare_demo_data())


# --- Pages ---


def show_message(message: dict) -> None:
    """Draw one chat bubble, with the agent's steps and any handoff notice."""
    with st.chat_message(message["role"]):
        st.markdown(message["text"])
        if message.get("steps"):
            with st.expander("What the agent did"):
                st.markdown("\n".join(f"- {line}" for line in message["steps"]))
        for case_id in message.get("case_ids", []):
            st.success(f"Case {case_id} was sent to the specialist inbox.")


def send(session: "chat.ChatSession", text: str) -> None:
    """Show the merchant's message, get the agent's reply and show it."""
    user_message = {"role": "user", "text": text}
    st.session_state.messages.append(user_message)
    show_message(user_message)
    with st.spinner("Checking..."):
        try:
            turn = session.send(text)
        except APIError as error:  # e.g. rate limits: show it instead of crashing
            st.error(f"The agent couldn't answer: {error}")
            return
    reply = {
        "role": "assistant",
        "text": turn.reply,
        "steps": [describe_tool_call(call) for call in turn.tool_calls],
        "case_ids": turn.case_ids,
    }
    st.session_state.messages.append(reply)
    show_message(reply)


def merchant_chat_page(store_id: str) -> None:
    session = current_chat(store_id)
    st.title("Merchant chat")
    st.caption(f"You are the merchant: the owner of **{store_id}**. Ask about your products.")
    for message in st.session_state.messages:
        show_message(message)
    queued = st.session_state.pop("pending_message", "")
    if text := st.chat_input("Ask about your products") or queued:
        send(session, text)


def specialist_inbox_page() -> None:
    st.title("Specialist inbox")
    st.caption("You are a support specialist at Google, picking up cases the agent handed over.")
    cases = list_cases()
    if not cases:
        st.info("No cases yet. Cases appear here when the agent hands a conversation off.")
        return
    st.caption(f"{len(cases)} case(s), newest first.")
    list_column, detail_column = st.columns([2, 3])
    with list_column:
        for case in cases:
            if st.button(case_label(case), key=f"open_{case.case_id}", use_container_width=True):
                st.session_state.open_case = case.case_id
    open_case = get_case(st.session_state.get("open_case") or cases[0].case_id) or cases[0]
    with detail_column:
        st.subheader(open_case.case_id)
        created = f"{open_case.created_at:%-d %b %Y, %H:%M} UTC"
        st.caption(f"Store: {open_case.store_id} · Created {created}")
        st.markdown(format_case(open_case))


# --- Layout ---

st.session_state.setdefault("messages", [])
page = st.sidebar.radio("Page", PAGES, key="page")
# The store is the merchant you chat as, and the store the demo fixes apply to.
store_id = st.sidebar.selectbox("Store", list_stores(), key="store")
if page == "Merchant chat" and st.sidebar.button("Reset conversation", key="reset_conversation"):
    end_conversation()
guide_panel(page)

with st.sidebar.expander("Demo operator controls", expanded=False):
    st.caption(ROLES["Demo operator"])
    issue = st.selectbox(
        "Simulate a fix", [issue.value for issue in demo.FIXABLE_ISSUE_TYPES], key="fix_issue"
    )
    if st.button("Apply fix", key="apply_fix"):
        fixed = demo.apply_fix(store_id, IssueType(issue))
        if fixed:
            st.success(f"Fixed {issue} on {', '.join(fixed)} in {store_id}.")
        else:
            st.info(f"No products in {store_id} have {issue}.")
    if st.button("Reset demo", key="reset_demo", help="Original store data, no cases"):
        removed = reset_demo()
        st.success(f"Store data restored and {removed} case(s) cleared.")

if page == "Start here":
    landing_page()
elif page == "Merchant chat":
    merchant_chat_page(store_id)
else:
    specialist_inbox_page()
