import asyncio

from google.adk import Event
from google.genai import types

from merchant_agent.chat import ChatSession, ToolCall, Turn, describe_tool_call, run_turn


class FakeRunner:
    """Stands in for an ADK runner by replaying a fixed list of events."""

    def __init__(self, events: list[Event]) -> None:
        self.events = events
        self.received: list[str] = []

    async def run_async(self, *, user_id, session_id, new_message):
        self.received.append(new_message.parts[0].text)
        for event in self.events:
            yield event


def event(*parts: types.Part) -> Event:
    return Event(author="merchant_support_agent", content=types.Content(role="model", parts=parts))


def call_part(name: str, args: dict) -> types.Part:
    return types.Part(function_call=types.FunctionCall(id="c1", name=name, args=args))


def response_part(name: str, response: dict) -> types.Part:
    return types.Part(function_response=types.FunctionResponse(id="c1", name=name, response=response))


def test_run_turn_collects_reply_and_tool_calls():
    runner = FakeRunner(
        [
            event(call_part("search_help_docs", {"query": "missing_gtin"})),
            event(response_part("search_help_docs", {"results": []})),
            event(types.Part(text="Here is what I found.")),
        ]
    )
    turn = asyncio.run(run_turn(runner, "session-1", "What happened?"))
    assert runner.received == ["What happened?"]
    assert turn.reply == "Here is what I found."
    assert turn.tool_calls == [
        ToolCall(name="search_help_docs", args={"query": "missing_gtin"}, response={"results": []})
    ]


def test_run_turn_ignores_thoughts_and_text_from_unfinished_events():
    thinking = types.Part(text="Let me think about GTINs...", thought=True)
    partial = Event(
        author="merchant_support_agent",
        content=types.Content(role="model", parts=[types.Part(text="Checking")]),
        partial=True,
    )
    runner = FakeRunner([event(thinking), partial, event(types.Part(text="Final answer."))])
    turn = asyncio.run(run_turn(runner, "session-1", "Hi"))
    assert turn.reply == "Final answer."


def test_turn_lists_created_case_ids():
    turn = Turn(
        reply="Done",
        tool_calls=[
            ToolCall(name="check_feed", args={}, response={}),
            ToolCall(
                name="create_handoff_case",
                args={},
                response={"status": "created", "case_id": "CASE-1"},
            ),
            ToolCall(name="create_handoff_case", args={}, response={"status": "error"}),
        ],
    )
    assert turn.case_ids == ["CASE-1"]


def test_describe_check_feed():
    call = ToolCall(
        name="check_feed",
        args={},
        response={"disapproved_products": 13, "limited_products": 5, "account_status": "active"},
    )
    assert describe_tool_call(call) == (
        "Checked the product feed: 13 disapproved, 5 with limited reach."
    )


def test_describe_check_feed_on_suspended_account():
    call = ToolCall(
        name="check_feed",
        args={},
        response={"disapproved_products": 0, "limited_products": 0, "account_status": "suspended"},
    )
    assert "account is suspended" in describe_tool_call(call)


def test_describe_help_search_names_the_docs_found():
    call = ToolCall(
        name="search_help_docs",
        args={"query": "missing_gtin"},
        response={"results": [{"title": "Product barcode number (GTIN)"}] * 2},
    )
    assert describe_tool_call(call) == (
        'Searched the help docs for "missing_gtin": found Product barcode number (GTIN).'
    )


def test_describe_help_search_with_no_results():
    call = ToolCall(name="search_help_docs", args={"query": "bids"}, response={"results": []})
    assert describe_tool_call(call) == 'Searched the help docs for "bids": no matching doc.'


def test_describe_handoff():
    call = ToolCall(
        name="create_handoff_case",
        args={"reason": "policy_appeal"},
        response={"status": "created", "case_id": "CASE-1"},
    )
    assert describe_tool_call(call) == "Handed off to a specialist: case CASE-1 (policy_appeal)."


def test_describe_failed_handoff():
    call = ToolCall(
        name="create_handoff_case",
        args={"reason": "x"},
        response={"status": "error", "message": "Case not saved. reason: bad"},
    )
    assert describe_tool_call(call) == "Tried to create a case, but: Case not saved. reason: bad"


class FakeRunnerWithSessions(FakeRunner):
    def __init__(self, events):
        super().__init__(events)
        from google.adk.sessions import InMemorySessionService

        self.session_service = InMemorySessionService()
        self.closed = False

    async def close(self):
        self.closed = True


def test_chat_session_runs_turns_from_synchronous_code():
    runner = FakeRunnerWithSessions([event(types.Part(text="Hello"))])
    chat = ChatSession("sample-store", runner=runner)
    assert chat.send("hi").reply == "Hello"
    assert chat.send("again").reply == "Hello"
    assert runner.received == ["hi", "again"]
    chat.close()
    assert runner.closed
