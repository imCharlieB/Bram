import datetime
from zoneinfo import ZoneInfo

import pytest
from test_history import T0, Env

from bram.cleanup import PLAN_LIFE, Cleanup, Plan

UTC = ZoneInfo("UTC")


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path / "bram.db")
    for entity, name in (("sensor.den", "Den sensor"), ("sensor.attic", "Attic sensor")):
        e.say(entity, "temperature", "70", name, area=name.split()[0],
              values={"now": 70.0, "unit": "F"})
    e.say("binary_sensor.hall", "motion", "on", "Hall motion", area="Hall")
    e.minutes(200)
    e.c = Cleanup(e.h, None, lambda: e.now)
    e.ids = {d["name"]: d["id"] for d in e.c.usage()}
    yield e
    e.h.close()


def count(env, table):
    return len(env.rows(table))


def test_usage_is_biggest_first(env):
    usage = env.c.usage()
    assert usage[0]["bytes"] >= usage[1]["bytes"] > usage[2]["bytes"] > 0
    assert usage[0]["first"] == T0


def test_a_list_changes_nothing_and_is_exact(env):
    before = {t: count(env, t) for t in ("reading", "hourly", "change")}
    plan = env.c.plan("delete", [env.ids["Den sensor"]])
    assert {t: count(env, t) for t in before} == before
    env.minutes(8)  # arrives after the list
    more = count(env, "reading")
    env.c.apply(plan.id)
    assert more - count(env, "reading") == plan.rows["reading"]
    assert count(env, "change") == before["change"]
    with pytest.raises(ValueError):  # once
        env.c.apply(plan.id)


def test_lists_expire(env):
    plan = env.c.plan("delete", [env.ids["Den sensor"]])
    env.now += PLAN_LIFE
    with pytest.raises(ValueError):
        env.c.apply(plan.id)
    assert env.c.waiting() == []


def test_shorten_keeps_every_hour(env):
    device = env.ids["Den sensor"]
    plan = env.c.plan("shorten", [device])
    env.c.apply(plan.id)
    assert min(r[1] for r in env.rows("reading") if r[0] == device) == T0 + 3 * 3600
    hours = [r for r in env.rows("hourly") if r[0] == device]
    assert len(hours) == 3
    env.minutes(90)  # rolling up again must not disturb them
    assert [r for r in env.rows("hourly") if r[0] == device][:3] == hours


def test_before_a_date(env):
    device = env.ids["Den sensor"]
    env.c.apply(env.c.plan("delete", [device], T0 + 3600).id)
    left = [r[1] for r in env.rows("reading") if r[0] == device]
    assert min(left) == T0 + 3600


def test_stop_and_start_keeping(env):
    env.c.apply(env.c.plan("stop", [env.ids["Den sensor"], env.ids["Hall motion"]]).id)
    start = {t: count(env, t) for t in ("reading", "change")}
    env.say("binary_sensor.hall", "motion", "off", "Hall motion")
    env.minutes(60)
    assert count(env, "change") == start["change"]
    attic = [r for r in env.rows("reading") if r[0] == env.ids["Attic sensor"]]
    assert count(env, "reading") - start["reading"] <= 13 and attic
    env.h.close()
    env.open()  # still stopped after a restart
    env.say("binary_sensor.hall", "motion", "on", "Hall motion")
    assert [r[2] for r in env.rows("change") if r[0] == env.ids["Hall motion"]][-1] != "no"
    env.c = Cleanup(env.h, None, lambda: env.now)
    env.c.apply(env.c.plan("keep", [env.ids["Hall motion"]]).id)
    env.say("binary_sensor.hall", "motion", "off", "Hall motion")
    assert [r[2] for r in env.rows("change")][-1] == "no"


@pytest.mark.parametrize(("action", "devices"), [
    ("evil", [1]), ("delete", []), ("delete", [999]), ("delete", [1, 1, 999])])
def test_bad_lists(env, action, devices):
    with pytest.raises(ValueError):
        env.c.plan(action, devices)


@pytest.mark.parametrize(("text", "action", "names", "before"), [
    ("delete hall motion history", "delete", ["Hall motion"], None),
    ("purge motion data older than 2 weeks", "delete", ["Hall motion"], 14),
    ("delete the attic readings older than a year", "delete", ["Attic sensor"], 365),
    ("shorten den readings older than 30 days", "shorten", ["Den sensor"], 30),
    ("stop keeping the attic sensor", "stop", ["Attic sensor"], None)])
def test_words_make_a_list(env, text, action, names, before):
    plan = env.c.request(text, UTC)
    assert isinstance(plan, Plan) and plan.action == action
    assert plan.devices == [env.ids[n] for n in names]
    assert plan.before == (env.now if before is None else env.now - before * 86400)


def test_dates_in_words(env):
    plan = env.c.request("delete motion data before june", UTC)
    assert datetime.datetime.fromtimestamp(plan.before, UTC).date() == datetime.date(2023, 6, 1)
    plan = env.c.request("delete motion data before june 5, 2022", UTC)
    assert datetime.datetime.fromtimestamp(plan.before, UTC).date() == datetime.date(2022, 6, 5)


@pytest.mark.parametrize("text", [
    "turn off the hall light", "what was the temperature before june", "delete",
    "how old is the data"])
def test_other_talk_is_not_a_request(env, text):
    assert env.c.request(text, UTC) is None


@pytest.mark.parametrize("text", [
    "delete the kitchen history", "delete everything in the database",
    "delete motion data before the party", "delete motion data from last month",
    "delete motion data before february 31"])
def test_unclear_requests_make_no_list(env, text):
    assert isinstance(env.c.request(text, UTC), str) and env.c.waiting() == []


def test_asks_when_nearly_full_and_not_again_for_30_days(env):
    assert env.c.should_ask() is None
    env.limit = 0
    assert "% full" in env.c.should_ask()
    env.c.ask_later()
    assert env.c.should_ask() is None
    env.now += 31 * 86400
    assert env.c.should_ask()
