"""Patterns that could be a nightly check: found by code from history, never by a model."""
import datetime
from zoneinfo import ZoneInfo

from bram.patterns import evening_checks

ZONE = ZoneInfo("America/Chicago")
NOW = datetime.datetime(2026, 11, 27, 15, tzinfo=ZONE).timestamp()


def night(days_ago, hour, minute=0):
    day = datetime.date(2026, 11, 27) - datetime.timedelta(days=days_ago)
    return datetime.datetime.combine(day, datetime.time(hour, minute), ZONE).timestamp()


def test_a_garage_often_open_late_is_a_pattern():
    changes = []
    for back in range(1, 29):
        changes.append(("cover.garage", "Garage door", "opening", night(back, 18), "yes"))
        if back % 3:  # two of every three nights it is shut only at midnight
            changes.append(("cover.garage", "Garage door", "opening", night(back, 23, 50),
                            "no"))
        else:
            changes.append(("cover.garage", "Garage door", "opening", night(back, 20, 30),
                            "no"))
        changes.append(("lock.front", "Front door", "lock", night(back, 21), "no"))
    changes.sort(key=lambda c: (c[0], c[3]))
    (found,) = evening_checks(changes, ZONE, NOW)
    assert found["entity_id"] == "cover.garage" and found["hour"] == 23  # the latest hour
    assert found["times"] == 19 and found["of"] == 28  # every night but each third


def test_unknown_never_counts_and_rare_is_not_a_pattern():
    changes = [("lock.back", "Back door", "lock", night(back, 22), "unknown")
               for back in range(1, 29)]
    changes += [("lock.back", "Back door", "lock", night(2, 21), "yes"),
                ("lock.back", "Back door", "lock", night(2, 23), "no")]
    assert evening_checks(sorted(changes, key=lambda c: c[3]), ZONE, NOW) == []
