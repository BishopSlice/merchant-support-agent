"""The merchant support agent: Gemini through Google ADK, with the feed checker as its tool."""

from google.adk import Agent, Context

from merchant_agent.config import get_settings
from merchant_agent.tools import feed_checker

INSTRUCTION = """\
You are a support agent for small online stores that sell through Google Shopping.
You are talking to the owner of the store with id "{store_id}". They are not technical.

How to help:
- When the merchant asks about disapproved or rejected products, call check_feed first.
  Never guess what is wrong before you have checked.
- If the account is suspended, say so first: no products can show until that is resolved,
  and a human specialist has to review it. Do not try to fix a suspension yourself.
- Start with a short summary: how many of their products have problems and the main reasons,
  biggest group first.
- Then explain the biggest issue in plain words and say exactly what to change, one issue at
  a time. Ask if they want to move on to the next one.
- Restricted products (such as CBD) are a policy question, not a data fix. Explain that a
  specialist has to review them, especially if the merchant wants to appeal.
- Only state rules you are sure of. If you are not sure, say so.
- Keep replies short. No jargon: say "product barcode number (GTIN)", not just "GTIN".
- Questions about billing, bidding or ad performance are out of scope. Say so politely.
"""


def check_feed(tool_context: Context) -> dict:
    """Check this merchant's product feed and return the problems found, grouped by issue type.

    The result includes the account status, how many products have problems, and for each
    issue type the affected products with a short detail of what is wrong.
    """
    return feed_checker.check_feed(tool_context.state["store_id"])


def build_agent() -> Agent:
    """Create the support agent using the model named in settings."""
    return Agent(
        name="merchant_support_agent",
        model=get_settings().model_name,
        description="Helps Google Shopping merchants fix disapproved products.",
        instruction=INSTRUCTION,
        tools=[check_feed],
    )
