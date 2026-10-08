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


def test_list_stores_finds_both_sample_stores():
    from merchant_agent.stores import list_stores

    assert list_stores() == ["sample-store", "suspended-store"]


def test_every_store_declares_its_automation_settings():
    """Google defaults item updates to on, so each store must state its settings explicitly."""
    import json

    from merchant_agent.config import PROJECT_ROOT

    paths = list((PROJECT_ROOT / "data" / "stores").glob("*/store.json")) + list(
        (PROJECT_ROOT / "evals" / "stores").glob("*/store.json")
    )
    assert paths
    for path in paths:
        settings = json.loads(path.read_text()).get("automatic_improvements")
        assert settings is not None, path
        assert set(settings) == {
            "price_updates",
            "availability_updates",
            "image_improvements",
            "shipping_improvements",
        }, path


def test_v1_stores_keep_item_updates_off_so_their_mismatches_stay_visible():
    store = load_store("sample-store")
    assert store.automatic_improvements.price_updates is False
    assert store.automatic_improvements.availability_updates is False
