"""Patterns in history that could be a rule: a door, window, or lock that is often still open
or unlocked at the same hour of the evening. Code only, no model.

The owner decides in Home Assistant whether BRAM should check it each night (F4).
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable
from zoneinfo import ZoneInfo

HOURS = (20, 21, 22, 23, 0, 1)  # evening and night, when something left open matters
DAYS = 28
MIN_TIMES = 8  # at least this many nights
MIN_SHARE = 0.4  # and at least this share of the nights it was known
KINDS = ("opening", "lock")
OPEN = "yes"  # history keeps open and unlocked as "yes"


def evening_checks(changes: Iterable[tuple[str, str, str, float, str]], zone: ZoneInfo,
                   now: float) -> list[dict]:
    """From changes (entity, name, kind, at, state), in time order per entity: the latest
    evening hour each door, window, or lock is still often open or unlocked."""
    by_entity: dict[str, list[tuple[float, str]]] = {}
    names: dict[str, tuple[str, str]] = {}
    for entity_id, name, kind, at, state in changes:
        if kind in KINDS:
            by_entity.setdefault(entity_id, []).append((at, state))
            names[entity_id] = (name, kind)
    today = datetime.datetime.fromtimestamp(now, zone).date()
    found = []
    for entity_id, timeline in by_entity.items():
        best = None
        for hour in HOURS:
            yes = known = 0
            for back in range(1, DAYS + 1):
                day = today - datetime.timedelta(days=back - (1 if hour < 12 else 0))
                moment = datetime.datetime.combine(day, datetime.time(hour), zone).timestamp()
                if moment > now:
                    continue
                state = next((s for at, s in reversed(timeline) if at <= moment), None)
                if state in ("yes", "no"):  # unknown is never counted either way (B2)
                    known += 1
                    yes += state == OPEN
            # The latest hour it is still often open: a check then does not nag while the
            # door is still in use in the evening.
            if yes >= MIN_TIMES and yes >= MIN_SHARE * known:
                best = (hour, yes, known)
        if best is not None:
            name, kind = names[entity_id]
            found.append({"entity_id": entity_id, "name": name[:60], "kind": kind,
                          "hour": best[0], "times": best[1], "of": best[2]})
    return sorted(found, key=lambda f: -f["times"])[:10]


LEFT_ON = ("light", "switch", "fan")
SAMPLE = 900  # look every 15 minutes
MIN_DAYS = 5


def left_on_away(changes: Iterable[tuple[str, str, str, float, str]], zone: ZoneInfo,
                 now: float) -> list[dict]:
    """Lights, switches, and fans that were on while everyone was away, on enough days.
    Everyone is away only when every person is known to be away (B2)."""
    timelines: dict[str, list[tuple[float, str]]] = {}
    names: dict[str, tuple[str, str]] = {}
    for entity_id, name, kind, at, state in changes:
        timelines.setdefault(entity_id, []).append((at, state))
        names[entity_id] = (name, kind)
    people = [e for e, (_, kind) in names.items() if kind == "person"]
    things = [e for e, (_, kind) in names.items() if kind in LEFT_ON]
    if not people or not things:
        return []

    def state_at(entity_id: str, moment: float) -> str | None:
        return next((s for at, s in reversed(timelines[entity_id]) if at <= moment), None)

    start = now - DAYS * 86400
    days: dict[str, set[str]] = {e: set() for e in things}
    looked: set[str] = set()
    moment = start - start % SAMPLE + SAMPLE
    while moment < now:
        if all(state_at(p, moment) == "no" for p in people):  # everyone away, known
            day = datetime.datetime.fromtimestamp(moment, zone).date().isoformat()
            looked.add(day)
            for e in things:
                if state_at(e, moment) == "yes" and state_at(e, moment - 600) == "yes":
                    days[e].add(day)  # on for ten minutes while everyone was away
        moment += SAMPLE
    found = [{"entity_id": e, "name": names[e][0][:60], "kind": names[e][1], "hour": -1,
              "times": len(days[e]), "of": len(looked)}
             for e in things if len(days[e]) >= MIN_DAYS]
    return sorted(found, key=lambda f: -f["times"])[:10]
