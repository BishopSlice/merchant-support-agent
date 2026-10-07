"""Run the Checkpoint B journeys against Gemini and save each as a transcript.

uv run python scripts/run_checkpoint_b.py [scenario ...]

Each scenario runs on a temporary demo copy of data/ and a temporary runtime/, so the
repo's store files and cases are never touched. When the merchant says they fixed
something, the script first applies that fix to the copy (see merchant_agent.demo).
Any handoff cases are appended to the transcript as JSON.
"""

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path

from google.adk.runners import InMemoryRunner

from merchant_agent.agent import build_agent
from merchant_agent.cli import APP_NAME, USER_ID, Transcript, send
from merchant_agent.config import PROJECT_ROOT, get_settings
from merchant_agent.demo import apply_fix, prepare_demo_data
from merchant_agent.models import IssueType
from merchant_agent.tools.handoff import list_cases

TRANSCRIPTS_DIR = PROJECT_ROOT / "docs" / "transcripts"

# Each turn: an issue the merchant fixed just before sending it (or None), and the message.
Turn = tuple[IssueType | None, str]

SCENARIOS: dict[str, tuple[str, list[Turn]]] = {
    "fix-then-appeal": (
        "sample-store",
        [
            (None, "Half my products got disapproved yesterday, what happened?"),
            (IssueType.MISSING_SHIPPING, "I added the shipping info. Can you check again?"),
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
                IssueType.PRICE_MISMATCH,
                "OK, I changed the prices in my feed to match my website. Is that sorted now?",
            ),
        ],
    ),
}


async def run_scenario(name: str) -> Path:
    """Run one scenario in a temp copy of the data and save its transcript."""
    store_id, turns = SCENARIOS[name]
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["RUNTIME_DIR"] = str(Path(tmp) / "runtime")
        os.environ.pop("DATA_DIR", None)
        os.environ["DATA_DIR"] = str(prepare_demo_data())

        runner = InMemoryRunner(agent=build_agent(), app_name=APP_NAME)
        session = await runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, state={"store_id": store_id}
        )
        transcript = Transcript(store_id, get_settings().model_name)
        try:
            for fixed, text in turns:
                if fixed:
                    ids = apply_fix(store_id, fixed)
                    transcript.lines += [
                        f"_Simulated merchant fix: {fixed.value} on {', '.join(ids)}._",
                        "",
                    ]
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
