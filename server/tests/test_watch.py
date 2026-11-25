import sqlite3

import pytest

from bram.audit import Audit
from bram.watch import Watcher
from bram.world import Answer, Event, World


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def world(clock):
    return World("h1", max_silence=90, clock=clock)


@pytest.fixture
def audit():
    log = Audit(":memory:")
    yield log
    log.close()


def ev(entity, kind, state, house="h1"):
    return Event(house, entity, kind, state)


@pytest.mark.parametrize("kind", ["person", "leak", "smoke", "opening", "lock", "other"])
@pytest.mark.parametrize("state", ["unknown", "unavailable", "", "None"])
def test_unusable_states_are_unknown(world, kind, state):
    world.update(ev("x", kind, state))
    assert world.check("x") is Answer.UNKNOWN


@pytest.mark.parametrize("state", ["jammed", "locking", "opening"])
def test_unrecognized_lock_state_is_not_locked(world, state):
    world.update(ev("lock.a", "lock", state))
    assert world.check("lock.a") is Answer.UNKNOWN


def test_missing_stale_and_disconnected_are_unknown(world, clock):
    assert world.check("lock.a") is Answer.UNKNOWN
    world.update(ev("lock.a", "lock", "locked"))
    assert world.check("lock.a") is Answer.NO
    clock.now = 91
    assert world.check("lock.a") is Answer.UNKNOWN
    world.heartbeat()
    assert world.check("lock.a") is Answer.NO
    world.disconnected()
    world.heartbeat()
    assert world.check("lock.a") is Answer.UNKNOWN


def test_empty_house_needs_every_person_known_away(world):
    assert world.anyone_home() is Answer.UNKNOWN
    world.update(ev("person.a", "person", "not_home"))
    assert world.anyone_home() is Answer.NO
    world.update(ev("person.b", "person", "unavailable"))
    assert world.anyone_home() is Answer.UNKNOWN
    world.update(ev("person.b", "person", "Work"))
    assert world.anyone_home() is Answer.NO
    world.update(ev("person.b", "person", "home"))
    assert world.anyone_home() is Answer.YES


def test_houses_do_not_mix(world):
    with pytest.raises(ValueError):
        world.update(ev("x", "leak", "on", house="h2"))


def test_audit_is_append_only_and_per_house(audit):
    audit.record("h1", "t", "d", "r", "ok")
    with pytest.raises(sqlite3.Error):
        audit._db.execute("DELETE FROM audit")
    with pytest.raises(sqlite3.Error):
        audit._db.execute("UPDATE audit SET reason = 'x'")
    assert len(audit.entries("h1")) == 1 and audit.entries("h2") == []


def test_watcher_logs_once_per_change(world, audit):
    watcher = Watcher(world, audit)
    said = [watcher.handle(ev("s", "leak", s)) for s in ("off", "on", "on", "off", "unavailable")]
    assert said[0] is None and "leak" in said[1] and said[2] is None and said[3] is None
    assert "cannot check" in said[4]
    assert "reporting again" in watcher.handle(ev("s", "leak", "off"))
    rows = audit.entries("h1")
    assert len(rows) == 3 and {r["decision"] for r in rows} == {"noticed"}


@pytest.mark.parametrize("kind", ["motion", "light", "person"])
def test_everyday_activity_is_not_stored(world, audit, kind):
    watcher = Watcher(world, audit)
    for state in ("on", "off", "unavailable", "on"):
        watcher.handle(ev("x", kind, state))
    assert audit.entries("h1") == []


def test_names_are_cleaned(world, audit):
    event = Event("h1", "s", "leak", "on", "Laundry\n\x00 leak")
    assert Watcher(world, audit).handle(event) == "Water leak detected. (Laundry leak)"


def test_leak_already_present_at_startup_is_reported(world, audit):
    assert Watcher(world, audit).handle(ev("s", "leak", "on"))
