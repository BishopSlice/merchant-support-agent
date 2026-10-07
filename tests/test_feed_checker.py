from merchant_agent.tools.feed_checker import check_feed

# Every problem planted in data/stores/sample-store/feed.csv.
PLANTED = {
    "missing_gtin": {"HG-002", "HG-007", "HG-011", "HG-019", "HG-024", "HG-028"},
    "price_mismatch": {"HG-004", "HG-015", "HG-021"},
    "invalid_image": {"HG-006", "HG-013", "HG-027"},
    "title_too_long": {"HG-009", "HG-017"},
    "availability_mismatch": {"HG-012", "HG-025"},
    "missing_shipping": {"HG-019", "HG-030"},
    "restricted_product": {"HG-023"},
}


def found_by_type(result: dict) -> dict[str, set[str]]:
    return {
        group["issue_type"]: {p["id"] for p in group["products"]}
        for group in result["issue_groups"]
    }


def test_checker_finds_exactly_the_planted_problems():
    assert found_by_type(check_feed("sample-store")) == PLANTED


def test_counts_match_product_lists():
    for group in check_feed("sample-store")["issue_groups"]:
        assert group["count"] == len(group["products"])


def test_groups_are_sorted_biggest_first():
    counts = [g["count"] for g in check_feed("sample-store")["issue_groups"]]
    assert counts == sorted(counts, reverse=True)
    assert check_feed("sample-store")["issue_groups"][0]["issue_type"] == "missing_gtin"


def test_summary_counts_products_not_issues():
    result = check_feed("sample-store")
    assert result["total_products"] == 30
    # HG-019 has two problems but is one product.
    assert result["products_with_issues"] == len(set().union(*PLANTED.values())) == 18


def test_result_includes_account_status():
    result = check_feed("suspended-store")
    assert result["account_status"] == "suspended"
    assert "returns policy" in result["suspension_reason"]
    assert result["issue_groups"] == []


def test_unknown_store_returns_an_error_instead_of_raising():
    assert "error" in check_feed("no-such-store")
