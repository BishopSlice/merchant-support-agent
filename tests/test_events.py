import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from merchant_agent.events import EventStore, mask


@dataclass
class Call:
    name: str
    args: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)


@dataclass
class Usage:
    model_calls: int = 2
    input_tokens: int = 1000
    cached_tokens: int = 0
    output_tokens: int = 100


@dataclass
class Turn:
    reply: str
    tool_calls: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    seconds: float = 3.5


@pytest.fixture
def store(tmp_path):
    return EventStore(tmp_path / "events.sqlite")


def rows(store, sql):
    with sqlite3.connect(store.path) as db:
        return db.execute(sql).fetchall()


def test_mask_removes_emails_and_phone_numbers():
    text = "Mail me at jo@example.com or call +1 (415) 555-0100. GTIN 0850012345043 is fine."
    masked = mask(text)
    assert "jo@example.com" not in masked and "555-0100" not in masked
    assert "[email]" in masked and "[phone]" in masked
    assert "0850012345043" in masked  # barcodes are not phone numbers


def test_a_conversation_and_its_turns_are_recorded(store):
    conversation = store.start_conversation(
        source="live", store_id="s-1", agent_version="abc", model="m", entry_point="issue_row"
    )
    case = Call(
        "create_handoff_case",
        {"reason": "policy_appeal"},
        {"status": "created", "case_id": "CASE-1", "preview": {}},
    )
    turn = Turn(
        "Reply for jo@example.com",
        [
            Call("list_products", {}, {"products": []}),
            Call("list_account_issues", {}, {"error": "x"}),
            case,
        ],
    )
    turn_id = store.record_turn(conversation, "Hi, I'm jo@example.com", turn, cost_usd=0.01)
    [(merchant, reply, seconds, cost)] = rows(
        store, "select merchant, reply, seconds, cost_usd from turns"
    )
    assert "[email]" in merchant and "[email]" in reply
    assert (seconds, cost) == (3.5, 0.01)
    calls = rows(store, "select name, ok from tool_calls order by rowid")
    assert calls == [("list_products", 1), ("list_account_issues", 0), ("create_handoff_case", 1)]
    assert rows(store, "select case_id, reason from handoffs") == [("CASE-1", "policy_appeal")]
    assert isinstance(turn_id, str)


def test_only_known_traffic_sources_are_accepted(store):
    with pytest.raises(ValueError):
        store.start_conversation(source="other", store_id="s", agent_version="a", model="m")


def test_feedback_is_one_vote_per_turn(store):
    conversation = store.start_conversation(
        source="live", store_id="s", agent_version="a", model="m"
    )
    turn_id = store.record_turn(conversation, "hi", Turn("hello"), cost_usd=0.0)
    store.record_feedback(turn_id, 1)
    store.record_feedback(turn_id, -1)  # changing your mind replaces the vote
    assert rows(store, "select value from feedback") == [(-1,)]
    with pytest.raises(ValueError):
        store.record_feedback(turn_id, 5)
    with pytest.raises(KeyError):
        store.record_feedback("no-such-turn", 1)


def test_text_older_than_30_days_is_removed_but_numbers_stay(store):
    conversation = store.start_conversation(
        source="live", store_id="s", agent_version="a", model="m"
    )
    store.record_turn(conversation, "old question", Turn("old answer"), cost_usd=0.02)
    later = datetime.now(UTC) + timedelta(days=31)
    assert store.purge_old_text(now=later) == 1
    assert rows(store, "select merchant, reply, cost_usd from turns") == [(None, None, 0.02)]


def test_recording_a_turn_is_fast(store):
    conversation = store.start_conversation(
        source="live", store_id="s", agent_version="a", model="m"
    )
    started = time.perf_counter()
    for _ in range(50):
        store.record_turn(conversation, "hi", Turn("hello", [Call("list_products")]), cost_usd=0.0)
    per_turn_ms = (time.perf_counter() - started) / 50 * 1000
    assert per_turn_ms < 50


def test_tool_responses_are_kept_capped_and_purged_with_the_text(store):
    conversation = store.start_conversation(
        source="live", store_id="s", agent_version="a", model="m"
    )
    big = Call("list_products", {}, {"products": ["x" * 30_000]})
    store.record_turn(conversation, "hi", Turn("hello", [big]), cost_usd=0.0)
    [(response,)] = rows(store, "select response from tool_calls")
    assert len(response) <= 20_000
    store.purge_old_text(now=datetime.now(UTC) + timedelta(days=31))
    assert rows(store, "select response from tool_calls") == [(None,)]


def test_an_older_database_gains_the_response_column(tmp_path):
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(
            "create table tool_calls (turn_id text, name text, args text, ok int, error text)"
        )
    store = EventStore(path)
    columns = [r[1] for r in rows(store, "pragma table_info(tool_calls)")]
    assert "response" in columns


def test_turn_checks_use_the_whole_conversation():
    from merchant_agent.events import turn_checks

    loaded = Turn(
        "2 products",
        [
            Call(
                "list_products",
                {},
                {
                    "products": [
                        {"offerId": "HG-001", "productStatus": {"itemLevelIssues": []}},
                        {"offerId": "HG-002", "productStatus": {"itemLevelIssues": []}},
                    ]
                },
            )
        ],
    )
    later = Turn(
        "HG-001 is fine, but HG-099 is broken", [Call("list_account_issues", {}, {"error": "x"})]
    )
    checks = turn_checks([loaded, later])
    assert checks == {
        "write_calls": [],
        "tool_failed": True,
        "invented": ["invented product id HG-099"],
    }
