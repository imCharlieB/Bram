"""Nightly checks learned from history: suggested, approved by an admin, then checked (F4)."""
import datetime
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.checks import Checks
from custom_components.bram.house_rules import HouseRules

pytestmark = pytest.mark.usefixtures("custom")
GARAGE = "cover.garage"
FOUND = {"entity_id": GARAGE, "name": "Garage door", "kind": "opening", "hour": 23,
         "times": 19, "of": 28}


@pytest.fixture
async def entry(hass):
    made = MockConfigEntry(domain="bram", options={
        "learn": True, "entities": [GARAGE, "lock.front"], "phones": ["mobile_app_phone"]})
    made.add_to_hass(hass)
    hass.states.async_set(GARAGE, "closed", {"device_class": "garage",
                                             "friendly_name": "Garage door"})
    return made


@pytest.mark.rule("F4")
async def test_a_suggested_check_changes_nothing_until_approved(hass, entry):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    checks = Checks(hass, entry)
    await checks.start()
    assert checks.received([FOUND, {**FOUND, "entity_id": "cover.not_shared"},
                            {**FOUND, "hour": 15}, {**FOUND, "extra": 1}, "nope"]) == 1
    await hass.async_block_till_done()
    assert calls[0].data["data"]["url"] == "/bram-review"
    (item,) = checks.review()
    assert item["title"] == "Check Garage door at 11 PM?"
    assert "On 19 of the last 28 nights, Garage door was still open at 11 PM" in item["text"]
    assert "checks" not in entry.options  # nothing until an admin answers
    with patch.object(hass.config_entries, "async_schedule_reload"):
        assert checks.answer(item["id"], "approve", "Owner")
    assert entry.options["checks"] == [{"entity_id": GARAGE, "hour": 23}]
    assert checks.review() == []
    assert checks.received([FOUND]) == 0  # already a check


async def test_never_and_rules_that_already_tell(hass, entry):
    checks = Checks(hass, entry)
    await checks.start()
    checks.received([FOUND])
    (item,) = checks.review()
    assert checks.answer(item["id"], "never", "")
    assert checks.received([FOUND]) == 0
    hass.config_entries.async_update_entry(entry, options={
        **entry.options, "open_night": True, "night_from": "22:00:00", "night_to": "06:00:00"})
    other = Checks(hass, entry)
    await other.start()
    assert other.received([{**FOUND, "entity_id": "lock.front", "kind": "lock"}]) == 1  # no rule
    assert other.received([{**FOUND, "entity_id": GARAGE}]) == 0


async def test_learning_off_suggests_nothing(hass, entry):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "learn": False})
    checks = Checks(hass, entry)
    await checks.start()
    assert checks.received([FOUND]) == 0


async def test_an_approved_check_tells_at_its_hour(hass):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    zone = dt_util.get_default_time_zone()
    now = [dt_util.as_utc(datetime.datetime(2026, 1, 1, 22, 50, tzinfo=zone))]
    entry = MockConfigEntry(domain="bram", options={
        "entities": [GARAGE], "phones": ["mobile_app_phone"],
        "checks": [{"entity_id": GARAGE, "hour": 23}]})
    hass.states.async_set(GARAGE, "open", {"device_class": "garage",
                                           "friendly_name": "Garage door"})
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: now[0]), patch(
            "homeassistant.util.dt.now", side_effect=lambda *a: dt_util.as_local(now[0])):
        rules = HouseRules(hass, entry)
        stop = await rules.start()
        await rules.run()
        assert calls == []  # not yet 11 PM
        now[0] += datetime.timedelta(minutes=15)
        await rules.run()
        await hass.async_block_till_done()
        stop()
    assert [c.data["message"] for c in calls] == [
        "Garage door is still open. Your nightly check at 11 PM."]
