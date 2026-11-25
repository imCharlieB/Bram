import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.problem_watch import DAILY, STARTING, ProblemWatch
from custom_components.bram.problems import Finder, Problem

pytestmark = pytest.mark.usefixtures("custom")


class Env:
    def __init__(self, hass, freezer):
        self.hass, self.freezer = hass, freezer
        self.entry = MockConfigEntry(domain="bram", options={
            "problem_watch": True, "phones": ["mobile_app_phone"], "entities": []})
        self.finder = Finder(hass, self.entry)

    async def texts(self, night=False):
        return [p.text for p in await self.finder.find(night)]

    def wait(self, **kw):
        self.freezer.tick(datetime.timedelta(**kw))

    def device(self, number, platform="zha", entry=None, domain="sensor"):
        entry = entry or self.home
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={(platform, number)},
            name=f"Thing {number}")
        return er.async_get(self.hass).async_get_or_create(
            domain, platform, number, device_id=device.id, config_entry=entry,
            suggested_object_id=f"{platform}_{number}").entity_id


@pytest.fixture
def env(hass, freezer):
    e = Env(hass, freezer)
    e.home = MockConfigEntry(domain="zha", title="Zigbee", state=ConfigEntryState.LOADED)
    e.home.add_to_hass(hass)
    yield e
    for entry in hass.config_entries.async_entries():
        entry.mock_state(hass, ConfigEntryState.NOT_LOADED)


async def test_a_healthy_home_has_nothing(env):
    env.hass.states.async_set(env.device("1"), "5")
    env.wait(hours=1)
    assert await env.texts() == [] and env.finder.not_run == []


async def test_failed_integrations_only_after_half_an_hour(env):
    for state in (ConfigEntryState.SETUP_ERROR, ConfigEntryState.SETUP_RETRY):
        MockConfigEntry(domain="demo", title="http://bob@10.0.0.5", state=state).add_to_hass(
            env.hass)
    MockConfigEntry(domain="moonraker", state=ConfigEntryState.SETUP_RETRY).add_to_hass(env.hass)
    assert await env.texts() == []
    env.wait(minutes=31)
    said = await env.texts()
    assert len(said) == 2 and "10.0.0.5" not in str(said) and "bob" not in str(said)


async def test_repeating_errors(env):
    item = {"name": "homeassistant.components.zha", "level": "ERROR", "count": 500,
            "source": ("x", 1), "message": ["Lost token=abc123"]}
    env.hass.data["system_log"] = SimpleNamespace(
        records=SimpleNamespace(to_list=lambda: [item]))
    assert await env.texts() == []  # what was there at the start is not a pattern
    item["count"] = 505
    assert await env.texts() == []
    item["count"] = 520
    (text,) = await env.texts()
    assert text.startswith("zha keeps logging the same error") and "abc123" not in text
    env.wait(hours=3)
    assert await env.texts() == []
    item["count"] = 5  # restarted
    assert await env.texts() == []
    del env.hass.data["system_log"]


async def test_repairs(env):
    ir.async_create_issue(env.hass, "demo", "a", is_fixable=False, translation_key="old_thing",
                          severity=ir.IssueSeverity.ERROR)
    ir.async_create_issue(env.hass, "bram", "b", is_fixable=False, translation_key="x",
                          severity=ir.IssueSeverity.ERROR)
    (text,) = await env.texts()
    assert "demo: old thing" in text


async def test_batteries_have_a_margin_and_unknown_is_not_charged(env):
    def level(value):
        env.hass.states.async_set("sensor.b", value, {"device_class": "battery",
                                                      "friendly_name": "Remote"})
    for value, said in (("16", 0), ("14", 1), ("18", 1), ("unavailable", 1), ("25", 0),
                        ("unavailable", 0)):
        level(value)
        assert len(await env.texts()) == said, value


async def test_phone_battery_only_at_night_and_not_charging(env):
    battery = env.device("p", "mobile_app")
    env.hass.states.async_set(battery, "10", {"device_class": "battery"})
    assert await env.texts(night=False) == []
    assert len(await env.texts(night=True)) == 1
    device = er.async_get(env.hass).async_get(battery).device_id
    state = er.async_get(env.hass).async_get_or_create(
        "sensor", "mobile_app", "s", device_id=device, suggested_object_id="p_battery_state")
    env.hass.states.async_set(state.entity_id, "charging")
    assert await env.texts(night=True) == []


async def test_offline_devices_and_whole_integrations(env):
    ids = [env.device(str(i)) for i in range(4)]
    for entity in ids:
        env.hass.states.async_set(entity, "unavailable" if entity == ids[0] else "5")
    for skipped in (env.device("a", "octoprint"), env.device("tv", "cast", None, "media_player")):
        env.hass.states.async_set(skipped, "unavailable")
    assert await env.texts() == []
    env.wait(minutes=31)
    assert await env.texts() == ["Thing 0 is offline"]
    for entity in ids:
        env.hass.states.async_set(entity, "unavailable")
    other = MockConfigEntry(domain="hue", title="Hue", state=ConfigEntryState.LOADED)
    other.add_to_hass(env.hass)
    for i in range(3):
        env.hass.states.async_set(env.device(str(i), "hue", other), "unavailable")
    env.wait(minutes=31)
    assert "Everything from Hue is offline" in await env.texts()


async def test_safety_sensors_are_left_to_their_own_rules(env):
    entity = env.device("leak", domain="binary_sensor")
    env.entry = MockConfigEntry(domain="bram", options={"entities": [entity]})
    env.finder = Finder(env.hass, env.entry)
    env.hass.states.async_set(entity, "unavailable", {"device_class": "moisture"})
    env.wait(minutes=31)
    assert await env.texts() == []


async def test_stuck_sensors(env):
    good, target = env.device("1"), env.device("target_temp")
    for entity in (good, target):
        env.hass.states.async_set(entity, "70", {"device_class": "temperature",
                                                 "friendly_name": "Den"})
    env.wait(hours=47)
    assert await env.texts() == []
    env.wait(hours=2)
    assert await env.texts() == [
        "Den has said 70 for more than 2 days. The sensor may be stuck"]


async def test_automations(env):
    env.hass.states.async_set("automation.a", "on", {"friendly_name": "Night"})
    env.hass.states.async_set("automation.b", "unavailable", {"friendly_name": "Broken"})
    env.hass.states.async_set("automation.c", "off")
    env.hass.states.async_set("light.real", "on")
    env.hass.data["automation"] = SimpleNamespace(entities=[
        SimpleNamespace(entity_id=f"automation.{n}",
                        referenced_entities={"light.real", "light.gone"}) for n in "abc"])
    said = await env.texts()
    del env.hass.data["automation"]
    assert said == ["Automation Night uses light.gone, which does not exist",
                    "Automation Broken could not be loaded"]


async def test_backups(env):
    entity = er.async_get(env.hass).async_get_or_create(
        "sensor", "backup", "last_successful_automatic_backup").entity_id
    env.hass.states.async_set(entity, "unknown")
    assert await env.texts() == []  # may be done another way
    env.hass.states.async_set(entity, dt_util.utcnow().isoformat())
    assert await env.texts() == []
    env.wait(days=9)
    assert "last automatic backup" in (await env.texts())[0]


async def test_a_broken_check_is_said_and_the_rest_run(env):
    with patch.object(Finder, "_repairs", side_effect=RuntimeError):
        await env.texts()
    assert env.finder.not_run == ["Repairs"]


class Watch:
    def __init__(self, hass, freezer, **options):
        self.hass, self.freezer, self.found, self.notes = hass, freezer, [], []
        self.calls = async_mock_service(hass, "notify", "mobile_app_phone")
        self.watch = ProblemWatch(hass, MockConfigEntry(domain="bram", options={
            "problem_watch": True, "phones": ["mobile_app_phone"], **options}),
            lambda: False, lambda *a: self.notes.append(a[:2]))
        self.watch._finder = SimpleNamespace(find=self.find, not_run=[])

    async def find(self, night):
        return [Problem(k, "low", f"{k} is wrong") for k in self.found]

    async def run(self, *found, minutes=10):
        self.found = found
        self.freezer.tick(datetime.timedelta(minutes=minutes))
        await self.watch.run()

    def texts(self):
        return [c.data["message"] for c in self.calls]


@pytest.fixture
async def watch(hass, freezer):
    w = Watch(hass, freezer)
    w.stop = await w.watch.start()
    yield w
    w.stop()
    await hass.async_block_till_done()


async def test_told_once_then_fixed(watch):
    watch.freezer.tick(STARTING)
    await watch.run("a")
    await watch.run("a")
    assert watch.texts() == ["a is wrong"]
    await watch.run()
    await watch.run()
    await watch.run()
    assert watch.texts() == ["a is wrong", "Fixed: a is wrong"]
    assert [n for n in watch.notes if n[1] != "open"] == [
        ("problems:a", "sent"), ("problems:a", "closed")]
    await watch.run("a")  # back within a day
    assert len(watch.texts()) == 2


async def test_nothing_is_called_fixed_just_after_a_start(watch):
    watch.watch._told = {"a": ["a is wrong", 0.0, None]}
    for _ in range(6):
        await watch.run()
    assert watch.texts() == []


async def test_grouped_and_many(watch):
    await watch.run("a", "b", "c")
    assert watch.texts()[0].count("wrong") == 3
    await watch.run(*[f"p{i}" for i in range(20)])
    assert "20 problems" in watch.texts()[1] and len(watch.texts()) == 2
    await watch.run(*[f"p{i}" for i in range(20)])
    assert len(watch.texts()) == 2


@pytest.mark.rule("E8")
async def test_stop_these_quiet_hours_and_daily_limit(hass, freezer, watch):
    await watch.run("a")
    action = watch.calls[0].data["data"]["actions"][0]["action"]
    hass.bus.async_fire("mobile_app_notification_action", {"action": action})
    await hass.async_block_till_done()
    assert watch.watch._muted == ["a"]
    for i in range(DAILY + 5):
        await watch.run(f"k{i}", minutes=1)
    assert len(watch.calls) == DAILY
    quiet = Watch(hass, freezer, quiet_from="00:00:00", quiet_to="23:59:59")
    await quiet.run("a")
    assert quiet.texts() == []


async def test_a_check_that_did_not_run_fixes_nothing(watch):
    watch.freezer.tick(STARTING)
    await watch.run("a")
    watch.watch._finder.not_run = ["Repairs"]
    for _ in range(4):
        await watch.run()
    assert watch.texts() == ["a is wrong"] and ("problems:a", "closed") not in watch.notes


async def test_off_does_nothing(hass, freezer):
    w = Watch(hass, freezer, problem_watch=False)
    (await w.watch.start())()
    assert w.texts() == []
