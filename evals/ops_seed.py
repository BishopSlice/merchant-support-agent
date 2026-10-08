"""Build the /ops seed baked into the hosted image: uv run python -m evals.ops_seed RUN.json...

Cloud Run scales to zero and starts with an empty runtime/ folder, so the dashboard would show
nothing until someone chats. The seed holds the release candidate's eval traffic and its AI
grades, labelled as eval traffic, so /ops has data from the first visit. Live traffic is never
in the seed.
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
        for case_id, record in run_file.runs.items():
            if record.status != "ok":
                continue
            log_events(store, record, run_file.price, run_label=path.stem)
            count += 1
            grade = run_file.grades.get(case_id)
            if grade and not grade.error:
                replies = grade.wrong_advice.replies if grade.wrong_advice else []
                wrong = (
                    sum(r.verdict == "unsupported" for r in replies) / len(replies)
                    if replies
                    else None
                )
                completeness = grade.completeness.verdict if grade.completeness else None
                store.record_grade(record.conversation_id, wrong, completeness, grade.cost_usd)
    return count


if __name__ == "__main__":
    print(f"{build_seed([Path(p) for p in sys.argv[1:]])} conversations -> {SEED_PATH}")
