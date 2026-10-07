import pytest

from evals.case_format import CaseError, load_cases

VALID = """
id = "{id}"
category = "easy_fix"
store = "sample-store"
description = "Merchant fixes shipping and the agent re-checks."

[[turns]]
merchant = "Why are my products disapproved?"

[[turns]]
fix = "missing_shipping"
merchant = "I added shipping. Check again?"

[expect]
should_handoff = false
resolved_issues = ["missing_shipping"]
must_mention = ["shipping"]
must_not_say = ["Shopify"]
must_cite = ["shipping"]
"""


def write(folder, name: str, text: str) -> None:
    (folder / f"{name}.toml").write_text(text)


def test_loads_a_valid_case(tmp_path):
    write(tmp_path, "fix-shipping", VALID.format(id="fix-shipping"))
    [case] = load_cases(tmp_path)
    assert case.id == "fix-shipping"
    assert case.turns[1].fix == "missing_shipping"
    assert case.expect.resolved_issues == ["missing_shipping"]


def test_cases_come_back_sorted_by_id(tmp_path):
    for name in ["b-case", "a-case"]:
        write(tmp_path, name, VALID.format(id=name))
    assert [case.id for case in load_cases(tmp_path)] == ["a-case", "b-case"]


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (('id = "fix-shipping"', 'id = "other-id"'), "does not match file name"),
        (('store = "sample-store"', 'store = "nowhere"'), "unknown store"),
        (('must_cite = ["shipping"]', 'must_cite = ["no-such-doc"]'), "unknown help doc"),
        (('must_mention = ["shipping"]', 'must_mention = ["(unclosed"]'), "bad pattern"),
        (('fix = "missing_shipping"', 'fix = "restricted_product"'), "can't be simulated"),
        (("should_handoff = false", "should_handoff = true"), "needs a handoff_reason"),
        (('category = "easy_fix"', 'category = "made_up"'), "category"),
    ],
)
def test_invalid_cases_are_reported_with_the_file_name(tmp_path, change, problem):
    write(tmp_path, "fix-shipping", VALID.format(id="fix-shipping").replace(*change))
    with pytest.raises(CaseError) as error:
        load_cases(tmp_path)
    assert "fix-shipping.toml" in str(error.value)
    assert problem in str(error.value)


def test_handoff_reason_without_a_handoff_is_rejected(tmp_path):
    text = VALID.format(id="x").replace(
        "should_handoff = false", 'should_handoff = false\nhandoff_reason = "policy_appeal"'
    )
    write(tmp_path, "x", text)
    with pytest.raises(CaseError, match="handoff_reason only makes sense"):
        load_cases(tmp_path)


def test_case_checks_need_a_handoff(tmp_path):
    text = VALID.format(id="x").replace(
        "should_handoff = false", 'should_handoff = false\ncase_must_mention = ["candle"]'
    )
    write(tmp_path, "x", text)
    with pytest.raises(CaseError, match="case_must_"):
        load_cases(tmp_path)


def test_all_problems_are_reported_together(tmp_path):
    write(tmp_path, "one", VALID.format(id="wrong-1"))
    write(tmp_path, "two", VALID.format(id="wrong-2"))
    with pytest.raises(CaseError) as error:
        load_cases(tmp_path)
    assert "one.toml" in str(error.value) and "two.toml" in str(error.value)


def test_eval_only_stores_count_as_known(tmp_path):
    text = VALID.format(id="x").replace('store = "sample-store"', 'store = "price-only"')
    write(tmp_path, "x", text)
    assert load_cases(tmp_path)[0].store == "price-only"
