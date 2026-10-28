"""Run approved, read-only missions at their scheduled time.

Schedules are written as "daily HH:MM" or "weekly mon HH:MM" (local time of the server). A mission whose
warrant writes is never run unattended: it needs a person to approve each run.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PATTERN = re.compile(
    r"^(?:(?P<daily>daily)|weekly\s+(?P<dow>mon|tue|wed|thu|fri|sat|sun))\s+(?P<h>\d{1,2}):(?P<m>\d{2})$"
)


def parse(schedule: str | None) -> tuple[int | None, int, int] | None:
    """Return (weekday or None for daily, hour, minute), or None if the text is not a schedule."""
    if not schedule:
        return None
    m = PATTERN.match(schedule.strip().lower())
    if not m:
        return None
    hour, minute = int(m.group("h")), int(m.group("m"))
    if hour > 23 or minute > 59:
        return None
    return (None if m.group("daily") else DAYS.index(m.group("dow")), hour, minute)


def last_slot(schedule: str | None, now: datetime) -> datetime | None:
    """The most recent scheduled time at or before ``now``."""
    spec = parse(schedule)
    if spec is None:
        return None
    weekday, hour, minute = spec
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if weekday is None:
        return slot if slot <= now else slot - timedelta(days=1)
    slot -= timedelta(days=(slot.weekday() - weekday) % 7)
    return slot if slot <= now else slot - timedelta(days=7)


def is_due(
    schedule: str | None, last_run: datetime | None, now: datetime, grace: timedelta = timedelta(hours=1)
) -> bool:
    """Due if the latest slot has passed, is recent (missed runs are not replayed) and has not run yet."""
    slot = last_slot(schedule, now)
    if slot is None or now - slot > grace:
        return False
    return last_run is None or last_run < slot


class Scheduler:
    def __init__(self, tick: Callable[[datetime], None], interval_s: float = 30.0):
        self._tick = tick
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="warrant-scheduler", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._tick(datetime.now())
            except Exception:  # a failed tick is logged and must not stop future ticks
                logging.getLogger("warrant.scheduler").exception("scheduler tick failed")
