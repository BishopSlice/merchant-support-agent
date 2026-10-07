"""Load a simulated store's account details and product feed from data/stores."""

import csv
import json
import re
from pathlib import Path

from merchant_agent.config import get_settings
from merchant_agent.models import Product, Store

_STORE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class StoreNotFoundError(LookupError):
    """Raised when a store id does not match any folder in data/stores."""


def store_dir(store_id: str) -> Path:
    """Return the folder for a store, rejecting ids that are not plain slugs."""
    if not _STORE_ID_PATTERN.match(store_id):
        raise StoreNotFoundError(f"Invalid store id: {store_id!r}")
    path = get_settings().stores_dir / store_id
    if not path.is_dir():
        raise StoreNotFoundError(f"No store called {store_id!r}")
    return path


def load_store(store_id: str) -> Store:
    """Load a store's name and account status from its store.json."""
    data = json.loads((store_dir(store_id) / "store.json").read_text())
    return Store(**data)


def load_feed(store_id: str) -> list[Product]:
    """Load every product row from a store's feed.csv."""
    with (store_dir(store_id) / "feed.csv").open(newline="") as f:
        return [Product(**row) for row in csv.DictReader(f)]
