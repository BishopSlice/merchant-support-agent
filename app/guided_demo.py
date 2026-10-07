"""The landing page and the guided-demo step panel. Step content lives in merchant_agent.guide.

Button callbacks run before the next rerun, which is what lets them change the page.
"""

import streamlit as st
from conversation import reset_demo

from merchant_agent import demo
from merchant_agent.guide import ROLES, STEPS, step
from merchant_agent.models import IssueType


def go_to_step(number: int) -> None:
    st.session_state.guide_step = number
    st.session_state.page = step(number).page


def start_guide() -> None:
    reset_demo()
    st.session_state.store = "sample-store"
    go_to_step(1)


def exit_guide() -> None:
    st.session_state.guide_step = None


def open_chat() -> None:
    st.session_state.page = "Merchant chat"


def queue_message(text: str) -> None:
    st.session_state.page = "Merchant chat"
    st.session_state.pending_message = text


def apply_guide_fix(issue: IssueType) -> None:
    fixed = demo.apply_fix(st.session_state.store, issue)
    products = ", ".join(fixed) or "no products"
    st.session_state.guide_notice = f"Done: the merchant's product data now fixes {products}."


def guide_panel(page: str) -> None:
    """The current step, in the sidebar so it stays in view while the chat scrolls."""
    number = st.session_state.get("guide_step")
    if not number:
        return
    current = step(number)
    with st.sidebar.container(border=True):
        st.caption(f"Guided demo · Step {number} of {len(STEPS)} · You are the {current.role}")
        st.subheader(current.title)
        st.markdown(current.body)
        if current.page != page:
            st.button(f"Go to {current.page}", key="guide_go", on_click=go_to_step, args=(number,))
        if current.fix:
            st.button(
                "Apply the shipping fix",
                key="guide_fix",
                on_click=apply_guide_fix,
                args=(current.fix,),
            )
            if notice := st.session_state.pop("guide_notice", None):
                st.success(notice)
        if current.message:
            st.markdown(f"> {current.message}")
            st.button(
                "Send this message",
                key="guide_send",
                type="primary",
                on_click=queue_message,
                args=(current.message,),
            )
        back, forward = st.columns(2)
        back.button(
            "Back", key="guide_back", disabled=number == 1, on_click=go_to_step, args=(number - 1,)
        )
        if number < len(STEPS):
            forward.button("Next step", key="guide_next", on_click=go_to_step, args=(number + 1,))
        st.button("Exit the guide", key="guide_exit", on_click=exit_guide)


def landing_page() -> None:
    st.title("Merchant Support Agent")
    st.markdown(
        "An AI support agent for small online stores whose products Google Shopping has "
        "rejected. It finds what's wrong, explains Google's rule in plain words with a link to "
        "the help page, walks the merchant through the fix, and hands the cases it shouldn't "
        "handle to a person, with everything that person needs."
    )
    st.header("The problem")
    st.markdown(
        "When a product breaks a Google Shopping rule it stops showing in ads, and the store "
        "owner usually finds out because sales drop. The error messages are short and technical, "
        "the rules are spread over many help pages, and when a case does reach a support "
        "specialist the merchant has to explain everything again."
    )
    st.header("What you'll do in the demo")
    st.markdown(
        "\n".join(f"{n}. **{role}**: {text}" for n, (role, text) in enumerate(ROLES.items(), 1))
    )
    st.markdown("The guide takes about three minutes and tells you what to click at each step.")
    left, right = st.columns(2)
    left.button("Start the guided demo", key="start_guide", type="primary", on_click=start_guide)
    right.button("Explore on my own", key="explore", on_click=open_chat)
    st.caption(
        "The stores are simulated and nothing is sent to Google. Answers are generated live by "
        "Gemini and checked by an evaluation suite (see the README)."
    )
