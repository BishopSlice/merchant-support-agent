"""Conversation state for the Streamlit app: one agent session per store, kept across reruns."""

import streamlit as st

from merchant_agent import chat, demo
from merchant_agent.tools.handoff import clear_cases


def end_conversation() -> None:
    """Close the current agent session and forget the chat history."""
    session = st.session_state.pop("chat", None)
    if session:
        session.close()
    st.session_state.messages = []


def current_chat(store_id: str) -> "chat.ChatSession":
    """Return the conversation for this store, starting a new one if the store changed."""
    session = st.session_state.get("chat")
    if session is None or session.store_id != store_id:
        end_conversation()
        session = st.session_state.chat = chat.ChatSession(store_id)
    return session


def reset_demo() -> int:
    """Restore the original store data, clear all cases and end the chat."""
    demo.prepare_demo_data(reset=True)
    end_conversation()
    return clear_cases()
