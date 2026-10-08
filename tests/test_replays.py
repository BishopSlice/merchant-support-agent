"""Replays: recorded from real runs, and stale replays fail this test (SPEC, Evals f)."""

import json

import pytest

from evals import replays
from evals.records import CaseRun, ToolCallRecord, TurnRecord
from merchant_agent.agent import agent_version

RECORDED = sorted(replays.REPLAYS_DIR.glob("*.json")) if replays.REPLAYS_DIR.is_dir() else []


@pytest.mark.parametrize("path", RECORDED, ids=lambda p: p.stem)
def test_every_replay_matches_the_current_agent_version(path):
    replay = json.loads(path.read_text())
    assert replay["agent_version"] == agent_version(), (
        f"{path.name} is stale: re-record with `uv run python -m evals.replays`"
    )
    assert replay["id"] == path.stem and replay["turns"]
    assert all(turn["reply"] for turn in replay["turns"])


def test_every_journey_has_a_recorded_replay():
    recorded = {p.stem for p in RECORDED}
    expected = {journey[0] for journey in replays.JOURNEYS}
    missing = expected - recorded
    if recorded:  # before the first recording there is nothing to check
        assert not missing, f"missing replays: {sorted(missing)}"


def fake_run(case, price):
    async def run():
        turns = []
        for scripted in case.turns:
            calls = [ToolCallRecord(name="list_aggregate_product_statuses", args={}, response={})]
            if case.expect.should_handoff and scripted is case.turns[-1]:
                calls.append(
                    ToolCallRecord(
                        name="create_handoff_case",
                        args={"reason": case.expect.handoff_reason.value},
                        response={
                            "status": "created",
                            "case_id": "CASE-1",
                            "preview": {"reason": "x"},
                        },
                    )
                )
            turns.append(
                TurnRecord(merchant=scripted.merchant, reply="A real reply", tool_calls=calls)
            )
        return CaseRun(case_id=case.id, category="multi_issue", turns=turns)

    return run()


def test_record_all_saves_one_file_per_journey_with_steps_and_the_case(tmp_path):
    saved = replays.record_all(tmp_path, run=fake_run)
    assert len(saved) == len(replays.JOURNEYS)
    appeal = json.loads((tmp_path / "cbd-appeal-preview.json").read_text())
    assert appeal["agent_version"] == agent_version()
    assert appeal["turns"][-1]["case"]["case_id"] == "CASE-1"
    assert appeal["turns"][0]["steps"]
    price = json.loads((tmp_path / "price-from-issue-row.json").read_text())
    assert price["entry_context"] == {"product": "HG-004", "issue_code": "price_mismatch"}
    assert price["turns"][1]["fix"] == "price_mismatch"
