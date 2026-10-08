import pytest


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch, tmp_path):
    """No test writes to the real runtime/ folder (cases, events, web data). Tests that need
    a specific runtime folder set RUNTIME_DIR again themselves."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime-default"))


@pytest.fixture(autouse=True)
def _no_real_model(monkeypatch):
    """The one-call path's default model function fails loudly in tests (ADR 0008)."""
    from merchant_agent import engine

    def refuse(model):
        def call(system, prompt):
            raise AssertionError("tests must not call the model; pass a fake answer function")

        return call

    monkeypatch.setattr(engine, "gemini_answer", refuse)

    def refuse_runner():
        raise AssertionError("tests must not call the model; pass a fake runner")

    monkeypatch.setattr(engine, "new_runner", refuse_runner)


@pytest.fixture(scope="session")
def test_spans():
    """One global tracer provider for the test session, collecting spans in memory."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture(autouse=True)
def _no_tracing_setup(monkeypatch):
    """The app and the eval command don't attach exporters in tests; tracing tests do."""
    monkeypatch.setenv("TRACING", "0")
