"""Step-by-step tracing with OpenTelemetry (SPEC, Observability; Task 21b).

Each turn is a "turn" span holding "preload" (one span per tool), "model_call" and "handoff"
spans, or, on the fallback path, ADK's own spans. Spans are tagged with the conversation, the
agent version, the entry point and the traffic source, and are written to the event store
in the background, off the merchant's wait.

Prompts and responses are not stored unless CAPTURE_PROMPTS=1, and everything stored is
masked. Exporting to Cloud Trace later would be another span processor.
"""

import json
import os
from collections.abc import Sequence

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from merchant_agent.events import EventStore, mask

TRACER_NAME = "merchant_agent"
# Attributes that carry prompts, model output or tool payloads.
CONTENT_MARKERS = (
    "llm_request",
    "llm_response",
    "tool_call_args",
    "tool_response",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.prompt",
    "gen_ai.completion",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
)


def tracer() -> trace.Tracer:
    return trace.get_tracer(TRACER_NAME)


def _is_content(key: str) -> bool:
    return any(marker in key for marker in CONTENT_MARKERS)


class EventStoreExporter(SpanExporter):
    """Writes finished spans into the event store's spans table."""

    def __init__(self, store: EventStore, capture_prompts: bool = False) -> None:
        self.store = store
        self.capture_prompts = capture_prompts

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        rows = []
        for span in spans:
            attributes = {}
            for key, value in (span.attributes or {}).items():
                if _is_content(key) and not self.capture_prompts:
                    continue
                attributes[key] = mask(value) if isinstance(value, str) else value
            context = span.get_span_context()
            rows.append(
                (
                    format(context.trace_id, "032x"),
                    format(context.span_id, "016x"),
                    format(span.parent.span_id, "016x") if span.parent else None,
                    span.name,
                    attributes.get("app.conversation_id"),
                    span.start_time,
                    round((span.end_time - span.start_time) / 1e6, 2),
                    json.dumps(attributes, default=str),
                )
            )
        self.store.record_spans(rows)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def setup_tracing(store: EventStore, capture_prompts: bool | None = None) -> None:
    """Send spans to the event store. Off when TRACING=0 (tests)."""
    if os.environ.get("TRACING") == "0":
        return
    if capture_prompts is None:
        capture_prompts = os.environ.get("CAPTURE_PROMPTS") == "1"
    if not capture_prompts:
        os.environ["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] = "false"
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(
            resource=Resource.create({"service.name": "merchant-support-agent"})
        )
        trace.set_tracer_provider(provider)
    provider.add_span_processor(BatchSpanProcessor(EventStoreExporter(store, capture_prompts)))


def flush() -> None:
    """Write any spans still waiting, for example before an eval command exits."""
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.force_flush()
