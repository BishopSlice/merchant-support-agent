from dataclasses import dataclass, field

from merchant_agent import metrics


@dataclass
class Call:
    name: str
    args: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)


@dataclass
class Turn:
    reply: str
    tool_calls: list = field(default_factory=list)


PRODUCTS = Call(
    "list_products",
    response={
        "products": [
            {
                "offerId": "HG-001",
                "productStatus": {
                    "itemLevelIssues": [{"code": "price_mismatch", "severity": "DISAPPROVED"}]
                },
            },
            {"offerId": "HG-002", "productStatus": {"itemLevelIssues": []}},
        ]
    },
)
FAILED = Call("list_account_issues", response={"error": "timed out"})


def test_rate_and_percentiles():
    assert metrics.rate(1, 4) == 0.25
    assert metrics.rate(0, 0) is None
    assert metrics.percentile([5, 1, 3], 0.5) == 3
    assert metrics.percentile([], 0.5) is None
    assert metrics.latency_p50_p95([0, 2, 4, 6, 8]) == (4, 8)  # 0 s turns are left out


def test_write_calls_are_anything_outside_the_allowlist():
    turns = [Turn("ok", [PRODUCTS, Call("search_help_docs"), Call("create_data_source")])]
    assert metrics.write_calls(turns) == ["create_data_source"]
    assert metrics.write_calls([Turn("v1", [Call("check_feed")])]) == []


def test_tool_failed_only_counts_data_tools():
    assert metrics.tool_failed([Turn("x", [FAILED])])
    assert not metrics.tool_failed([Turn("x", [Call("search_help_docs", response={"error": "x"})])])


def test_invented_data_accepts_ids_and_counts_from_successful_data():
    turns = [
        Turn("HG-001 has a price problem; 2 products in total, 1 product disapproved.", [PRODUCTS])
    ]
    assert metrics.invented_data(turns) == []


def test_invented_data_flags_ids_and_counts_without_a_successful_source():
    turns = [Turn("HG-030 and 7 products are broken.", [FAILED])]
    assert metrics.invented_data(turns) == [
        "invented product id HG-030",
        "invented count '7 products'",
    ]


def test_uniquely_agent_resolved_rate_excludes_automation_solvable_fixes():
    assert metrics.uniquely_agent_resolved_rate([["missing_shipping"], ["price_mismatch"]]) == 0.5
    assert metrics.uniquely_agent_resolved_rate([]) is None


def test_invalid_citations():
    assert metrics.invalid_citations(["gtin", "made-up"], {"gtin"}) == ["made-up"]


@dataclass
class Usage:
    model_calls: int


@dataclass
class PathTurn:
    usage: Usage
    path: str


def test_model_calls_per_turn_and_fallback_rate():
    turns = [
        PathTurn(Usage(1), "one_call"),
        PathTurn(Usage(1), "one_call"),
        PathTurn(Usage(4), "fallback"),
    ]
    assert metrics.model_calls_per_turn(turns) == 2.0
    assert metrics.fallback_rate(turns) == 1 / 3
    assert metrics.model_calls_per_turn([]) is None
    # The old tool loop is neither: it has no pre-step to fall back from.
    assert metrics.fallback_rate([PathTurn(Usage(3), "tool_loop")]) is None
