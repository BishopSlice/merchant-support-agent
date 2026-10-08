"""The event store behind the /ops dashboard: conversations, turns, tool calls, handoffs,
feedback and grades, in SQLite.

Privacy (SPEC, Observability): emails and phone numbers are masked before anything is
stored, and message text is removed after 30 days, leaving only the numbers.
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from merchant_agent import metrics
from merchant_agent.models import _EMAIL, _PHONE

SOURCES = {"live", "eval", "replay"}
TEXT_RETENTION = timedelta(days=30)
MAX_RESPONSE_CHARS = 20_000  # tool responses are kept for the safety checks, capped

SCHEMA = """
create table if not exists conversations (
  id text primary key,
  source text not null check (source in ('live', 'eval', 'replay')),
  store_id text not null,
  agent_version text not null,
  model text not null,
  entry_point text,
  label text,
  started_at text not null
);
create table if not exists turns (
  id text primary key,
  conversation_id text not null references conversations(id),
  at text not null,
  merchant text,
  reply text,
  seconds real not null,
  model_calls integer not null,
  input_tokens integer not null,
  output_tokens integer not null,
  cost_usd real not null,
  checks text
);
create table if not exists tool_calls (
  turn_id text not null references turns(id),
  name text not null,
  args text,
  ok integer not null,
  error text,
  response text
);
create table if not exists handoffs (
  turn_id text not null references turns(id),
  case_id text not null,
  reason text
);
create table if not exists feedback (
  turn_id text primary key references turns(id),
  value integer not null check (value in (-1, 1)),
  at text not null
);
create table if not exists grades (
  conversation_id text not null references conversations(id),
  wrong_advice_rate real,
  completeness text,
  cost_usd real not null,
  at text not null
);
"""


def mask(text: str) -> str:
    """Replace emails and phone numbers with placeholders."""
    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", text))


def turn_checks(conversation: list) -> dict:
    """Safety checks for the last turn of a conversation, using every turn so far: calls
    outside the allowlist, whether a data tool failed, and data the reply invented."""
    last = conversation[-1:]
    invented_before = set(metrics.invented_data(conversation[:-1]))
    return {
        "write_calls": metrics.write_calls(last),
        "tool_failed": metrics.tool_failed(last),
        "invented": [p for p in metrics.invented_data(conversation) if p not in invented_before],
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()


class EventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(SCHEMA)
            columns = [row[1] for row in db.execute("pragma table_info(tool_calls)")]
            if "response" not in columns:  # databases made before responses were stored
                db.execute("alter table tool_calls add column response text")
            turn_columns = [row[1] for row in db.execute("pragma table_info(turns)")]
            if turn_columns and "checks" not in turn_columns:
                db.execute("alter table turns add column checks text")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.execute("pragma foreign_keys = on")
        return db

    def start_conversation(
        self,
        *,
        source: str,
        store_id: str,
        agent_version: str,
        model: str,
        entry_point: str | None = None,
        label: str | None = None,
        conversation_id: str = "",
    ) -> str:
        """Open a conversation and return its id. source is live, eval or replay."""
        if source not in SOURCES:
            raise ValueError(f"source must be one of {sorted(SOURCES)}")
        conversation_id = conversation_id or uuid.uuid4().hex
        with self._db() as db:
            db.execute(
                "insert into conversations values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    source,
                    store_id,
                    agent_version,
                    model,
                    entry_point,
                    label,
                    _now(),
                ),
            )
        return conversation_id

    def record_turn(
        self,
        conversation_id: str,
        merchant: str,
        turn: Any,
        cost_usd: float,
        turn_id: str = "",
        checks: dict | None = None,
    ) -> str:
        """Store one turn (masked) with its tool calls and any handoff; return the turn id.

        checks holds the safety checks worked out by the caller, who has the whole
        conversation (see turn_checks).
        """
        turn_id = turn_id or uuid.uuid4().hex
        usage = turn.usage
        with self._db() as db:
            db.execute(
                "insert into turns (id, conversation_id, at, merchant, reply, seconds, "
                "model_calls, input_tokens, output_tokens, cost_usd, checks) "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id,
                    conversation_id,
                    _now(),
                    mask(merchant),
                    mask(turn.reply),
                    turn.seconds,
                    usage.model_calls,
                    usage.input_tokens,
                    usage.output_tokens,
                    cost_usd,
                    json.dumps(checks or {}),
                ),
            )
            for call in turn.tool_calls:
                response = call.response if isinstance(call.response, dict) else {}
                error = response.get("error")
                db.execute(
                    "insert into tool_calls (turn_id, name, args, ok, error, response) "
                    "values (?, ?, ?, ?, ?, ?)",
                    (
                        turn_id,
                        call.name,
                        mask(json.dumps(call.args, default=str)),
                        int(isinstance(call.response, dict) and error is None),
                        mask(str(error)) if error is not None else None,
                        mask(json.dumps(call.response, default=str))[:MAX_RESPONSE_CHARS],
                    ),
                )
                if call.name == "create_handoff_case" and response.get("status") == "created":
                    db.execute(
                        "insert into handoffs values (?, ?, ?)",
                        (turn_id, response["case_id"], call.args.get("reason")),
                    )
        return turn_id

    def record_feedback(self, turn_id: str, value: int) -> None:
        """Thumbs up (1) or down (-1) on one reply. A second vote replaces the first."""
        if value not in (-1, 1):
            raise ValueError("feedback is 1 or -1")
        with self._db() as db:
            if not db.execute("select 1 from turns where id = ?", (turn_id,)).fetchone():
                raise KeyError(turn_id)
            db.execute(
                "insert into feedback values (?, ?, ?) "
                "on conflict(turn_id) do update set value = excluded.value, at = excluded.at",
                (turn_id, value, _now()),
            )

    def record_grade(
        self,
        conversation_id: str,
        wrong_advice_rate: float | None,
        completeness: str | None,
        cost_usd: float,
    ) -> None:
        with self._db() as db:
            db.execute(
                "insert into grades values (?, ?, ?, ?, ?)",
                (conversation_id, wrong_advice_rate, completeness, cost_usd, _now()),
            )

    def purge_old_text(self, now: datetime | None = None) -> int:
        """Remove message text older than 30 days; numbers stay. Returns turns changed."""
        cutoff = ((now or datetime.now(UTC)) - TEXT_RETENTION).isoformat()
        with self._db() as db:
            changed = db.execute(
                "update turns set merchant = null, reply = null "
                "where at < ? and (merchant is not null or reply is not null)",
                (cutoff,),
            ).rowcount
            db.execute(
                "update tool_calls set args = null, response = null "
                "where turn_id in (select id from turns where at < ?)",
                (cutoff,),
            )
        return changed
