"""
CatSprayer spray-event logging and statistics.

Appends one small JSON record per spray event to a local log file, and
computes simple aggregate stats from it for the GUI's stats window.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timedelta

from catsprayer.paths import EVENTS_LOG


def log_spray_event(confidence: float = 0.0) -> None:
    """
    Append a single spray event to the log. Safe to call frequently; each
    call is a single appended line, no read-modify-write of the whole file.
    """

    EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": time.time(),
        "confidence": confidence,
    }

    with open(EVENTS_LOG, "a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


def _load_events() -> list[dict]:
    if not EVENTS_LOG.exists():
        return []

    events = []

    with open(EVENTS_LOG, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip a corrupted line (e.g. partial write from a crash)
                # rather than failing the whole stats view over it.
                continue

    return events


def get_stats() -> dict:
    """
    Returns:
    {
        "today_count": int,
        "week_count": int,
        "total_count": int,
        "most_common_hour": int | None,   # 0-23, local time
        "last_event_timestamp": float | None,
    }
    """

    events = _load_events()

    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=today_start.weekday())

    today_count = 0
    week_count = 0
    hour_counter: Counter[int] = Counter()
    last_event_timestamp = None

    for event in events:
        ts = event.get("timestamp")
        if ts is None:
            continue

        dt = datetime.fromtimestamp(ts)

        if dt >= today_start:
            today_count += 1
        if dt >= week_start:
            week_count += 1

        hour_counter[dt.hour] += 1

        if last_event_timestamp is None or ts > last_event_timestamp:
            last_event_timestamp = ts

    most_common_hour = None
    if hour_counter:
        most_common_hour = hour_counter.most_common(1)[0][0]

    return {
        "today_count": today_count,
        "week_count": week_count,
        "total_count": len(events),
        "most_common_hour": most_common_hour,
        "last_event_timestamp": last_event_timestamp,
    }
