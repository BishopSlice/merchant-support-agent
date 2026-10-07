import pytest

from merchant_agent.models import AccountStatus
from merchant_agent.stores import StoreNotFoundError, load_feed, load_store


def test_sample_store_is_active():
    store = load_store("sample-store")
    assert store.name == "Hearth & Hollow"
    assert store.account_status is AccountStatus.ACTIVE


def test_sample_store_has_thirty_unique_products():
    products = load_feed("sample-store")
    assert len(products) == 30
    assert len({p.id for p in products}) == 30


def test_suspended_store_is_suspended_with_a_reason():
    store = load_store("suspended-store")
    assert store.account_status is AccountStatus.SUSPENDED
    assert store.suspension_reason


def test_unknown_store_raises():
    with pytest.raises(StoreNotFoundError):
        load_store("no-such-store")


@pytest.mark.parametrize("bad_id", ["../secrets", "Sample-Store", "", "a/b"])
def test_store_ids_must_be_plain_slugs(bad_id):
    with pytest.raises(StoreNotFoundError):
        load_feed(bad_id)
