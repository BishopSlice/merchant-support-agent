"""The container must include every module the web app imports at run time."""

import re

from merchant_agent.config import PROJECT_ROOT


def _imported_eval_modules() -> set[str]:
    """evals modules reachable from the web app, following imports within evals."""
    sources = [*(PROJECT_ROOT / "src/merchant_agent").rglob("*.py")]
    seen, queue = set(), []
    for path in sources:
        queue += re.findall(r"^from evals\.(\w+) import", path.read_text(), re.MULTILINE)
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        text = (PROJECT_ROOT / "evals" / f"{module}.py").read_text()
        queue += re.findall(r"^from evals\.(\w+) import", text, re.MULTILINE)
    return seen


def test_dockerfile_copies_every_eval_module_the_app_uses():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    for module in _imported_eval_modules():
        assert f"evals/{module}.py" in dockerfile, f"Dockerfile misses evals/{module}.py"


def test_secrets_stay_out_of_the_image():
    ignored = (PROJECT_ROOT / ".dockerignore").read_text().split()
    assert ".env" in ignored and "runtime" in ignored
    assert "GOOGLE_API_KEY=" not in (PROJECT_ROOT / "Dockerfile").read_text()


def test_the_image_includes_the_replays_and_the_ops_seed():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    assert "COPY replays" in dockerfile
    assert "deploy/ops-seed.sqlite" in dockerfile
