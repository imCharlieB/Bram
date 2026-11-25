import datetime

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.bram.digest import Digest
from custom_components.bram.feed import Feed

LOCK, DOOR, ALEX = "lock.front", "binary_sensor.back", "person.alex"


def make(hass, **options):
    entry = MockConfigEntry(domain="bram", options={
        "entities": [LOCK, DOOR, ALEX], "phones": ["mobile_app_phone"], **options})
    feed = Feed(hass, entry)
    feed.connected = True
    return Digest(hass, entry, feed)


def put(hass, lock="locked", door="off", alex="home"):
    hass.states.async_set(LOCK, lock, {"friendly_name": "Front lock"})
    hass.states.async_set(DOOR, door, {"friendly_name": "Back door", "device_class": "door"})
    hass.states.async_set(ALEX, alex, {"friendly_name": "Alex"})


async def test_all_well(hass):
    put(hass)
    assert make(hass).text() == "Every lock and door I can see is locked and closed.\nHome: Alex"


@pytest.mark.parametrize(("states", "line"), [
    ({"lock": "unlocked"}, "Not locked: Front lock"), ({"lock": "jammed"}, "Not locked: Front"),
    ({"lock": "unavailable"}, "Can't see: Front lock"), ({"door": "on"}, "Open: Back door"),
    ({"alex": "Work"}, "Away: Alex")])
async def test_never_says_all_well_when_it_is_not(hass, states, line):
    put(hass, **states)
    text = make(hass).text()
    assert line in text and (states.get("alex") or "Every lock" not in text)


async def test_missing_device_is_not_well(hass):
    assert "Can't see" in make(hass).text() and "Every lock" not in make(hass).text()


async def test_sent_once_at_the_time_and_off_by_default(hass):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    put(hass)
    due = (dt_util.now() + datetime.timedelta(hours=2)).replace(second=0, microsecond=0)
    stop = make(hass, digest=due.strftime("%H:%M:%S")).start()
    make(hass).start()
    async_fire_time_changed(hass, due - datetime.timedelta(minutes=1))
    await hass.async_block_till_done()
    assert calls == []
    async_fire_time_changed(hass, due + datetime.timedelta(seconds=1))
    await hass.async_block_till_done()
    stop()
    assert len(calls) == 1 and "locked and closed" in calls[0].data["message"]
