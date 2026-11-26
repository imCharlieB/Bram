"""Quiet nights and how long doors stay open, worked out from history. Code only, no model.

The one record of what happened is history. Home Assistant gets these summaries and only
suggests; the owner decides (F4).
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable
from zoneinfo import ZoneInfo

START = 18  # a night is looked at from 6 PM until noon
STEP = 5  # minutes
STEPS = 18 * 60 // STEP
MIN_SEEN = STEPS * 9 // 10  # otherwise the night was not watched well enough
MIN_QUIET, MAX_QUIET = 180, 720
KEEP_DAYS = 60
MAX_OPENS = 200
KINDS = ("motion", "opening", "lock")
KNOWN = ("yes", "no")


def quiet_gap(active: Iterable[int]) -> list[int] | None:
    """The longest stretch with nothing happening, between two things that did."""
    points = sorted(set(active))
    gaps = [((b - a) * STEP, a, b) for a, b in zip(points, points[1:], strict=False)]
    if not gaps:
        return None
    size, start, end = max(gaps)
    # Too short is not a night; too long is an empty home or a missed evening.
    return [start * STEP, end * STEP] if MIN_QUIET <= size <= MAX_QUIET else None


def summarize(changes: Iterable[tuple[int, str, float, str]], seen: Iterable[int],
              zone: ZoneInfo, now: float) -> dict[str, dict[str, list[int]]]:
    """From changes (device, kind, at, state) in time order per device, and the 5-minute
    slots the server was watching, each finished night's quiet stretch and each finished
    day's door openings in minutes."""
    today = datetime.datetime.fromtimestamp(now, zone).date()
    active: list[float] = []
    opens: dict[str, list[int]] = {}
    last: dict[int, str] = {}
    opened: dict[int, float] = {}
    for device, kind, at, state in changes:
        before, last[device] = last.get(device), state
        if before not in KNOWN or state not in KNOWN or before == state:
            if state not in KNOWN:
                opened.pop(device, None)  # unknown is never a closing (B2)
            continue
        if not (kind == "motion" and state == "no"):
            active.append(at)
        if kind != "opening":
            continue
        if state == "yes":
            opened[device] = at
        elif (since := opened.pop(device, None)) is not None:
            day = datetime.datetime.fromtimestamp(at, zone).date()
            if day < today:
                minutes = opens.setdefault(day.isoformat(), [])
                if len(minutes) < MAX_OPENS:
                    minutes.append(max(1, round((at - since) / 60)))
    slots = set(seen)
    nights: dict[str, list[int]] = {}
    for back in range(1, KEEP_DAYS + 1):
        day = today - datetime.timedelta(days=back)
        start = datetime.datetime.combine(day, datetime.time(START), zone).timestamp()
        end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(12),
                                        zone).timestamp()
        if end > now:
            continue
        watched = sum(1 for s in range(int(start // 300) * 300, int(end), 300) if s in slots)
        if watched < MIN_SEEN:
            continue
        steps = [int((t - start) // (STEP * 60)) for t in active if start <= t < end]
        if gap := quiet_gap(steps):
            nights[day.isoformat()] = gap
    oldest = (today - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    return {"nights": nights, "opens": {d: v for d, v in opens.items() if d >= oldest}}
