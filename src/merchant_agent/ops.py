"""The /ops dashboard's numbers, computed from the event store.

Shared definitions (latency percentiles, write calls, rates) come from merchant_agent.metrics,
the same functions the eval scorecard uses. Every summary covers one traffic source, live or
eval; replays are never logged. Anything not measured says so instead of showing a number.
"""

import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta

from merchant_agent import metrics
from merchant_agent.events import EventStore

SMALL_SAMPLE = 30
# Business case assumption (docs/business-case.md): a conversation the agent contains would
# otherwise have been a live support contact, at Gartner's $8.01 average.
LIVE_CONTACT_COST_USD = 8.01
COST_AVOIDED_ASSUMPTION = (
    "Assumes each conversation without a handoff would otherwise have been a live support "
    f"contact at ${LIVE_CONTACT_COST_USD:.2f} (Gartner average, see the business case), minus "
    "the agent's model cost."
)
NOT_MEASURED = {
    "resolution": "Not measured on live traffic yet: needs edits linked to re-checks.",
    "injection": "Not detected on live traffic; measured by the eval injection cases.",
    "safety_blocks": "Model safety blocks aren't logged yet.",
}
TOOL_ERROR_ALERT = 0.05
P95_ALERT_SECONDS = 20.0


def _rows(store: EventStore, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with sqlite3.connect(store.path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(sql, params).fetchall()


def _in_window(store, source, days, now):
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=days)).isoformat()
    return _rows(
        store,
        "select * from conversations where source = ? and started_at >= ? order by started_at",
        (source, cutoff),
    )


def _placeholders(items) -> str:
    return ",".join("?" for _ in items)


def summary(store: EventStore, source: str = "live", days: int = 30, now=None) -> dict:
    """Panels 1 to 4 for one traffic source over the last `days` days."""
    convs = _in_window(store, source, days, now)
    ids = [c["id"] for c in convs]
    marks = _placeholders(ids)
    turns = _rows(store, f"select * from turns where conversation_id in ({marks})", tuple(ids))
    turn_ids = [t["id"] for t in turns]
    tmarks = _placeholders(turn_ids)
    calls = _rows(store, f"select * from tool_calls where turn_id in ({tmarks})", tuple(turn_ids))
    handoffs = _rows(
        store,
        "select h.*, t.conversation_id from handoffs h join turns t on t.id = h.turn_id "
        f"where h.turn_id in ({tmarks})",
        tuple(turn_ids),
    )
    feedback = _rows(store, f"select * from feedback where turn_id in ({tmarks})", tuple(turn_ids))
    grades = _rows(
        store,
        f"select * from grades where conversation_id in ({marks}) order by at",
        tuple(ids),
    )

    checks = [json.loads(t["checks"] or "{}") for t in turns]
    cost_by_conv = Counter()
    for t in turns:
        cost_by_conv[t["conversation_id"]] += t["cost_usd"]
    handed_off = {h["conversation_id"] for h in handoffs}
    contained = [c for c in ids if c not in handed_off]
    p50, p95 = metrics.latency_p50_p95(t["seconds"] for t in turns)
    failed_calls = Counter(c["name"] for c in calls if not c["ok"])
    after_failure = [c for c in checks if c.get("tool_failed")]
    latest_grade = {g["conversation_id"]: g for g in grades}  # ordered by time: last wins
    wrong = [
        g["wrong_advice_rate"] for g in latest_grade.values() if g["wrong_advice_rate"] is not None
    ]
    complete = [g["completeness"] for g in latest_grade.values() if g["completeness"]]
    today = (now or datetime.now(UTC)).date().isoformat()

    data = {
        "source": source,
        "days": days,
        "conversations": len(ids),
        "small_sample": len(ids) < SMALL_SAMPLE,
        "outcomes": {
            "by_day": _by_day(convs),
            "by_entry_point": dict(Counter(c["entry_point"] or source for c in convs)),
            "handoff_rate": metrics.rate(len(handed_off), len(ids)),
            "handoff_reasons": dict(Counter(h["reason"] for h in handoffs)),
            "feedback": {
                "up": sum(f["value"] == 1 for f in feedback),
                "down": sum(f["value"] == -1 for f in feedback),
            },
            "cost_avoided": {
                "contained": len(contained),
                "usd": sum(LIVE_CONTACT_COST_USD - cost_by_conv[c] for c in contained),
                "assumption": COST_AVOIDED_ASSUMPTION,
            },
            "resolution": None,
        },
        "quality": {
            "graded": len(latest_grade),
            "wrong_advice_rate": sum(wrong) / len(wrong) if wrong else None,
            "case_completeness": metrics.rate(complete.count("complete"), len(complete)),
        },
        "safety": {
            "write_calls": sum(len(c.get("write_calls", [])) for c in checks),
            "after_tool_failure": {
                "graceful": sum(not c.get("invented") for c in after_failure),
                "invented": sum(bool(c.get("invented")) for c in after_failure),
            },
            "personal_data_blocked": sum(
                c["name"] == "create_handoff_case"
                and "personal contact details" in (c["response"] or "")
                for c in calls
            ),
        },
        "operations": {
            "latency_p50": p50,
            "latency_p95": p95,
            "turns": len(turns),
            "cost_per_conversation": metrics.rate(sum(cost_by_conv.values()), len(ids)),
            "tokens_per_conversation": metrics.rate(
                sum(t["input_tokens"] + t["output_tokens"] for t in turns), len(ids)
            ),
            "spend_today": sum(t["cost_usd"] for t in turns if t["at"].startswith(today))
            + sum(g["cost_usd"] for g in grades if g["at"].startswith(today)),
            "model_calls_per_turn": metrics.model_calls_per_turn(_TurnRow(t) for t in turns),
            "fallback_rate": metrics.fallback_rate(_TurnRow(t) for t in turns),
            "tool_errors": dict(failed_calls),
            "tool_error_rate": metrics.rate(sum(failed_calls.values()), len(calls)),
            "agent_versions": sorted({c["agent_version"] for c in convs}),
            "models": sorted({c["model"] for c in convs}),
        },
        "not_measured": NOT_MEASURED,
    }
    data["alerts"] = _alerts(data)
    return data


class _TurnRow:
    """A stored turn in the shape the shared metrics read."""

    def __init__(self, row: sqlite3.Row) -> None:
        self.usage = type("Usage", (), {"model_calls": row["model_calls"]})
        self.path = row["path"] or "tool_loop"


def _by_day(convs) -> list[dict]:
    days: dict[str, Counter] = {}
    for c in convs:
        days.setdefault(c["started_at"][:10], Counter())[c["entry_point"] or "other"] += 1
    return [{"day": day, **counts} for day, counts in sorted(days.items())]


def _alerts(data: dict) -> list[str]:
    alerts = []
    if data["safety"]["write_calls"]:
        alerts.append(
            f"Write calls: {data['safety']['write_calls']} call(s) outside the read-only allowlist."
        )
    if data["safety"]["after_tool_failure"]["invented"]:
        alerts.append("The agent invented data after a tool failure.")
    rate = data["operations"]["tool_error_rate"]
    if rate is not None and rate > TOOL_ERROR_ALERT:
        alerts.append(f"Tool errors are {rate:.0%} of calls (alert above 5%).")
    p95 = data["operations"]["latency_p95"]
    if p95 is not None and p95 > P95_ALERT_SECONDS:
        alerts.append(f"p95 latency is {p95:.1f} s (alert above {P95_ALERT_SECONDS:.0f} s).")
    return alerts


def conversations(store: EventStore, source: str = "live", limit: int = 50) -> list[dict]:
    """The most recent conversations, newest first, for the trace list."""
    rows = _rows(
        store,
        "select c.*, "
        "(select count(*) from turns t where t.conversation_id = c.id) as turns, "
        "(select count(*) from handoffs h join turns t on t.id = h.turn_id "
        " where t.conversation_id = c.id) as handoffs, "
        "(select f.value from feedback f join turns t on t.id = f.turn_id "
        " where t.conversation_id = c.id order by f.at desc limit 1) as feedback "
        "from conversations c where c.source = ? order by c.started_at desc limit ?",
        (source, limit),
    )
    return [dict(r) for r in rows]


def trace(store: EventStore, conversation_id: str) -> dict | None:
    """One conversation in full: messages, tool calls, handoffs, feedback and grades."""
    [conv] = _rows(store, "select * from conversations where id = ?", (conversation_id,)) or [None]
    if conv is None:
        return None
    turns = []
    for t in _rows(
        store, "select * from turns where conversation_id = ? order by at", (conversation_id,)
    ):
        calls = _rows(
            store, "select * from tool_calls where turn_id = ? order by rowid", (t["id"],)
        )
        vote = _rows(store, "select value from feedback where turn_id = ?", (t["id"],))
        turns.append(
            {
                **{k: t[k] for k in ("id", "at", "merchant", "reply", "seconds", "cost_usd")},
                "checks": json.loads(t["checks"] or "{}"),
                "feedback": vote[0]["value"] if vote else None,
                "tool_calls": [
                    {k: c[k] for k in ("name", "args", "ok", "error", "response")} for c in calls
                ],
            }
        )
    grades = _rows(
        store, "select * from grades where conversation_id = ? order by at", (conversation_id,)
    )
    return {
        **dict(conv),
        "turns": turns,
        "grades": [dict(g) for g in grades],
        "steps": _steps(store, conversation_id),
    }


def _steps(store: EventStore, conversation_id: str) -> list[list[dict]]:
    """Each traced turn's spans in start order, with their depth: the step-by-step timings."""
    trace_ids = [
        r["trace_id"]
        for r in _rows(
            store,
            "select trace_id, min(start_ns) as first from spans where conversation_id = ? "
            "group by trace_id order by first",
            (conversation_id,),
        )
    ]
    traces = []
    for trace_id in trace_ids:
        spans = _rows(
            store, "select * from spans where trace_id = ? order by start_ns", (trace_id,)
        )
        parents = {s["span_id"]: s["parent_id"] for s in spans}

        def depth(span_id: str, parents: dict = parents) -> int:
            level, parent = 0, parents.get(span_id)
            while parent in parents:
                level, parent = level + 1, parents[parent]
            return level

        traces.append(
            [
                {
                    "name": s["name"],
                    "depth": depth(s["span_id"]),
                    "duration_ms": s["duration_ms"],
                    "attributes": json.loads(s["attributes"] or "{}"),
                }
                for s in spans
            ]
        )
    return traces
