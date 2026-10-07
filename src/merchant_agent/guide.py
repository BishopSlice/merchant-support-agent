"""Content for the app's guided demo: the roles a visitor plays and the steps of the walkthrough.

Kept as plain data so it can be tested and edited without touching the Streamlit layout.
"""

from dataclasses import dataclass

from merchant_agent.models import IssueType

PAGES = ("Start here", "Merchant chat", "Specialist inbox")

ROLES = {
    "Merchant": (
        "You own a small online home goods store. Some of your products stopped showing on "
        "Google Shopping and you want to know why."
    ),
    "Demo operator": (
        "You stand in for the merchant editing their product data, so the agent has a real "
        "change to check. A real merchant would do this in their own store."
    ),
    "Specialist": (
        "You work on Google's support team and pick up the cases the agent hands over, without "
        "having to ask the merchant to explain everything again."
    ),
}


@dataclass(frozen=True)
class Step:
    """One step of the guided demo."""

    number: int
    role: str
    page: str
    title: str
    body: str
    message: str = ""  # a merchant message the visitor can send with one click
    fix: IssueType | None = None  # a simulated merchant fix the visitor can apply


STEPS = (
    Step(
        1,
        "Merchant",
        "Merchant chat",
        "Ask what went wrong",
        "Send the message below. The agent checks your store's product feed and explains the "
        "problems in plain words, biggest first, with links to Google's help pages.",
        message="Half my products got disapproved yesterday, what happened?",
    ),
    Step(
        2,
        "Merchant",
        "Merchant chat",
        "See how the agent got its answer",
        "Open **What the agent did** under the reply. It lists every tool the agent used: the "
        "feed check and the help-doc search. The links in the reply are the help pages it relied "
        "on. It isn't allowed to state a rule no help page supports.",
    ),
    Step(
        3,
        "Demo operator",
        "Merchant chat",
        "Fix something, then tell the agent",
        "Click **Apply the shipping fix** to play the merchant adding the missing shipping costs "
        "to their product data. Then send the message. The agent checks the feed again before "
        "it answers.",
        message="I added the shipping info. Can you check again?",
        fix=IssueType.MISSING_SHIPPING,
    ),
    Step(
        4,
        "Merchant",
        "Merchant chat",
        "Disagree with a policy decision",
        "One product, a CBD candle, is blocked by a policy rather than a data problem. Send the "
        "message to appeal. The agent can't decide appeals, so it creates a case for a "
        "specialist, including your reasons.",
        message=(
            "About the CBD candle: it's a home fragrance product, not a supplement. "
            "I disagree with the decision and want to appeal."
        ),
    ),
    Step(
        5,
        "Specialist",
        "Specialist inbox",
        "Pick up the case",
        "You're now the specialist. The case the agent created is at the top of the inbox. It "
        "has the reason, the merchant's own arguments, the issues found, what was tried, a "
        "suggested next step and the help pages cited, so there's no need to contact the "
        "merchant again.",
    ),
    Step(
        6,
        "Specialist",
        "Specialist inbox",
        "That's the whole journey",
        "You saw the agent diagnose a feed, ground every rule in a help page, re-check after a "
        "fix, and hand a policy appeal to a person with a complete case. Use **Reset demo** to "
        "start again, or explore on your own: try the suspended store, or ask something off "
        "topic.",
    ),
)


def step(number: int) -> Step:
    """The step with this number, clamped to the first and last steps."""
    return STEPS[min(max(number, 1), len(STEPS)) - 1]
