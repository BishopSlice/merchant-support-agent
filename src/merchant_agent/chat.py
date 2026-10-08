"""Run conversation turns through the ADK runner, for both the terminal and the web app."""

import asyncio
import threading
import time
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

from google.adk import Runner
from google.adk.runners import InMemoryRunner
from google.genai import types

from merchant_agent.agent import build_agent

APP_NAME = "merchant_support"
USER_ID = "merchant"


@dataclass
class ToolCall:
    """One tool the agent called during a turn, with its arguments and result."""

    name: str
    args: dict
    response: Any
    by: str = "model"  # "code" when code made the call itself (ADR 0008)


@dataclass
class Usage:
    """Tokens used by model calls. Output includes thinking tokens, which are billed as output."""

    model_calls: int = 0
    input_tokens: int = 0  # all prompt tokens, including the cached ones
    cached_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.model_calls + other.model_calls,
            self.input_tokens + other.input_tokens,
            self.cached_tokens + other.cached_tokens,
            self.output_tokens + other.output_tokens,
        )

    @classmethod
    def from_metadata(cls, metadata: types.GenerateContentResponseUsageMetadata) -> "Usage":
        """Read one model call's token counts."""
        return cls(
            model_calls=1,
            input_tokens=metadata.prompt_token_count or 0,
            cached_tokens=metadata.cached_content_token_count or 0,
            output_tokens=(metadata.candidates_token_count or 0)
            + (metadata.thoughts_token_count or 0),
        )


@dataclass
class Turn:
    """The agent's reply to one merchant message, plus the tools it used to get there."""

    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    seconds: float = 0.0  # wall-clock time for the whole turn
    path: str = "tool_loop"  # "one_call", "fallback" (tool loop after the pre-step) or "tool_loop"

    @property
    def case_ids(self) -> list[str]:
        """Ids of handoff cases created during this turn."""
        return [
            call.response["case_id"]
            for call in self.tool_calls
            if call.name == "create_handoff_case"
            and isinstance(call.response, dict)
            and call.response.get("status") == "created"
        ]


def new_runner() -> InMemoryRunner:
    """Create a runner for the support agent, with sessions kept in memory."""
    return InMemoryRunner(agent=build_agent(), app_name=APP_NAME)


def entry_note(entry_context: dict | None) -> str:
    """One line for the agent's instructions saying where the merchant opened the chat."""
    if not entry_context:
        return "The merchant opened this chat from Help, not from a specific issue."
    return (
        "The merchant opened this chat from the issue row for product "
        f"{entry_context['product_name']} (issue code {entry_context['issue_code']})."
    )


async def new_session(runner: Runner, store_id: str, extra_state: dict | None = None) -> str:
    """Start a conversation as the owner of a store and return its session id.

    extra_state can carry "entry_context" ({product_name, issue_code}) when the side panel was
    opened from an issue row; the agent sees it as the "entry_note" line in its instructions.
    """
    state = {"store_id": store_id, **(extra_state or {})}
    state["entry_note"] = entry_note(state.get("entry_context"))
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state=state
    )
    return session.id


async def run_turn(runner: Runner, session_id: str, text: str) -> Turn:
    """Send one merchant message through the runner and collect the reply and tool calls."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    pending: dict[str, tuple[str, dict]] = {}
    turn = Turn(reply="")
    started = time.monotonic()
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        if event.usage_metadata:
            turn.usage += Usage.from_metadata(event.usage_metadata)
        for part in (event.content.parts if event.content else None) or []:
            if part.function_call:
                call = part.function_call
                pending[call.id or call.name] = (call.name, dict(call.args or {}))
            elif part.function_response:
                result = part.function_response
                name, args = pending.pop(result.id or result.name, (result.name, {}))
                turn.tool_calls.append(ToolCall(name=name, args=args, response=result.response))
            elif part.text and not part.thought and event.is_final_response():
                turn.reply += part.text
    turn.seconds = round(time.monotonic() - started, 2)
    return turn


def describe_tool_call(call: ToolCall) -> str:
    """Say in one plain sentence what a tool call did, for showing to a person."""
    response = call.response if isinstance(call.response, dict) else {}
    if "error" in response:
        return f"Tried {call.name}, but it failed: {response['error']}"
    if call.name == "check_feed":
        if response.get("account_status") == "suspended":
            return "Checked the product feed: the account is suspended."
        return (
            f"Checked the product feed: {response.get('disapproved_products', 0)} disapproved, "
            f"{response.get('limited_products', 0)} with limited reach."
        )
    if call.name == "list_aggregate_product_statuses":
        statuses = response.get("aggregateProductStatuses") or [{}]
        disapproved = statuses[0].get("stats", {}).get("disapprovedCount", "0")
        kinds = len(statuses[0].get("itemLevelIssues", []))
        return f"Checked product statuses: {disapproved} disapproved, {kinds} kinds of issue."
    if call.name == "list_products":
        count = len(response.get("products", []))
        if code := call.args.get("issue_code"):
            return f'Listed products with "{code}": {count} found.'
        return f"Listed all products: {count} found."
    if call.name == "get_product_by_name":
        return f"Looked up product {call.args.get('name', '').split('~')[-1]}."
    if call.name == "list_account_issues":
        titles = [issue.get("title", "") for issue in response.get("accountIssues", [])]
        return f"Checked account issues: {', '.join(titles) or 'none'}."
    if call.name == "get_automatic_improvements":
        updates = response.get("itemUpdates", {})

        def state(key: str) -> str:
            return "on" if updates.get(key) else "off"

        return (
            "Checked automatic improvements: "
            f"price updates {state('effectiveAllowPriceUpdates')}, "
            f"availability updates {state('effectiveAllowAvailabilityUpdates')}."
        )
    if call.name == "search_help_docs":
        query = call.args.get("query", "")
        titles = list(dict.fromkeys(r["title"] for r in response.get("results", [])))
        if query.startswith("(docs for"):  # the one-call preload (ADR 0008)
            return f"Loaded {len(titles)} help docs for the store's issues."
        if not titles:
            return f'Searched the help docs for "{query}": no matching doc.'
        return f'Searched the help docs for "{query}": found {", ".join(titles)}.'
    if call.name == "create_handoff_case":
        if response.get("status") == "created":
            reason = call.args.get("reason", "")
            return f"Handed off to a specialist: case {response['case_id']} ({reason})."
        return f"Tried to create a case, but: {response.get('message', 'unknown error')}"
    return f"Called {call.name}."


class ChatSession:
    """A conversation with the agent for one store, usable from synchronous code.

    The runner lives on its own event loop in a background thread, so a web app that
    reruns its script on every click can keep one conversation going.
    """

    def __init__(self, store_id: str, runner: Runner | None = None) -> None:
        self.store_id = store_id
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._runner = runner or new_runner()
        self._session_id = self._run(new_session(self._runner, store_id))

    def _run(self, coroutine: Coroutine) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    def send(self, text: str) -> Turn:
        """Send one merchant message and wait for the agent's reply."""
        return self._run(run_turn(self._runner, self._session_id, text))

    def close(self) -> None:
        """Shut down the runner and its background event loop."""
        self._run(self._runner.close())
        self._loop.call_soon_threadsafe(self._loop.stop)
