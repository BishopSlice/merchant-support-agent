import pytest

from merchant_agent import demo
from merchant_agent.models import IssueType
from merchant_agent.tools.feed_checker import check_feed


@pytest.fixture
def demo_data(monkeypatch, tmp_path):
    """A fresh demo copy of the data, with settings pointed at it."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("DATA_DIR", raising=False)
    path = demo.prepare_demo_data()
    monkeypatch.setenv("DATA_DIR", str(path))
    return path


def issue_types(store_id: str) -> set[str]:
    return {group["issue_type"] for group in check_feed(store_id)["issue_groups"]}


def test_demo_data_is_a_copy_under_runtime(demo_data, tmp_path):
    assert demo_data == tmp_path / "runtime" / "demo-data"
    assert (demo_data / "stores" / "sample-store" / "feed.csv").is_file()
    assert (demo_data / "help_docs" / "gtin.md").is_file()


@pytest.mark.parametrize("issue_type", demo.FIXABLE_ISSUE_TYPES)
def test_each_fix_removes_its_issue_and_nothing_else(demo_data, issue_type):
    before = issue_types("sample-store")
    changed = demo.apply_fix("sample-store", issue_type)
    assert changed
    assert issue_types("sample-store") == before - {issue_type.value}


def test_restricted_products_and_missing_gtins_cannot_be_fixed_by_editing_data(demo_data):
    assert IssueType.RESTRICTED_PRODUCT not in demo.FIXABLE_ISSUE_TYPES
    assert IssueType.MISSING_GTIN not in demo.FIXABLE_ISSUE_TYPES
    with pytest.raises(ValueError):
        demo.apply_fix("sample-store", IssueType.RESTRICTED_PRODUCT)


def test_reset_restores_the_original_feed(demo_data, monkeypatch):
    demo.apply_fix("sample-store", IssueType.MISSING_SHIPPING)
    monkeypatch.delenv("DATA_DIR")
    demo.prepare_demo_data(reset=True)
    monkeypatch.setenv("DATA_DIR", str(demo_data))
    assert "missing_shipping" in issue_types("sample-store")


def test_prepare_keeps_existing_demo_data_unless_reset(demo_data, monkeypatch):
    demo.apply_fix("sample-store", IssueType.MISSING_SHIPPING)
    monkeypatch.delenv("DATA_DIR")
    demo.prepare_demo_data()
    monkeypatch.setenv("DATA_DIR", str(demo_data))
    assert "missing_shipping" not in issue_types("sample-store")


def test_fixes_refuse_to_edit_the_real_data_folder(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    with pytest.raises(RuntimeError):
        demo.apply_fix("sample-store", IssueType.MISSING_SHIPPING)


def test_shortened_titles_end_on_a_whole_word(demo_data):
    from merchant_agent.stores import load_feed

    originals = {p.id: p.title for p in load_feed("sample-store")}
    for product_id in demo.apply_fix("sample-store", IssueType.TITLE_TOO_LONG):
        new_title = next(p.title for p in load_feed("sample-store") if p.id == product_id)
        assert originals[product_id].startswith(new_title + " ")


def test_fixing_a_feed_with_no_products_changes_nothing(demo_data):
    feed = demo_data / "stores" / "sample-store" / "feed.csv"
    feed.write_text(feed.read_text().splitlines()[0] + "\n")
    assert demo.apply_fix("sample-store", IssueType.MISSING_SHIPPING) == []
