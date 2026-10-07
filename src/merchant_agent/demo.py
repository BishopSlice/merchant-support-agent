"""Demo helpers: a resettable copy of the store data, and simulated merchant fixes.

The app points DATA_DIR at runtime/demo-data so a demo can change feeds freely and be
reset to the original files in data/ afterwards. The real data/ folder is never edited.
"""

import csv
import shutil
from collections.abc import Callable
from pathlib import Path

from merchant_agent.config import PROJECT_ROOT, get_settings
from merchant_agent.models import IssueType, Product
from merchant_agent.stores import store_dir
from merchant_agent.tools.feed_rules import MAX_TITLE_LENGTH, run_checks

ORIGINAL_DATA_DIR = PROJECT_ROOT / "data"


def demo_data_dir() -> Path:
    """Where the demo copy of the data lives."""
    return get_settings().runtime_dir / "demo-data"


def prepare_demo_data(reset: bool = False) -> Path:
    """Copy data/ to the demo folder if it isn't there yet, or always when reset is True."""
    target = demo_data_dir()
    if reset and target.exists():
        shutil.rmtree(target)
    if not target.exists():
        shutil.copytree(ORIGINAL_DATA_DIR, target)
    return target


def _shorten_title(product: Product) -> str:
    """Cut a title to the limit at a word boundary."""
    return product.title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0].rstrip(", ")


# What a merchant would change to fix each issue: (feed column, new value for a product).
# Restricted products need a policy decision and missing GTINs need the real barcode,
# so neither can be fixed by simply editing data.
FIXES: dict[IssueType, tuple[str, Callable[[Product], str]]] = {
    IssueType.PRICE_MISMATCH: ("price", lambda p: p.landing_page_price),
    IssueType.AVAILABILITY_MISMATCH: ("availability", lambda p: p.landing_page_availability),
    IssueType.MISSING_SHIPPING: ("shipping", lambda p: "US:::5.95 USD"),
    IssueType.INVALID_IMAGE: ("image_link", lambda p: f"{p.link}/photo.jpg"),
    IssueType.TITLE_TOO_LONG: ("title", _shorten_title),
}
FIXABLE_ISSUE_TYPES = list(FIXES)


def apply_fix(store_id: str, issue_type: IssueType) -> list[str]:
    """Fix every product in a store's demo feed that has this issue; return their ids."""
    if issue_type not in FIXES:
        raise ValueError(f"{issue_type} can't be fixed by editing product data")
    if get_settings().data_dir.resolve() == ORIGINAL_DATA_DIR.resolve():
        raise RuntimeError("Refusing to edit the original data/ folder; use the demo copy")

    column, new_value = FIXES[issue_type]
    path = store_dir(store_id) / "feed.csv"
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = reader.fieldnames or []

    changed = []
    for row in rows:
        product = Product(**row)
        if any(issue.issue_type is issue_type for issue in run_checks(product)):
            row[column] = new_value(product)
            changed.append(product.id)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return changed
