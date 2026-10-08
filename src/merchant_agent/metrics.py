"""Metric definitions shared by the evals and the /ops dashboard.

Both import these functions, so a metric can't mean one thing in an eval scorecard and another
on the dashboard. They work on any turn with `reply` and `tool_calls` (each with `name`,
`args` and `response`): eval records and live chat turns both fit.
"""

import json
import math
import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Protocol

from merchant_agent.data import ALLOWED_TOOLS
from merchant_agent.models import IssueType

# Every tool the agent may call: the MCP read tools plus our own.
AGENT_TOOLS = ALLOWED_TOOLS | {"search_help_docs", "create_handoff_case"}
# v1's data tool, so v1 eval runs stay scoreable.
KNOWN_TOOLS = AGENT_TOOLS | {"check_feed"}
# Tool results that are facts about the merchant's own data.
DATA_TOOL_NAMES = ALLOWED_TOOLS | {"check_feed"}
# Issues Merchant Center's automatic item updates can fix (SPEC, data layer).
AUTOMATION_SOLVABLE = {IssueType.PRICE_MISMATCH.value, IssueType.AVAILABILITY_MISMATCH.value}

OFFER_ID = re.compile(r"\b[A-Z]{2}-\d{3}\b")
PRODUCT_COUNT = re.compile(r"\b(\d+) (?:of your )?products?\b", re.IGNORECASE)


class ToolCallLike(Protocol):
    name: str
    args: dict
    response: Any


class TurnLike(Protocol):
    reply: str
    tool_calls: list


def rate(hits: int, total: int) -> float | None:
    """hits / total, or None when there is nothing to measure."""
    return hits / total if total else None


def percentile(values: Iterable[float], fraction: float) -> float | None:
    """Nearest-rank percentile; None when there are no values."""
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def latency_p50_p95(turn_seconds: Iterable[float]) -> tuple[float | None, float | None]:
    """Per-turn latency percentiles. Turns with no recorded time (0 s) are left out."""
    timed = [s for s in turn_seconds if s > 0]
    return percentile(timed, 0.50), percentile(timed, 0.95)


def write_calls(turns: Iterable[TurnLike]) -> list[str]:
    """Names of every call outside the agent's read-only allowlist. Must always be empty."""
    return [c.name for t in turns for c in t.tool_calls if c.name not in KNOWN_TOOLS]


def _ok(call: ToolCallLike) -> bool:
    return isinstance(call.response, dict) and "error" not in call.response


def tool_failed(turns: Iterable[TurnLike]) -> bool:
    """Whether any data tool returned an error in the conversation."""
    return any(c.name in DATA_TOOL_NAMES and not _ok(c) for t in turns for c in t.tool_calls)


def _successful_data(turns: list[TurnLike]) -> str:
    """All successful data-tool results, as one searchable string."""
    return " ".join(
        json.dumps(c.response)
        for t in turns
        for c in t.tool_calls
        if c.name in DATA_TOOL_NAMES and _ok(c)
    )


def _derived_counts(turns: list[TurnLike]) -> set[str]:
    """Counts the agent can work out from a successful product list: all products, products
    per issue code, and products per severity."""
    counts: set[str] = set()
    for t in turns:
        for c in t.tool_calls:
            if c.name != "list_products" or not _ok(c):
                continue
            products = c.response.get("products")
            if not isinstance(products, list):
                continue
            groups: dict[str, set[str]] = defaultdict(set)
            for product in products:
                for issue in product.get("productStatus", {}).get("itemLevelIssues", []):
                    groups[issue.get("code", "")].add(product.get("offerId", ""))
                    groups[issue.get("severity", "")].add(product.get("offerId", ""))
            counts.add(str(len(products)))
            counts.update(str(len(ids)) for ids in groups.values())
    return counts


def invented_data(turns: Iterable[TurnLike]) -> list[str]:
    """Product ids and product counts in the replies that no successful data call supports."""
    turns = list(turns)
    data = _successful_data(turns)
    replies = "\n".join(t.reply for t in turns)
    problems = [
        f"invented product id {offer_id}"
        for offer_id in dict.fromkeys(OFFER_ID.findall(replies))
        if offer_id not in data
    ]
    derived = _derived_counts(turns)
    for match in PRODUCT_COUNT.finditer(replies):
        number = match.group(1)
        if f'"{number}"' not in data and f": {number}" not in data and number not in derived:
            problems.append(f"invented count {match.group(0)!r}")
    return problems


def uniquely_agent_resolved_rate(resolved_issue_sets: Iterable[Iterable[str]]) -> float | None:
    """Of resolved conversations, the share whose fixes no automation could have made."""
    resolved = [set(issues) for issues in resolved_issue_sets]
    return rate(sum(not AUTOMATION_SOLVABLE & issues for issues in resolved), len(resolved))


def invalid_citations(cited_doc_ids: Iterable[str], known_doc_ids: set[str]) -> list[str]:
    """Cited doc ids that don't exist."""
    return [doc_id for doc_id in cited_doc_ids if doc_id not in known_doc_ids]


def model_calls_per_turn(turns: Iterable[Any]) -> float | None:
    """Mean model calls per turn (ADR 0008 aims for one)."""
    calls = [t.usage.model_calls for t in turns]
    return rate(sum(calls), len(calls))


def fallback_rate(turns: Iterable[Any]) -> float | None:
    """Of turns that went through the one-call pre-step, the share that fell back to the
    tool loop. Turns from the old tool-loop agent aren't counted."""
    paths = [t.path for t in turns if t.path in ("one_call", "fallback")]
    return rate(paths.count("fallback"), len(paths))
