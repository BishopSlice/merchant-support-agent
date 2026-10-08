"""Build the /ops seed baked into the hosted image: uv run python -m evals.ops_seed RUN.json...

Cloud Run scales to zero and starts with an empty runtime/ folder, so the dashboard would show
nothing until someone chats. The seed holds the release candidate's eval traffic, labelled as
eval traffic, so /ops has data from the first visit. Live traffic is never in the seed.
"""

import sys
from pathlib import Path

from evals.run import RunFile
from evals.runner import log_events
from merchant_agent.config import PROJECT_ROOT
from merchant_agent.events import EventStore

SEED_PATH = PROJECT_ROOT / "deploy" / "ops-seed.sqlite"


def build_seed(paths: list[Path], out: Path = SEED_PATH) -> int:
    """Write a fresh seed from the given run files; return how many conversations it holds."""
    out.unlink(missing_ok=True)
    store = EventStore(out)
    count = 0
    for path in paths:
        run_file = RunFile.model_validate_json(path.read_text())
        for record in run_file.runs.values():
            if record.status == "ok":
                log_events(store, record, run_file.price, run_label=path.stem)
                count += 1
    return count


if __name__ == "__main__":
    print(f"{build_seed([Path(p) for p in sys.argv[1:]])} conversations -> {SEED_PATH}")
