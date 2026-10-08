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
