"""Suggestions from what the owner does: checked against what Home Assistant sent, and only
an answer changes anything (F4). Never a safety alert (C3)."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.suggestions import Suggestions

pytestmark = pytest.mark.usefixtures("custom")

STOP = {"action": "BRAM_QUIET_left_open:binary_sensor.back", "title": "Stop these"}
LESS = {"action": "BRAM_LESS_0123456789abcdef", "title": "Less often"}
KNOWN = {"rules:left_open:binary_sensor.back": {
    "buttons": [STOP, LESS], "text": "Back door has been open for 10 minutes.",
    "source": "rules"},
    "silent:binary_sensor.leak": {"buttons": [{"action": "BRAM_MUTE_x", "title": "Stop these"}],
                                  "text": "Leak stopped reporting", "source": "silent"}}
KEY = "rules:left_open:binary_sensor.back"


@pytest.fixture
async def env(hass):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    acted, notes = [], []
    entry = MockConfigEntry(domain="bram", options={"phones": ["mobile_app_phone"]})
    s = Suggestions(hass, entry, KNOWN.get, acted.append, lambda *a: notes.append(a))
    await s.start()
    return s, acted, notes, calls


async def test_a_suggestion_waits_and_one_message_opens_the_review_page(hass, env):
    s, acted, _, calls = env
    assert s.received(KEY, "You hid it 3 times in two weeks.")
    assert not s.received(KEY, "again")  # already waiting
    await hass.async_block_till_done()
    assert len(calls) == 1 and calls[0].data["data"]["url"] == "/bram-review"
    (item,) = s.review()
    assert [c["label"] for c in item["choices"]] == [
        "Stop these", "Less often", "Not now", "Never suggest this"]
    assert acted == []  # nothing until answered


@pytest.mark.rule("C3")
@pytest.mark.parametrize("key", ["silent:binary_sensor.leak", "safety:leak", "rules:unknown",
                                 None])
async def test_only_routine_messages_it_really_sent(env, key):
    s, acted, _, _ = env
    assert not s.received(key, "why")
    assert s.review() == [] and acted == []


@pytest.mark.rule("F4")
async def test_answers(env):
    s, acted, notes, _ = env
    s.received(KEY, "why")
    (item,) = s.review()
    assert not s.answer(item["id"], "approve", "Owner")  # not a choice here
    assert not s.answer("habit:nope", "stop", "Owner")
    assert s.answer(item["id"], "stop", "Owner")
    assert acted == [STOP["action"]] and s.review() == []
    assert notes[-1][2] == "Suggestion answered: Stop these, by Owner"


async def test_never_means_never(env):
    s, acted, _, _ = env
    s.received(KEY, "why")
    (item,) = s.review()
    assert s.answer(item["id"], "never", "")
    assert not s.received(KEY, "why") and acted == []
