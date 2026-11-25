import sqlite3
from zoneinfo import ZoneInfo

import pytest

from bram.history import GAP, HOUR, SLOT, TABLES, History
from bram.server import _detail
from bram.world import Event, World

T0 = 1_700_000_000 // 86400 * 86400  # a UTC midnight
UTC = ZoneInfo("UTC")


class Env:
    def __init__(self, path):
        self.path, self.now, self.on, self.limit = path, float(T0), True, 2048
        self.open()
        self.world = World("h1", clock=lambda: self.now)

    def open(self):
        self.h = History(self.path, lambda: self.on, lambda: self.limit, lambda: self.now)

    def say(self, entity, kind, state, name="", **detail):
        event = Event("h1", entity, kind, state, name or entity, detail)
        self.world.update(event)
        self.h.record(event, self.world)

    def ac(self, action="cooling", target=72, now=75.0, state="cool", area="Den"):
        self.say("climate.den", "climate", state, "Den AC", area=area, values={
            "action": action, "target": target, "now": now, "mode": state, "unit": "°F"})

    def minutes(self, count):
        for _ in range(count):
            self.now += 60
            self.world.heartbeat()
            self.h.sample([self.world])

    def days(self):
        return self.h.climate_days("h1", 7, UTC)

    def rows(self, table):
        with sqlite3.connect(self.path) as db:
            return db.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path / "bram.db")
    yield e
    e.h.close()


def test_off_writes_nothing(env):
    env.on = False
    env.ac()
    env.say("binary_sensor.d", "opening", "on")
    env.minutes(20)
    assert all(env.rows(t) == [] for t in (*TABLES, "device"))


def test_readings_are_averaged_and_rolled_into_hours(env):
    for value in (70.0, 80.0):
        env.say("sensor.t", "temperature", str(value), values={"now": value, "unit": "°F"})
        env.minutes(5)
    env.minutes(60)
    first = env.rows("reading")[0]
    assert first[2] == 70 and first[1] % SLOT == 0
    hours = env.rows("hourly")
    assert len(hours) == 1 and hours[0][2] == 70 and hours[0][4] == 80


def test_unknown_is_never_a_value(env):
    env.say("sensor.t", "temperature", "70", values={"now": 70.0, "unit": "°F"})
    env.minutes(6)
    count = len(env.rows("reading"))
    env.say("sensor.t", "temperature", "unavailable", values={"now": 70.0})
    env.minutes(30)
    assert len(env.rows("reading")) <= count + 1
    env.now += 1000  # silent, so not live
    env.h.sample([env.world])
    assert len(env.rows("reading")) <= count + 1


def test_runs_and_settings(env):
    env.ac()
    env.minutes(60)
    env.ac(target=70)
    env.minutes(30)
    env.ac("idle")
    env.minutes(30)
    (day,) = env.days()
    assert day["seconds"] == {"cooling": 5400} and day["starts"] == 2
    assert day["targets"] == {"72": 3600, "70": 1800} and not day["cut"]


def test_runs_are_split_at_midnight(env):
    env.now += 23.5 * HOUR
    env.ac()
    env.minutes(60)
    env.ac("idle")
    assert [round(d["seconds"]["cooling"]) for d in env.days()] == [1800, 1800]


@pytest.mark.parametrize("how", ["unavailable", "silent", "restart"])
def test_what_was_not_seen_is_not_counted(env, how):
    env.ac()
    env.minutes(10)
    if how == "unavailable":
        env.ac(state="unavailable")
        env.now += 5 * HOUR
    else:
        if how == "restart":
            env.h.close()
            env.open()
        env.now += 5 * HOUR
        env.ac()
    env.minutes(1)
    (day,) = env.days()
    assert day["seconds"]["cooling"] <= 12 * 60 and day["cut"]


def test_a_short_reconnect_continues_the_run(env):
    env.ac()
    env.minutes(5)
    env.h.lost("h1")
    env.now += GAP - 10
    env.ac()
    env.minutes(5)
    (day,) = env.days()
    assert day["starts"] == 1 and not day["cut"]


def test_thermostat_that_does_not_report_action_has_no_runs(env):
    env.ac(action=None)
    env.minutes(10)
    assert env.days() == [] and env.rows("run") == []


def test_outside_temperature(env):
    env.say("weather.home", "other", "sunny", values={"now": 95.0, "unit": "°F"})
    env.ac()
    env.minutes(5)
    assert env.days()[0]["outside"] == 95


def test_changes_record_lost_contact_as_unknown(env):
    env.say("binary_sensor.d", "opening", "on")
    env.say("binary_sensor.d", "opening", "on")
    env.now += 10
    env.h.lost("h1")
    env.now += 10
    env.say("binary_sensor.d", "opening", "on")
    assert [r[2] for r in env.rows("change")] == ["yes", "unknown", "yes"]


def test_server_down_is_unknown_from_when_it_was_last_alive(env):
    env.say("binary_sensor.d", "opening", "on")
    env.minutes(3)
    env.h.close()
    env.now += HOUR
    env.open()
    assert env.rows("change")[-1][1:] == (T0 + 180.0, "unknown")


def test_thermostat_is_compared_with_room_sensors(env):
    env.ac(now=75.0)
    for entity, area in (("sensor.den", "Den"), ("sensor.other", "Attic")):
        env.say(entity, "temperature", "72", entity, area=area, values={"now": 72.0, "unit": "°F"})
    env.minutes(30)
    (pair,) = env.h.compare("h1")
    assert (pair["sensor"], pair["apart"], pair["climate_avg"]) == ("sensor.den", -3, 75)
    assert env.h.compare("h2") == []


def test_past_readings_never_replace_measured_ones(env):
    env.say("sensor.t", "temperature", "70", values={"now": 70.0, "unit": "°F"})
    env.minutes(70)
    ((device, entity),) = env.h.to_import("h1")
    assert entity == "sensor.t"
    rows = [[T0, 1, 1, 1], [T0 - HOUR, 60, 61, 62], [T0 - 2 * HOUR, "x", 1, 1], "junk",
            [env.now + 9999, 1, 1, 1], [T0 - HOUR, float("nan"), 1, 1], [True, 1, 1, 1]]
    env.h.add_past(device, rows)
    env.h.add_past(device, "junk")
    assert [(r[1], r[3]) for r in env.rows("hourly")] == [(T0 - HOUR, 61), (T0, 70)]
    env.h.imported(device)
    assert env.h.to_import("h1") == []


def test_the_limit_shortens_old_readings_and_keeps_their_hours(env):
    env.say("sensor.t", "temperature", "70", values={"now": 70.0, "unit": "°F"})
    env.minutes(60 * 30)
    hours = len(env.rows("hourly"))
    env.limit = 0
    env.minutes(70)
    assert env.h.shortened and len(env.rows("hourly")) >= hours
    assert min(r[1] for r in env.rows("reading")) >= env.now - 26 * HOUR


def test_forget_one_home_or_all(env):
    env.say("binary_sensor.d", "opening", "on")
    env.h.record(Event("h2", "binary_sensor.d", "opening", "on"), World("h2"))
    env.h.forget("h1")
    assert len(env.rows("device")) == 1
    env.h.forget()
    assert all(env.rows(t) == [] for t in (*TABLES, "device"))
    env.say("binary_sensor.d", "opening", "off")
    assert len(env.rows("change")) == 1


def test_a_copy_taken_while_running_opens_cleanly(env, tmp_path):
    env.ac()
    env.minutes(10)
    copy = tmp_path / "copy"
    copy.mkdir()
    for file in tmp_path.glob("bram.db*"):
        (copy / file.name).write_bytes(file.read_bytes())
    other = History(copy / "bram.db", lambda: True, clock=lambda: env.now)
    assert other.healthy and other.climate_days("h1", 7, UTC)
    other.close()


def test_values_from_home_assistant_are_checked():
    found = _detail({"values": {"now": 70, "target": float("inf"), "low": "x", "high": True,
                                "mode": "cool" * 50, "action": 5, "evil": "x"}})
    assert found["values"] == {"now": 70.0, "mode": ("cool" * 50)[:40]}
