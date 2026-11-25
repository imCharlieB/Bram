import datetime
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.feed import Feed
from custom_components.bram.home_alerts import DAILY_NOTICES, REPEAT, HomeAlerts

pytestmark = pytest.mark.usefixtures("custom")

LEAK = "binary_sensor.leak"
WET = {"device_class": "moisture", "friendly_name": "Laundry leak"}
START = datetime.datetime(2026, 1, 1, 12, tzinfo=datetime.UTC)


class Env:
    def __init__(self, hass):
        self.hass, self.now, self.to_server = hass, START, []
        self.calls = async_mock_service(hass, "notify", "mobile_app_phone")

    async def start(self, entry=None, **options):
        self.entry = entry or MockConfigEntry(domain="bram", options={
            "entities": [LEAK], "phones": ["mobile_app_phone"], **options})
        self.feed = Feed(self.hass, self.entry)
        self.feed.connected = True
        self.feed.send = lambda m: self.to_server.append(m) or True
        self.alerts = HomeAlerts(self.hass, self.entry, self.feed)
        self.stop = await self.alerts.start()
        await self.hass.async_block_till_done()

    async def set(self, value, entity=LEAK, attrs=WET):
        if value is None:
            self.hass.states.async_remove(entity)
        else:
            self.hass.states.async_set(entity, value, attrs)
        await self.hass.async_block_till_done()

    async def wait(self, seconds, step=30):
        end = self.now + datetime.timedelta(seconds=seconds)
        while self.now < end:
            self.now = min(self.now + datetime.timedelta(seconds=step), end)
            await self.alerts.run()
        await self.hass.async_block_till_done()

    async def press(self, action):
        self.hass.bus.async_fire("mobile_app_notification_action", {"action": action})
        await self.hass.async_block_till_done()

    def texts(self):
        return [c.data["message"] for c in self.calls]

    def safety(self):
        return [c for c in self.calls if c.data["title"].startswith("BRAM alert")]


@pytest.fixture
async def env(hass):
    e = Env(hass)
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: e.now), patch(
            "homeassistant.util.dt.now", side_effect=lambda *a: dt_util.as_local(e.now)):
        await e.set("off")
        yield e
        e.stop()
        await hass.async_block_till_done()


def action(call):
    return call.data["data"]["actions"][0]["action"]


@pytest.mark.rule("C1")
@pytest.mark.rule("C2")
async def test_leak_is_sent_at_once_without_the_server(env):
    await env.start()
    env.feed.connected = False
    await env.set("on")
    assert env.texts() == ["Water leak detected: Laundry leak."]
    data = env.calls[0].data["data"]
    assert data["importance"] == "max" and data["priority"] == "high"


@pytest.mark.rule("C4")
async def test_repeats_to_limit_then_stops(env):
    await env.start()
    await env.set("on")
    await env.wait(86400, 60)
    assert len(env.calls) == len(REPEAT) + 1


@pytest.mark.parametrize(("device_class", "words"), [
    ("smoke", "Smoke"), ("carbon_monoxide", "CARBON MONOXIDE"), ("gas", "GAS"),
    ("heat", "heat"), ("safety", "Safety problem"), ("tamper", "Safety problem")])
async def test_every_safety_sensor_alerts(env, device_class, words):
    await env.start(entities=["binary_sensor.s"])
    await env.set("on", "binary_sensor.s", {"device_class": device_class})
    assert len(env.safety()) == 1 and words in env.texts()[0]
    await env.wait(150)
    assert len(env.safety()) == 2


@pytest.mark.parametrize("device_class", ["problem", "battery", "power", None])
async def test_other_sensors_do_not(env, device_class):
    await env.start(entities=["binary_sensor.s"])
    await env.set("on", "binary_sensor.s", {"device_class": device_class})
    await env.set("unavailable", "binary_sensor.s", {"device_class": device_class})
    await env.wait(900)
    assert env.calls == []


async def test_acknowledge_stops_and_a_new_leak_starts_again(env):
    await env.start()
    await env.set("on")
    await env.press("BRAM_ACK_wrong")
    await env.wait(150)
    assert len(env.calls) == 2
    await env.press(action(env.calls[0]))
    await env.wait(86400, 600)
    assert len(env.calls) == 2
    await env.set("on", attrs={**WET, "battery": 1})
    assert len(env.calls) == 2
    await env.set("off")
    await env.set("on")
    assert len(env.calls) == 3


async def test_drying_out_does_not_stop_an_unacknowledged_alert(env):
    await env.start()
    await env.set("on")
    await env.set("off")
    await env.wait(150)
    assert "since cleared" in env.texts()[1]
    await env.press(action(env.calls[1]))
    await env.wait(86400, 600)
    assert len(env.calls) == 2


async def test_sensor_that_loses_its_type_still_alerts(env):
    await env.start()
    await env.set("on", attrs={})
    assert len(env.safety()) == 1


@pytest.mark.rule("B2")
async def test_unavailable_is_not_dry(env):
    await env.start()
    await env.set("on")
    await env.press(action(env.calls[0]))
    await env.set("unavailable")
    await env.set("on")
    assert len(env.safety()) == 1


@pytest.mark.rule("C3")
async def test_quiet_hours_and_mute_never_hold_back_safety(env):
    await env.start(quiet_from="00:00:00", quiet_to="23:59:00")
    await env.press(f"BRAM_MUTE_{LEAK}")
    await env.set("on")
    assert len(env.safety()) == 1


async def test_survives_restart(env):
    await env.start()
    await env.set("on")
    await env.hass.async_block_till_done()
    env.stop()
    await env.start(env.entry)
    await env.wait(150)
    assert len(env.calls) == 2 and "reminder 1" in env.calls[1].data["title"]


async def test_already_wet_at_startup(env):
    await env.set("on")
    await env.start()
    assert len(env.calls) == 1


async def test_failed_send_is_retried_and_shown_in_home_assistant(env):
    await env.start()
    with patch("custom_components.bram.home_alerts.notify", return_value=False):
        await env.set("on")
    assert env.calls == []
    await env.wait(70)
    assert len(env.calls) == 1


async def test_silent_sensor_waits_tells_once_and_reports_back(env):
    await env.start()
    await env.set("unavailable")
    await env.wait(240)
    await env.set("off")
    await env.wait(3600)
    assert env.calls == []
    await env.set(None)
    await env.wait(86400, 600)
    assert len(env.calls) == 1 and "stopped reporting" in env.texts()[0]
    await env.set("off")
    await env.wait(60)
    assert env.texts()[1] == "Reporting again: Laundry leak is dry"


@pytest.mark.rule("E8")
async def test_mute_stops_silent_notices(env):
    await env.start()
    await env.set("unavailable")
    await env.wait(400)
    await env.press(action(env.calls[0]))
    await env.set("off")
    await env.set("unavailable")
    await env.wait(3600)
    assert len(env.calls) == 1


async def test_stopped_messages_can_be_allowed_again(env):
    await env.start()
    await env.press(f"BRAM_MUTE_{LEAK}")
    env.alerts.allow_all()
    await env.set("unavailable")
    await env.wait(400)
    assert len(env.calls) == 1


@pytest.mark.rule("E8")
async def test_quiet_hours_delay_notices(env):
    local = dt_util.as_local(START).time()
    later = (dt_util.as_local(START) + datetime.timedelta(hours=2)).time()
    await env.start(quiet_from=local.isoformat(), quiet_to=later.isoformat())
    await env.set("unavailable")
    await env.wait(7000, 100)
    assert env.calls == []
    await env.wait(400)
    assert len(env.calls) == 1


@pytest.mark.rule("E8")
async def test_daily_limit(env):
    await env.start()
    for i in range(DAILY_NOTICES + 4):
        env.alerts._notice(f"k{i}", "x", None, False)
        await env.alerts.run()
    await env.wait(60)
    assert len(env.calls) == DAILY_NOTICES


async def test_server_lost_and_back(env):
    await env.start()
    env.feed.connected = False
    env.alerts._server_changed()
    await env.wait(120)
    assert env.calls == []
    await env.wait(120)
    assert "not answering" in env.texts()[0]
    env.feed.connected = True
    env.alerts._server_changed()
    await env.wait(30)
    assert env.texts()[1] == "The BRAM Server is back."


async def test_escalation_is_off_by_default(env):
    await env.start()
    await env.set("on")
    await env.wait(3600)
    assert env.to_server == []


async def test_escalation_only_when_unacknowledged(env):
    await env.start(escalate=True)
    await env.set("on")
    await env.wait(240)
    assert env.to_server == []
    await env.wait(120)
    assert env.to_server == [{"type": "escalate", "entity_id": LEAK}]
    await env.press(action(env.calls[0]))
    assert env.to_server[-1] == {"type": "deescalate", "entity_id": LEAK}


async def test_no_phone_still_shows_in_home_assistant(env):
    await env.start(phones=[])
    with patch("custom_components.bram.notifier.persistent_notification.async_create") as shown:
        await env.set("on")
    assert env.calls == [] and shown.called


async def test_safety_only_phones_get_safety_and_nothing_else(env):
    other = async_mock_service(env.hass, "notify", "mobile_app_other")
    await env.start(safety_phones=["mobile_app_other", "mobile_app_phone"])
    await env.set("unavailable")
    await env.wait(400)
    assert len(env.calls) == 1 and other == []
    await env.set("on")
    assert len(env.safety()) == 1  # once, though it is in both lists
    assert [c.data["message"] for c in other] == ["Water leak detected: Laundry leak."]
    await env.press(action(other[0]))  # anyone may acknowledge
    await env.wait(600)
    assert len(env.safety()) == 1 and len(other) == 1


async def test_safety_only_phones_work_alone(env):
    other = async_mock_service(env.hass, "notify", "mobile_app_other")
    await env.start(phones=[], safety_phones=["mobile_app_other"])
    await env.set("on")
    assert len(other) == 1


async def test_only_chosen_safety_sensors(env):
    await env.start(entities=[LEAK, "lock.a", "light.a"])
    await env.set("unlocked", "lock.a", {})
    await env.set("on", "light.a", {})
    await env.set("on", "binary_sensor.other", WET)
    await env.wait(600)
    assert env.calls == []


async def test_several_notices_become_one(env):
    await env.start()
    for i in range(3):
        env.alerts._notice(f"k{i}", f"text {i}", None, False)
    await env.alerts.run()
    assert [c.data["message"] for c in env.calls] == ["text 0\ntext 1\ntext 2"]
