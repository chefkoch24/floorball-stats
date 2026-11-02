import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sync_connect_notion import keep_order, matches  # noqa: E402


def page(status=None, archived=False):
    return {"archived": archived, "properties": {"_Status": {"type": "status", "status": {"name": status} if status else None}}}


def test_matches_filters_on_status_and_archive():
    assert matches(page("Done"), {"_Status": "Done"})
    assert not matches(page("Not started"), {"_Status": "Done"})
    assert not matches(page(), {"_Status": "Done"})
    assert not matches(page("Done", archived=True), None)
    assert matches(page(), None)


def test_keep_order_keeps_committed_order_and_appends_new_by_creation():
    records = [
        {"id": "new-late", "_created": "2026-03-01"},
        {"id": "b", "_created": "2025-01-01"},
        {"id": "new-early", "_created": "2026-02-01"},
        {"id": "a", "_created": "2025-06-01"},
    ]
    ordered = keep_order(records, ["a", "b"])
    assert [record["id"] for record in ordered] == ["a", "b", "new-early", "new-late"]
    assert all("_created" not in record for record in ordered)
