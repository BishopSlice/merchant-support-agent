"""Run the Checkpoint B journeys against Gemini and save each as a transcript.

uv run python scripts/run_checkpoint_b.py [scenario ...]

Each scenario runs on a temporary copy of data/ and runtime/, so the repo's store
files and cases are never touched. When the merchant says they fixed something,
the script first edits that copy of the feed, to stand in for the merchant's fix.
Any handoff cases are appended to the transcript as JSON.
"""

import argparse
import asyncio
import csv
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from google.adk.runners import InMemoryRunner

from merchant_agent.agent import build_agent
from merchant_agent.cli import APP_NAME, USER_ID, Transcript, send
from merchant_agent.config import PROJECT_ROOT, get_settings
from merchant_agent.tools.handoff import list_cases

TRANSCRIPTS_DIR = PROJECT_ROOT / "docs" / "transcripts"

FeedEdit = Callable[[Path], None]


def edit_feed(store_id: str, column: str, values: dict[str, str]) -> FeedEdit:
    """Return a step that sets one column for some products in a store's feed copy."""

    def apply(data_dir: Path) -> None:
        path = data_dir / "stores" / store_id / "feed.csv"
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row["id"] in values:
                row[column] = values[row["id"]]
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    apply.__name__ = f"set {column} on {', '.join(values)}"
    return apply


Turn = tuple[FeedEdit | None, str]

SCENARIOS: dict[str, tuple[str, list[Turn]]] = {
    "fix-then-appeal": (
        "sample-store",
        [
            (None, "Half my products got disapproved yesterday, what happened?"),
            (
                edit_feed(
                    "sample-store", "shipping", {"HG-019": "US:::5.95 USD", "HG-030": "US:::5.95 USD"}
                ),
                "I added the shipping info. Can you check again?",
            ),
            (
                None,
                (
                    "What about the CBD candle? It's just a candle, I think that decision is "
                    "wrong and I want to appeal it."
                ),
            ),
        ],
    ),
    "suspended": (
        "suspended-store",
        [(None, "None of my products are showing on Google anymore. What's going on?")],
    ),
    "plain-fix": (
        "sample-store",
        [
            (None, "Some of my products got disapproved. What's wrong?"),
            (
                edit_feed(
                    "sample-store",
                    "price",
                    {"HG-004": "36.00 USD", "HG-015": "64.00 USD", "HG-021": "44.00 USD"},
                ),
                "OK, I changed the prices in my feed to match my website. Is that sorted now?",
            ),
        ],
    ),
}


async def run_scenario(name: str) -> Path:
    """Run one scenario in a temp copy of the data and save its transcript."""
    store_id, turns = SCENARIOS[name]
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        shutil.copytree(PROJECT_ROOT / "data", data_dir)
        os.environ["DATA_DIR"] = str(data_dir)
        os.environ["RUNTIME_DIR"] = str(Path(tmp) / "runtime")

        runner = InMemoryRunner(agent=build_agent(), app_name=APP_NAME)
        session = await runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, state={"store_id": store_id}
        )
        transcript = Transcript(store_id, get_settings().model_name)
        try:
            for feed_edit, text in turns:
                if feed_edit:
                    feed_edit(data_dir)
                    transcript.lines += [f"_Simulated merchant fix: {feed_edit.__name__}._", ""]
                print(f"\nyou> {text}")
                transcript.add("Merchant", text)
                reply = await send(runner, session.id, text, transcript)
                transcript.add("Agent", reply)
                print(f"\nagent> {reply}")
        finally:
            await runner.close()

        cases = [json.loads(case.model_dump_json()) for case in list_cases()]
        transcript.lines += ["## Saved cases", ""]
        if cases:
            transcript.lines += ["```json", json.dumps(cases, indent=2), "```", ""]
        else:
            transcript.lines += ["None.", ""]

    path = TRANSCRIPTS_DIR / f"checkpoint-b-{name}.md"
    transcript.save(path)
    print(f"\nSaved {path.relative_to(PROJECT_ROOT)} ({len(cases)} case(s))")
    return path


def main() -> None:
    """Run the named scenarios, or all of them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenarios", nargs="*", help=f"any of: {', '.join(SCENARIOS)}")
    names = parser.parse_args().scenarios or list(SCENARIOS)
    unknown = [name for name in names if name not in SCENARIOS]
    if unknown:
        parser.error(f"unknown scenario(s): {', '.join(unknown)}")
    for name in names:
        asyncio.run(run_scenario(name))


if __name__ == "__main__":
    main()
