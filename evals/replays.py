"""Record the replays the hosted demo plays without calling the model.

Each journey is a scripted conversation on the demo store the shell shows (sample-store),
played through the real agent with the same isolated runner as the evals. A replay is never
written by hand: it's saved from a real run, with the agent version, so a test can fail when
the agent changes and the replays go stale (SPEC, Evals f).

    uv run python -m evals.replays
"""

import asyncio
import json
import sys
from pathlib import Path

from evals.case_format import EvalCase
from evals.records import CaseRun
from evals.runner import run_case
from merchant_agent.agent import agent_version
from merchant_agent.chat import ToolCall, describe_tool_call
from merchant_agent.config import MODEL_PRICES, PROJECT_ROOT, get_settings

REPLAYS_DIR = PROJECT_ROOT / "replays"
DEMO_STORE = "sample-store"

# (id, title shown in the side panel, entry context or None, turns, whether it hands off)
JOURNEYS = [
    (
        "price-from-issue-row",
        "Fix a price mismatch, opened from its issue row",
        {"product": "HG-004", "issue_code": "price_mismatch"},
        [
            {"merchant": "How do I fix this?"},
            {
                "merchant": "Done, I've changed the prices to match my site.",
                "fix": "price_mismatch",
            },
        ],
        None,
    ),
    (
        "whats-wrong-overview",
        "Ask what's wrong, from Help",
        None,
        [{"merchant": "What's wrong with my products?"}],
        None,
    ),
    (
        "cbd-appeal-preview",
        "Appeal a policy disapproval and see the case preview",
        None,
        [
            {"merchant": "Why was my CBD candle disapproved?"},
            {
                "merchant": "It's a scented candle with no THC, so I think that's wrong. "
                "I'd like to appeal. What will the specialist see?"
            },
        ],
        "policy_appeal",
    ),
    (
        "ask-for-a-person",
        "Ask for a person",
        None,
        [{"merchant": "Can I talk to someone at Google about my account, please?"}],
        "merchant_requested_human",
    ),
]


def journey_case(replay_id: str, entry, turns, handoff_reason) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": f"replay-{replay_id}",
            "category": "multi_issue",
            "store": DEMO_STORE,
            "description": "Replay recording",
            "turns": turns,
            "entry_context": entry,
            "expect": {
                "should_handoff": handoff_reason is not None,
                "handoff_reason": handoff_reason,
            },
        }
    )


def to_replay(replay_id: str, title: str, case: EvalCase, record: CaseRun, version: str) -> dict:
    """Turn a recorded run into what the side panel plays back."""
    turns = []
    for scripted, turn in zip(case.turns, record.turns, strict=True):
        calls = [ToolCall(name=c.name, args=c.args, response=c.response) for c in turn.tool_calls]
        created = [
            c.response
            for c in calls
            if c.name == "create_handoff_case"
            and isinstance(c.response, dict)
            and c.response.get("status") == "created"
        ]
        turns.append(
            {
                "merchant": scripted.merchant,
                "fix": scripted.fix.value if scripted.fix else None,
                "steps": [describe_tool_call(c) for c in calls],
                "reply": turn.reply,
                "case": created[-1] if created else None,
                "seconds": turn.seconds,
            }
        )
    return {
        "id": replay_id,
        "title": title,
        "agent_version": version,
        "model": get_settings().model_name,
        "store": case.store,
        "entry_context": case.entry_context.model_dump(mode="json") if case.entry_context else None,
        "turns": turns,
    }


def record_all(out_dir: Path = REPLAYS_DIR, run=run_case) -> list[Path]:
    """Record every journey; a journey whose run errors is reported and not saved."""
    out_dir.mkdir(parents=True, exist_ok=True)
    price = MODEL_PRICES[get_settings().model_name]
    saved = []
    for replay_id, title, entry, turns, reason in JOURNEYS:
        case = journey_case(replay_id, entry, turns, reason)
        record = asyncio.run(run(case, price))
        if record.status != "ok":
            print(f"{replay_id}: not saved ({record.error[:80]})", file=sys.stderr)
            continue
        path = out_dir / f"{replay_id}.json"
        path.write_text(
            json.dumps(to_replay(replay_id, title, case, record, agent_version()), indent=1)
        )
        saved.append(path)
        print(f"{replay_id}: saved ({record.cost_usd:.4f} USD)")
    return saved


if __name__ == "__main__":
    record_all()
