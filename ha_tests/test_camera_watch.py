"""Camera messages: fixed rules, the rest of the home, once, and the Frigate picture."""
import datetime
from unittest.mock import patch

import pytest
from homeassistant.core import Event
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.camera_watch import CameraWatch

pytestmark = pytest.mark.usefixtures("custom")
START = datetime.datetime(2026, 1, 1, 15, tzinfo=datetime.UTC)


def event(i, label="person", who="", zones=(), at=None):
    return {"id": f"e{i}", "label": label, "who": who, "zones": list(zones),
            "start": (at or START).timestamp(), "end": None, "picture": True,
            "summary": "x"}


class Env:
    def __init__(self, hass):
        self.hass, self.now, self.away, self.night = hass, START, False, False
        self.calls = async_mock_service(hass, "notify", "mobile_app_phone")
        self.notes = []

    async def start(self, **options):
        entry = MockConfigEntry(domain="bram", options={"phones": ["mobile_app_phone"],
                                                        **options})
        self.watch = CameraWatch(self.hass, entry, lambda: self.away, lambda: self.night,
                                 lambda *a: self.notes.append(a))
        await self.watch.start()

    async def see(self, camera, raw):
        await self.watch.weigh(camera, raw)
        await self.hass.async_block_till_done()

    def texts(self):
        return [c.data["message"] for c in self.calls]


@pytest.fixture
async def env(hass):
    e = Env(hass)
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: e.now), patch(
            "homeassistant.util.dt.now", side_effect=lambda *a: dt_util.as_local(e.now)):
        yield e


@pytest.mark.rule("F5")
async def test_nothing_until_turned_on(env):
    await env.start()
    env.away = env.night = True
    await env.see("front_door", event(1))
    await env.see("porch", event(2, "package"))
    assert env.calls == []


async def test_person_while_away(env):
    await env.start(camera_away=True)
    await env.see("front_door", event(1))
    assert env.calls == []  # someone is home
    env.away = True
    await env.see("front_door", event(2, who="Alex", zones=["porch"]))
    assert env.texts() == ["Alex at front door, and everyone I track is away. In porch."]
    data = env.calls[0].data["data"]
    assert data["tag"] == "bram_camera_person" and "image" not in data  # no Frigate here
    assert data["actions"][0] == {"action": "BRAM_CAMERA_front_door:person",
                                  "title": "Stop these"}


async def test_picture_from_the_frigate_integration(hass, env):
    hass.config.components.add("frigate")
    await env.start(camera_package=True)
    await env.see("porch", event("1.5-ab", "package"))
    assert env.calls[0].data["data"]["image"] == "/api/frigate/notifications/e1.5-ab/snapshot.jpg"


async def test_once_per_camera_and_across_cameras(env):
    await env.start(camera_night=True, camera_repeat=30)
    env.night = True
    await env.see("front_door", event(1))
    await env.see("front_door", event(1))  # the same event, updated
    env.now += datetime.timedelta(seconds=30)
    await env.see("driveway", event(2, at=env.now))  # walking past another camera
    env.now += datetime.timedelta(minutes=10)
    await env.see("front_door", event(3, at=env.now))  # same camera, too soon
    await env.see("driveway", event(4, at=env.now))  # another camera, later: news
    env.now += datetime.timedelta(minutes=31)
    await env.see("front_door", event(5, at=env.now))
    assert env.texts() == ["Someone at front door, and it's night.",
                           "Someone at driveway, and it's night.",
                           "Someone at front door, and it's night."]


async def test_stranger_and_known_people(env):
    await env.start(camera_stranger=True)
    await env.see("front_door", event(1, who="Alex"))
    await env.see("yard", event(2))
    assert env.texts() == ["A person Frigate does not know at yard."]


async def test_quiet_hours_hold_routine_but_not_urgent(env):
    await env.start(camera_package=True, camera_away=True, quiet_from="00:00:00",
                    quiet_to="23:59:00")
    await env.see("porch", event(1, "package"))
    assert env.calls == [] and any(n[1] == "held" for n in env.notes)
    env.away = True
    await env.see("porch", event(2))
    assert len(env.calls) == 1


async def test_old_events_are_not_news(env):
    await env.start(camera_package=True)
    await env.see("porch", event(1, "package", at=START - datetime.timedelta(hours=1)))
    assert env.calls == []


async def test_stop_these(hass, env):
    await env.start(camera_package=True, camera_repeat=1)
    await env.see("porch", event(1, "package"))
    env.watch.answered(Event("mobile_app_notification_action",
                             {"action": "BRAM_CAMERA_porch:package"}))
    env.now += datetime.timedelta(hours=2)
    await env.see("porch", event(2, "package", at=env.now))
    assert len(env.calls) == 1
    env.watch.allow_all()
    await env.see("porch", event(3, "package", at=env.now))
    assert len(env.calls) == 2
