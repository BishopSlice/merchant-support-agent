import pytest


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch, tmp_path):
    """No test writes to the real runtime/ folder (cases, events, web data). Tests that need
    a specific runtime folder set RUNTIME_DIR again themselves."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime-default"))
