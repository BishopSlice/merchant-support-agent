"""Step-by-step tracing (Task 21b): spans per turn, step and tool, stored without prompts."""

import asyncio
import json
import sqlite3

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from merchant_agent.events import EventStore
from merchant_agent.tracing import EventStoreExporter


@pytest.fixture
def spans(test_spans):
    """Spans finished during the test, from the test tracer provider (see conftest)."""
    test_spans.clear()
    return test_spans


def tracer_with(exporter):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test")


def test_exported_spans_drop_prompt_content_and_mask_contact_details(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    tracer = tracer_with(EventStoreExporter(store))
    with tracer.start_as_current_span("call_llm") as span:
        span.set_attribute("app.conversation_id", "c1")
        span.set_attribute("gcp.vertex.agent.llm_request", '{"prompt": "secret"}')
        span.set_attribute("gen_ai.input.messages", "hello")
        span.set_attribute("app.note", "mail jo@example.com")
    [(name, conversation, attributes, duration)] = (
        sqlite3.connect(store.path)
        .execute("select name, conversation_id, attributes, duration_ms from spans")
        .fetchall()
    )
    attributes = json.loads(attributes)
    assert name == "call_llm" and conversation == "c1" and duration >= 0
    assert "gcp.vertex.agent.llm_request" not in attributes
    assert "gen_ai.input.messages" not in attributes
    assert attributes["app.note"] == "mail [email]"


def test_prompt_capture_can_be_turned_on(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    tracer = tracer_with(EventStoreExporter(store, capture_prompts=True))
    with tracer.start_as_current_span("call_llm") as span:
        span.set_attribute("gcp.vertex.agent.llm_request", "ask jo@example.com")
    [(attributes,)] = sqlite3.connect(store.path).execute("select attributes from spans").fetchall()
    assert json.loads(attributes)["gcp.vertex.agent.llm_request"] == "ask [email]"


def test_a_one_call_turn_is_traced_step_by_step(spans):
    from test_engine import FakeAnswer

    from merchant_agent.engine import Conversation

    conversation = Conversation(
        "sample-store",
        answer=FakeAnswer(),
        trace={"conversation_id": "c9", "traffic_source": "eval", "entry_point": "help"},
    )
    asyncio.run(conversation.ask("What's wrong?"))
    finished = {s.name: s for s in spans.get_finished_spans()}
    assert {"turn", "preload", "tool.list_products", "model_call"} <= set(finished)
    turn = finished["turn"]
    assert turn.attributes["app.conversation_id"] == "c9"
    assert turn.attributes["app.traffic_source"] == "eval"
    assert turn.attributes["app.path"] == "one_call"
    assert turn.attributes["app.model_calls"] == 1
    assert finished["preload"].parent.span_id == turn.context.span_id
    assert finished["tool.list_products"].parent.span_id == finished["preload"].context.span_id
    assert finished["model_call"].parent.span_id == turn.context.span_id


def test_the_trace_view_lists_each_turns_steps_with_timings(tmp_path):
    from merchant_agent.ops import trace

    store = EventStore(tmp_path / "events.sqlite")
    conversation = store.start_conversation(
        source="live", store_id="s", agent_version="a", model="m", conversation_id="c1"
    )
    tracer = tracer_with(EventStoreExporter(store))
    with tracer.start_as_current_span("turn") as span:
        span.set_attribute("app.conversation_id", conversation)
        with (
            tracer.start_as_current_span("preload"),
            tracer.start_as_current_span("tool.list_products"),
        ):
            pass
        with tracer.start_as_current_span("model_call"):
            pass
    [steps] = trace(store, conversation)["steps"]
    assert [(s["name"], s["depth"]) for s in steps] == [
        ("turn", 0),
        ("preload", 1),
        ("tool.list_products", 2),
        ("model_call", 1),
    ]
    assert all(s["duration_ms"] >= 0 for s in steps)


__all__ = ["InMemorySpanExporter"]
