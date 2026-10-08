"""The one-call path (ADR 0008): code loads the context, the model answers once."""

import asyncio

from merchant_agent.answer import Answer, HandoffRequest
from merchant_agent.chat import Usage
from merchant_agent.engine import Conversation
from merchant_agent.merchant_api import product_name


class FakeAnswer:
    """Records each prompt and returns a canned answer: one model call per turn."""

    def __init__(self, *answers: Answer) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def __call__(self, system: str, prompt: str):
        self.systems.append(system)
        self.prompts.append(prompt)
        answer = self.answers.pop(0) if self.answers else Answer(reply="ok")
        return answer, Usage(model_calls=1, input_tokens=5000, output_tokens=300)


class FakeLoop:
    """A tool-loop runner that must only be used on the fallback path."""

    used = 0

    def __init__(self):
        from google.adk.sessions import InMemorySessionService

        self.session_service = InMemorySessionService()

    async def run_async(self, *, user_id, session_id, new_message):
        from google.adk import Event
        from google.genai import types

        FakeLoop.used += 1
        yield Event(
            author="agent",
            content=types.Content(role="model", parts=[types.Part(text="loop reply")]),
        )

    async def close(self):
        pass


def ask(conversation, *messages):
    async def run():
        return [await conversation.ask(m) for m in messages]

    return asyncio.run(run())


def names(turn, by=None):
    return [c.name for c in turn.tool_calls if by is None or c.by == by]


def test_a_store_question_is_answered_in_one_call_with_context_loaded_by_code():
    fake = FakeAnswer(Answer(reply="Here's what's wrong."))
    [turn] = ask(Conversation("sample-store", answer=fake), "What's wrong with my products?")
    assert turn.path == "one_call" and turn.usage.model_calls == 1
    assert len(fake.prompts) == 1
    for tool in [
        "list_account_issues",
        "list_aggregate_product_statuses",
        "list_products",
        "get_automatic_improvements",
        "search_help_docs",
    ]:
        assert tool in names(turn, by="code")
    prompt = fake.prompts[0]
    assert "HG-004" in prompt and "price_mismatch" in prompt
    assert "automatic price updates: off" in prompt
    assert "source_url: https://support.google.com/merchants/answer/12159029" in prompt
    assert "{store_id}" not in fake.systems[0] and "sample-store" in fake.systems[0]


def test_docs_given_to_the_model_are_recorded_as_retrieved_for_the_grader():
    [turn] = ask(Conversation("sample-store", answer=FakeAnswer()), "What's wrong?")
    retrieved = {
        r["doc_id"]
        for c in turn.tool_calls
        if c.name == "search_help_docs"
        for r in c.response["results"]
    }
    assert {
        "price-mismatch",
        "automatic-item-updates",
        "gtin",
        "cbd-unapproved-substances",
    } <= retrieved


def test_an_issue_row_loads_that_product_and_says_not_to_ask_which_one():
    entry = {"product_name": product_name("sample-store", "HG-004"), "issue_code": "price_mismatch"}
    fake = FakeAnswer()
    [turn] = ask(Conversation("sample-store", entry, answer=fake), "Hmm?")
    [call] = [c for c in turn.tool_calls if c.name == "get_product_by_name"]
    assert call.args == {"name": entry["product_name"]}
    assert "don't ask which one" in fake.prompts[0]


def test_a_handoff_is_saved_by_code_and_its_number_goes_into_the_reply():
    from merchant_agent.tools.handoff import list_cases

    request = HandoffRequest(
        reason="merchant_requested_human",
        merchant_request="Talk to a person",
        suggested_next_step="Call back",
    )
    fake = FakeAnswer(
        Answer(reply="Passed on. Your case number is {CASE_NUMBER}.", handoff=request)
    )
    [turn] = ask(Conversation("sample-store", answer=fake), "I want a human")
    [case] = list_cases()
    assert case.case_id in turn.reply and "{CASE_NUMBER}" not in turn.reply
    [call] = [c for c in turn.tool_calls if c.name == "create_handoff_case"]
    assert call.by == "code" and call.response["preview"]["reason"] == "merchant_requested_human"
    assert turn.usage.model_calls == 1


def test_an_unrelated_question_falls_back_to_the_tool_loop_and_is_recorded():
    FakeLoop.used = 0
    fake = FakeAnswer()
    conversation = Conversation("sample-store", runner_factory=FakeLoop, answer=fake)
    [turn] = ask(conversation, "Can you recommend a good pizza place nearby?")
    assert turn.path == "fallback" and turn.reply == "loop reply"
    assert FakeLoop.used == 1 and fake.prompts == []


def test_follow_ups_stay_on_the_one_call_path_and_see_the_conversation():
    fake = FakeAnswer(Answer(reply="First answer"), Answer(reply="Second answer"))
    first, second = ask(Conversation("sample-store", answer=fake), "What's wrong?", "ok thanks!")
    assert (first.path, second.path) == ("one_call", "one_call")
    assert "Merchant: What's wrong?" in fake.prompts[1] and "You: First answer" in fake.prompts[1]


def test_a_failed_preload_is_shown_as_not_loaded(monkeypatch):
    from merchant_agent.data import FailingMerchantData
    from merchant_agent.tools import merchant_tools

    failing = FailingMerchantData(merchant_tools.merchant_data, "list_products", "timeout")
    monkeypatch.setattr(merchant_tools, "merchant_data", failing)
    fake = FakeAnswer()
    [turn] = ask(Conversation("sample-store", answer=fake), "Which products are broken?")
    assert "list_products: COULD NOT BE LOADED" in fake.prompts[0]
    [call] = [c for c in turn.tool_calls if c.name == "list_products"]
    assert "error" in call.response


def test_descriptions_and_product_types_never_reach_the_prompt():
    fake = FakeAnswer()
    ask(Conversation("sample-store", answer=fake), "What's wrong?")
    assert "Made for everyday use at home" not in fake.prompts[0]  # a description
    assert "Home & Garden >" not in fake.prompts[0]  # a product type


def test_without_an_answer_function_every_turn_uses_the_tool_loop():
    FakeLoop.used = 0
    [turn] = ask(
        Conversation("sample-store", runner_factory=FakeLoop, answer=None), "What's wrong?"
    )
    assert turn.path == "tool_loop" and FakeLoop.used == 1


def test_one_call_answers_use_the_lower_thinking_level():
    from google.genai import types

    from merchant_agent import answer

    assert answer.THINKING_LEVEL == types.ThinkingLevel.LOW


def test_the_instructions_summarise_product_issues_after_a_suspension():
    from merchant_agent.answer import ANSWER_INSTRUCTION

    text = " ".join(ANSWER_INSTRUCTION.lower().split())
    assert "after the suspension, also give the short summary of the product issues" in text
