from datetime import date

from assesstrack.review import classify

NAMES = ["Assessment Plan", "Data Summary", "Findings"]


def test_not_submitted_misses_everything():
    r = classify(None, "2026-10-15", {}, NAMES)
    assert r.status == "not_submitted" and r.missing == NAMES


def test_missing_lists_only_absent_items_in_order():
    r = classify("2026-10-01T10:00:00", "2026-10-15", {"Assessment Plan": True, "Findings": False}, NAMES)
    assert r.status == "missing" and r.missing == ["Data Summary", "Findings"]


def test_late_when_complete_after_due_date():
    present = dict.fromkeys(NAMES, True)
    assert classify("2026-10-16T09:00:00", "2026-10-15", present, NAMES).status == "late"
    assert classify("2026-10-15T23:59:00", date(2026, 10, 15), present, NAMES).status == "complete"
