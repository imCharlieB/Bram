import datetime
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.house_rules import DAILY, HouseRules

pytestmark = pytest.mark.usefixtures("custom")

LOCK, DOOR, ALEX, SAM = "lock.front", "binary_sensor.back", "person.alex", "person.sam"
ALL = {"night": True, "away": True, "left_open": True, "offline": True}


class Env:
    def __init__(self, hass):
        self.hass, self.now = hass, datetime.datetime(2026, 1, 1, 20, tzinfo=datetime.UTC)
        self.calls = async_mock_service(hass, "notify", "mobile_app_phone")

    async def start(self, entry=None, **options):
        self.entry = entry or MockConfigEntry(domain="bram", options={
            "entities": [LOCK, DOOR, ALEX, SAM], "phones": ["mobile_app_phone"],
            "night_from": "22:00:00", "night_to": "06:00:00", "open_minutes": 10, **options})
        self.rules = HouseRules(self.hass, self.entry)
        self.stop = await self.rules.start()

    async def set(self, entity, value):
        attrs = {"friendly_name": {LOCK: "Front lock", DOOR: "Back door"}.get(entity, entity)}
        if entity == DOOR:
            attrs["device_class"] = "door"
        self.hass.states.async_set(entity, value, attrs)
        await self.hass.async_block_till_done()

    def clock(self, hour):
        local = dt_util.as_local(self.now)
        target = local.replace(hour=hour, minute=0, second=0)
        self.now = dt_util.as_utc(target if target > local
                                  else target + datetime.timedelta(days=1))

    async def wait(self, minutes):
        for _ in range(int(minutes * 2)):
            self.now += datetime.timedelta(seconds=30)
            await self.rules.run()
        await self.hass.async_block_till_done()

    def texts(self):
        return [c.data["message"] for c in self.calls]


@pytest.fixture
async def env(hass):
    e = Env(hass)
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: e.now), patch(
            "homeassistant.util.dt.now", side_effect=lambda *a: dt_util.as_local(e.now)):
        e.clock(14)
        for entity, value in ((LOCK, "locked"), (DOOR, "off"), (ALEX, "home"), (SAM, "home")):
            await e.set(entity, value)
        yield e
        e.stop()
        await hass.async_block_till_done()


async def test_everything_is_off_by_default(env):
    await env.start()
    await env.set(LOCK, "unlocked")
    await env.set(DOOR, "on")
    env.clock(23)
    await env.wait(60)
    assert env.calls == []


async def test_lock_at_night_once_even_in_quiet_hours(env):
    await env.start(**ALL, quiet_from="21:00:00", quiet_to="07:00:00")
    await env.set(LOCK, "unlocked")
    await env.wait(30)
    assert env.calls == []
    env.clock(23)
    await env.wait(60)
    assert env.texts() == ["Front lock is unlocked, and it's night."]
    await env.set(LOCK, "locked")
    await env.wait(1)
    await env.set(LOCK, "unlocked")
    await env.wait(5)
    assert len(env.calls) == 2


async def test_brief_unlock_is_not_news(env):
    await env.start(**ALL)
    env.clock(23)
    await env.set(LOCK, "unlocked")
    await env.wait(1)
    await env.set(LOCK, "locked")
    await env.wait(10)
    assert env.calls == []


async def test_away_needs_every_person_known_away(env):
    await env.start(**ALL)
    await env.set(LOCK, "unlocked")
    await env.set(ALEX, "not_home")
    await env.wait(10)
    await env.set(SAM, "unavailable")
    await env.wait(10)
    assert env.calls == []
    await env.set(SAM, "Work")
    await env.wait(10)
    assert env.texts() == ["Front lock is unlocked, and everyone I track is away."]


async def test_no_people_means_never_away(env):
    await env.start(**ALL, entities=[LOCK])
    await env.set(LOCK, "unlocked")
    await env.wait(60)
    assert env.calls == []


async def test_door_left_open(env):
    await env.start(**ALL)
    await env.set(DOOR, "on")
    await env.wait(9)
    assert env.calls == []
    await env.wait(60)
    assert env.texts() == ["Back door has been open for 10 minutes."]


async def test_routine_rules_wait_for_quiet_hours(env):
    await env.start(**ALL, quiet_from="13:00:00", quiet_to="16:00:00")
    await env.set(DOOR, "on")
    await env.wait(60)
    assert env.calls == []
    await env.wait(70)
    assert len(env.calls) == 1


@pytest.mark.parametrize("value", ["unavailable", "unknown"])
async def test_offline_lock_is_told_and_is_not_locked(env, value):
    await env.start(**ALL)
    await env.set(LOCK, value)
    await env.wait(4)
    assert env.calls == []
    await env.wait(30)
    assert env.texts() == ["I can't see Front lock. It is offline."]


async def test_stop_these_and_allow_again(env):
    await env.start(**ALL)
    await env.set(DOOR, "on")
    await env.wait(15)
    action = env.calls[0].data["data"]["actions"][0]["action"]
    for bad in ("BRAM_QUIET_left_open:lock.other", "BRAM_QUIET_x:" + DOOR, "BRAM_QUIET_"):
        env.hass.bus.async_fire("mobile_app_notification_action", {"action": bad})
    env.hass.bus.async_fire("mobile_app_notification_action", {"action": action})
    await env.hass.async_block_till_done()
    assert env.rules._muted == [f"left_open:{DOOR}"]
    await env.set(DOOR, "off")
    await env.set(DOOR, "on")
    await env.wait(15)
    assert len(env.calls) == 1
    env.rules.allow_all()
    await env.wait(1)
    assert len(env.calls) == 2


async def test_restart_does_not_repeat(env):
    await env.start(**ALL)
    await env.set(DOOR, "on")
    await env.wait(15)
    await env.rules._store.async_save({"kinds": env.rules._kinds, "muted": [],
                                       "told": sorted(env.rules._told)})
    env.stop()
    await env.start(env.entry)
    await env.wait(30)
    assert len(env.calls) == 1


async def test_door_that_loses_its_type_is_still_watched(env):
    await env.start(**ALL)
    await env.rules.run()
    env.hass.states.async_set(DOOR, "on", {})
    await env.wait(15)
    assert len(env.calls) == 1


async def test_daily_limit(env):
    await env.start(**ALL)
    for _ in range(DAILY + 5):
        await env.set(DOOR, "on")
        await env.wait(11)
        await env.set(DOOR, "off")
        await env.wait(0.5)
    assert len(env.calls) == DAILY


async def test_failed_send_is_tried_again(env):
    await env.start(**ALL)
    await env.set(DOOR, "on")
    with patch("custom_components.bram.house_rules.notify", return_value=False):
        await env.wait(15)
    await env.wait(1)
    assert len(env.calls) == 1


async def test_several_routine_messages_become_one(env):
    doors = [f"cover.d{i}" for i in range(4)]
    await env.start(entities=doors, offline=True)
    for door in doors:
        env.hass.states.async_set(door, "closed", {"device_class": "garage"})
    await env.wait(1)
    for door in doors:
        env.hass.states.async_set(door, "unavailable", {"device_class": "garage"})
    await env.wait(10)
    assert len(env.calls) == 1 and env.texts()[0].count("offline") == 4
    assert env.calls[0].data["data"]["actions"] == []



async def test_windows_can_be_left_out(env):
    await env.start(left_open=True, away=True, open_windows=False)
    env.hass.states.async_set(DOOR, "on", {"device_class": "window", "friendly_name": "Window"})
    await env.wait(30)
    assert env.calls == []
    for person in (ALEX, SAM):
        await env.set(person, "not_home")
    await env.wait(5)
    assert env.texts() == ["Window is open, and everyone I track is away."]
