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
    env.now += __import__("datetime").timedelta(hours=1)
    await env.see("porch", {**event("2", "package", at=env.now), "picture": False})
    assert env.calls[1].data["data"]["image"] == "/api/frigate/notifications/e2/thumbnail.jpg"


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


async def test_person_at_an_open_or_unlocked_door(hass, env):
    hass.states.async_set("lock.front", "locked", {"friendly_name": "Front lock"})
    await env.start(camera_door=True, camera_setup={"front_door": {"doors": ["lock.front"]}})
    await env.see("front_door", event(1))
    assert env.calls == []
    hass.states.async_set("lock.front", "unlocked", {"friendly_name": "Front lock"})
    await env.see("front_door", event(2))
    await env.see("yard", event(3))  # not linked to that lock
    assert env.texts() == ["Someone at front door, and Front lock is unlocked."]
    hass.states.async_set("lock.front", "unavailable")
    env.now += datetime.timedelta(hours=1)
    await env.see("front_door", event(4, at=env.now))  # unknown is never open (B2)
    assert len(env.calls) == 1


async def test_a_car_must_stay_in_its_zone(hass, env):
    await env.start(camera_car=True, camera_setup={"driveway": {"zones": ["driveway"]}})
    passing = {**event(1, "car", zones=["street"]), "end": (START.timestamp() + 60)}
    await env.see("driveway", passing)  # outside the zones that count
    quick = {**event(2, "car", zones=["driveway"]), "end": START.timestamp() + 5}
    await env.see("driveway", quick)  # gone in 5 seconds: drove past
    assert env.calls == []
    stays = event(3, "car", zones=["driveway"])
    await env.see("driveway", stays)  # just arrived: not yet, but looked at again later
    assert env.calls == [] and len(env.watch._waiting) == 1
    env.watch.stop()
    env.now += datetime.timedelta(seconds=40)
    await env.see("driveway", stays)  # the second look: it stayed
    assert env.texts() == ["A car at driveway. In driveway."]


async def test_each_camera_its_own_messages(env):
    await env.start(camera_package=True, camera_stranger=True,
                    camera_setup={"porch": {"rules": ["camera_package"]}})
    await env.see("porch", event(1))  # strangers are not for this camera
    await env.see("porch", event(2, "package"))
    await env.see("yard", event(3))  # every message for a camera not set up
    assert env.texts() == ["A package at porch.", "A person Frigate does not know at yard."]


async def test_the_models_words_when_ready(env):
    await env.start(camera_package=True)
    await env.see("porch", {**event(1, "package"), "description": "A brown box by the mat."})
    assert env.texts() == ["A package at porch. A brown box by the mat."]


async def test_not_news_is_never_told(env):
    await env.start(camera_stranger=True)
    env.watch.quiet = [("yard", "person", ())]
    await env.see("yard", event(1))  # a person outside every zone: the neighbors
    await env.see("yard", event(2, zones=["path"]))  # on the owner's path: still news
    assert env.texts() == ["A person Frigate does not know at yard. In path."]


async def test_not_news_from_a_phone(env):
    told = []
    await env.start(camera_package=True, camera_repeat=1)
    env.watch._not_news = lambda camera, event_id: told.append((camera, event_id)) or True
    await env.see("porch", event(1, "package", zones=["steps"]))
    buttons = env.calls[0].data["data"]["actions"]
    assert buttons[-1] == {"action": "BRAM_CAMNEWS_e1", "title": "Not news"}
    env.watch.answered(Event("mobile_app_notification_action", {"action": "BRAM_CAMNEWS_e1"}))
    env.watch.answered(Event("mobile_app_notification_action", {"action": "BRAM_CAMNEWS_e9"}))
    assert told == [("porch", "e1")]  # an event it never sent is ignored
    env.now += datetime.timedelta(hours=1)
    await env.see("porch", event(2, "package", zones=["steps"], at=env.now))
    assert len(env.calls) == 1  # the same is now not news
