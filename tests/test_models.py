from datetime import UTC, datetime

from merchant_agent.models import AccountStatus, Case, Issue, IssueType, Product, Store


def test_product_optional_fields_default_to_blank():
    product = Product(id="SKU-1", title="Mug")
    assert product.gtin == ""
    assert product.image_link == ""


def test_store_defaults_to_active():
    store = Store(store_id="s", name="S")
    assert store.account_status is AccountStatus.ACTIVE


def test_issue_type_accepts_plain_string():
    issue = Issue(
        product_id="SKU-1", issue_type="missing_gtin", severity="limited", field="gtin", detail="x"
    )
    assert issue.issue_type is IssueType.MISSING_GTIN


def test_case_lists_start_empty():
    case = Case(
        case_id="c1",
        store_id="s",
        created_at=datetime(2026, 10, 7, tzinfo=UTC),
        reason="account_suspended",
        merchant_request="get my account back",
        suggested_next_step="review suspension",
    )
    assert case.issues_found == []
    assert case.already_tried == []
