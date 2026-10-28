from __future__ import annotations

from datetime import datetime, timedelta

from warrant.scheduler import is_due, last_slot, parse

THU = datetime(2026, 10, 29, 7, 40)  # a Thursday


def test_parse():
    assert parse("daily 07:30") == (None, 7, 30)
    assert parse("Weekly Mon 18:00") == (0, 18, 0)
    assert parse("on request") is None
    assert parse("daily 25:00") is None


def test_last_slot():
    assert last_slot("daily 07:30", THU) == datetime(2026, 10, 29, 7, 30)
    assert last_slot("daily 08:00", THU) == datetime(2026, 10, 28, 8, 0)
    assert last_slot("weekly mon 18:00", THU) == datetime(2026, 10, 26, 18, 0)


def test_is_due_runs_once_per_slot_and_skips_stale_slots():
    assert is_due("daily 07:30", None, THU)
    assert not is_due("daily 07:30", datetime(2026, 10, 29, 7, 31), THU)
    assert is_due("daily 07:30", datetime(2026, 10, 28, 7, 31), THU)
    assert not is_due("daily 07:30", None, THU + timedelta(hours=3))  # missed by more than the grace period
    assert not is_due(None, None, THU)
