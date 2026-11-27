"""The review page's commands: admins only, and only the suggestion that is waiting."""
from types import SimpleNamespace

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bram import review


class Learner:
    def __init__(self):
        self.answers = []

    def review(self):
        return [{"id": "learning:night", "title": "Better night hours", "text": "On 14 nights",
                 "changes": [], "expires": 0}]

    def answer(self, item, word, who):
        if item != "learning:night":
            return False
        self.answers.append((item, word, who))
        return True


@pytest.fixture
async def learner(hass):
    assert await async_setup_component(hass, "websocket_api", {})
    await review.start(hass)
    entry = MockConfigEntry(domain="bram")
    entry.add_to_hass(hass)
    found = Learner()
    entry.runtime_data = SimpleNamespace(learner=found)
    return found


@pytest.mark.rule("F4")
async def test_an_admin_sees_and_answers(hass, hass_ws_client, learner):
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "bram/review/list"})
    shown = await ws.receive_json()
    assert shown["success"] and shown["result"]["items"][0]["id"] == "learning:night"
    await ws.send_json({"id": 2, "type": "bram/review/answer", "item": "learning:open",
                        "answer": "approve"})
    assert (await ws.receive_json())["error"]["code"] == "gone"
    await ws.send_json({"id": 3, "type": "bram/review/answer", "item": "learning:night",
                        "answer": "unlock"})
    assert not (await ws.receive_json())["success"]
    await ws.send_json({"id": 4, "type": "bram/review/answer", "item": "learning:night",
                        "answer": "approve"})
    assert (await ws.receive_json())["success"]
    assert [a[:2] for a in learner.answers] == [("learning:night", "approve")]


@pytest.mark.rule("F4")
async def test_someone_who_is_not_an_admin_cannot(hass, hass_ws_client,
                                                  hass_read_only_access_token, learner):
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    for n, message in enumerate([{"type": "bram/review/list"}, {
            "type": "bram/review/answer", "item": "learning:night", "answer": "approve"}]):
        await ws.send_json({"id": n + 1, **message})
        assert (await ws.receive_json())["error"]["code"] == "unauthorized"
    assert learner.answers == []


async def test_the_camera_card_reads_only_what_bram_was_told(hass, hass_ws_client,
                                                              hass_read_only_access_token):
    assert await async_setup_component(hass, "websocket_api", {})
    await review.start(hass)
    entry = MockConfigEntry(domain="bram")
    entry.add_to_hass(hass)
    event = {"id": "e1", "label": "car", "who": "", "zones": ["driveway"], "start": 1.0,
             "end": None, "picture": False, "summary": "car at roof camera, in driveway",
             "description": "A white van parks in the driveway."}
    entry.runtime_data = SimpleNamespace(camera_names=["RoofCamera", "porch"],
                                         camera_events={"RoofCamera": event})
    ws = await hass_ws_client(hass, hass_read_only_access_token)  # anyone signed in may look
    await ws.send_json({"id": 1, "type": "bram/cameras"})
    reply = await ws.receive_json()
    assert reply["result"]["cameras"] == [
        {"name": "RoofCamera", "event": event, "image": None},  # no Frigate integration here
        {"name": "porch", "event": None, "image": None}]
    hass.config.components.add("frigate")
    await ws.send_json({"id": 2, "type": "bram/cameras"})
    reply = await ws.receive_json()
    assert reply["result"]["cameras"][0]["image"] == (
        "/api/frigate/notifications/e1/thumbnail.jpg")
