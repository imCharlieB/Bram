"""Camera events reach Home Assistant from the real server, checked (E2)."""
import json

import pytest
from test_integration import server, start, until  # noqa: F401

from bram.cameras import event_from
from bram.server import CONFIG
from custom_components.bram import cameras

pytestmark = pytest.mark.usefixtures("custom")
JPEG = b"\xff\xd8 a picture"
RAW = {"id": "e1", "camera": "front_door", "label": "person", "sub_label": ["Alex", .9],
       "zones": ["porch"], "start_time": 1_800_000_000, "end_time": None, "has_snapshot": True}


@pytest.mark.rule("E2")
async def test_only_turned_on_cameras_reach_home_assistant(hass, server):  # noqa: F811
    app = server[0]
    page = app[CONFIG]
    page._settings.update_channel("cameras", {"url": "http://127.0.0.1:5000",
                                              "on": ["front_door"]})
    page.cameras.found = ["front_door", "yard"]
    page.cameras.zones = {"front_door": ["porch"], "yard": ["lawn"]}
    entry = await start(hass, server)
    feed = entry.runtime_data
    await until(lambda: feed.camera_names == ["front_door"])
    await until(lambda: feed.camera_zones == {"front_door": ["porch"]})  # not the yard's

    event = event_from(RAW)
    page.cameras.events["front_door"] = [event]
    await page._camera_event(event, True)
    await until(lambda: "front_door" in feed.camera_events)
    assert feed.camera_events["front_door"]["who"] == "Alex"
    # No entities: the Frigate integration already has the cameras.
    assert not [s for s in hass.states.async_entity_ids() if "front_door" in s]

    page.cameras.choose("front_door", False)
    await page.tell_cameras()
    await until(lambda: feed.camera_names == [] and feed.camera_events == {})


@pytest.mark.parametrize("raw", [
    {**json.loads(json.dumps({"id": "e", "label": "person", "who": "", "zones": [],
                              "start": 1.0, "end": None, "picture": True, "summary": "x"})),
     "extra": 1},
    {"id": "e", "label": "person", "who": "", "zones": "porch", "start": 1.0, "end": None,
     "picture": True, "summary": "x"},
    {"id": "", "label": "person", "who": "", "zones": [], "start": 1.0, "end": None,
     "picture": True, "summary": "x"},
    {"id": "e", "label": "person", "who": "x" * 65, "zones": [], "start": 1.0, "end": None,
     "picture": True, "summary": "x"},
    {"id": "e", "label": "person", "who": "", "zones": [], "start": True, "end": None,
     "picture": True, "summary": "x"},
    "nope"])
def test_server_text_is_checked(raw):
    assert cameras.event(raw) is None


def test_camera_names_are_checked():
    assert cameras.names(["front_door", "back-yard"]) == ["front_door", "back-yard"]
    assert cameras.names(["../x"]) is None
    assert cameras.names("front_door") is None



def test_words_from_the_model_are_checked():
    base = {"id": "e", "label": "person", "who": "", "zones": [], "start": 1.0, "end": None,
            "picture": True, "summary": "x"}
    assert cameras.event({**base, "description": "A man at the door."})["description"] == (
        "A man at the door.")
    assert cameras.event(base)["description"] is None
    assert cameras.event({**base, "description": "x" * 301}) is None
    assert cameras.event({**base, "description": ""}) is None


def test_not_news_patterns_are_checked():
    good = [{"camera": "yard", "label": "person", "zones": ["path", "gate"]}]
    assert cameras.patterns(good) == [("yard", "person", ("gate", "path"))]
    assert cameras.patterns([{**good[0], "extra": 1}]) is None
    assert cameras.patterns([{**good[0], "camera": "../x"}]) is None
    assert cameras.patterns("yard") is None
