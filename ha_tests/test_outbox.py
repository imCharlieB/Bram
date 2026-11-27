import datetime
import json
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.feed import Feed
from custom_components.bram.house_rules import HouseRules
from custom_components.bram.outbox import MAX_WAITING, RESEND, SETTLED, Outbox

pytestmark = pytest.mark.usefixtures("custom")
NOTE = ("Front lock is unlocked", "rules", "low")


class Env:
    def __init__(self, hass):
        self.hass, self.sent, self.ready = hass, [], True
        self.now = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        self.entry = MockConfigEntry(domain="bram")

    async def start(self):
        self.box = Outbox(self.hass, self.entry, lambda m: self.sent.append(m) or True,
                          lambda: self.ready)
        self.stop = await self.box.start()

    def whats(self):
        return [m["what"] for m in self.sent]

    def wait(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)
        self.box.tick()


@pytest.fixture
async def env(hass):
    e = Env(hass)
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: e.now):
        await e.start()
        yield e
        e.stop()
        await hass.async_block_till_done()


async def test_kept_until_confirmed(env):
    env.ready = False
    env.box.note("k", "open", *NOTE)
    assert env.sent == []
    env.ready = True
    env.box.reconnected()
    env.wait(5)
    assert env.whats() == ["open"]
    env.wait(RESEND)
    assert env.whats() == ["open", "open"] and env.sent[0]["id"] == env.sent[1]["id"]
    env.box.confirmed(env.sent[0]["id"])
    env.wait(RESEND)
    assert len(env.sent) == 2


async def test_open_is_said_once_and_closed_only_if_open(env):
    env.box.note("k", "closed", *NOTE)
    for _ in range(3):
        env.box.note("k", "open", *NOTE)
    env.box.note("k", "closed", *NOTE)
    assert env.whats() == ["open", "closed"]


async def test_survives_a_restart_and_closes_what_nobody_sees(env, hass_storage):
    env.box.note("gone", "open", *NOTE)
    env.box.note("still", "open", *NOTE)
    await env.box._store.async_save({"waiting": env.box._waiting, "open": env.box._open})
    env.stop()
    env.sent.clear()
    await env.start()
    env.box.note("still", "open", *NOTE)
    env.box.tick()
    assert [m["key"] for m in env.sent] == ["gone", "still"]
    env.wait(SETTLED)
    closed = [m["key"] for m in env.sent if m["what"] == "closed"]
    assert closed == ["gone"]


async def test_limited(env):
    env.ready = False
    for i in range(MAX_WAITING + 50):
        env.box.note(f"k{i}", "sent", *NOTE)
    assert len(env.box._waiting) == MAX_WAITING


@pytest.mark.parametrize(("version", "takes"), [
    (None, False), ("0.23.9", False), ("0.24.0", True), ("1.0.0", True)])
async def test_older_servers_are_not_sent_notes(hass, version, takes):
    feed = Feed(hass, MockConfigEntry(domain="bram"))
    feed.connected, feed.server_version = True, version
    assert feed.takes_notes() is takes
    feed.note("k", "open", *NOTE)  # nothing to keep it in, and nothing breaks


async def test_rules_note_found_told_and_over(hass):
    async_mock_service(hass, "notify", "mobile_app_phone")
    notes = []
    now = [datetime.datetime(2026, 1, 1, 12, tzinfo=datetime.UTC)]
    rules = HouseRules(hass, MockConfigEntry(domain="bram", options={
        "entities": ["lock.a"], "phones": ["mobile_app_phone"], "offline": True}),
        lambda *a: notes.append(a[:2]))
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: now[0]):
        stop = await rules.start()
        hass.states.async_set("lock.a", "locked")
        await rules.run()
        hass.states.async_set("lock.a", "unavailable")
        await rules.run()
        assert notes == []
        now[0] += datetime.timedelta(minutes=10)
        await rules.run()
        hass.states.async_set("lock.a", "locked")
        await rules.run()
        stop()
        await hass.async_block_till_done()
    key = "rules:offline:lock.a"
    assert [n for n in notes if n[1] != "open"] == [(key, "sent"), (key, "closed")]
    assert notes[0] == (key, "open")


STOP = {"action": "BRAM_QUIET_night:lock.a", "title": "Stop these"}
LESS = {"action": "BRAM_LESS_0123456789abcdef", "title": "Less often"}


async def test_offered_buttons_go_to_the_page_but_never_acknowledge(env):
    env.box.note("rules:k", "open", *NOTE)
    env.box.offer("rules:k", [STOP, LESS, {"action": "BRAM_ACK_x", "title": "Acknowledge"},
                              {"action": "BRAM_QUIET_y", "title": "Unlock"}], "rules")
    assert env.sent[-1]["what"] == "buttons" and env.sent[-1]["buttons"] == [STOP, LESS]
    env.box.offer("silent:a", [{"action": "BRAM_ACK_a", "title": "Acknowledge"}], "silent")
    assert env.sent[-1]["key"] == "rules:k"  # nothing pressable, so nothing sent


async def test_only_an_offered_button_is_pressed_and_only_once(env):
    env.box.note("rules:k", "open", *NOTE)
    env.box.offer("rules:k", [STOP, LESS], "rules")
    assert not env.box.press("rules:k", "BRAM_ACK_x")
    assert not env.box.press("rules:other", STOP["action"])
    assert not env.box.press(["rules:k"], STOP["action"])
    assert env.box.press("rules:k", LESS["action"])
    assert env.sent[-1]["buttons"] == [STOP]
    assert not env.box.press("rules:k", LESS["action"])
    assert env.box.press("rules:k", STOP["action"])
    assert env.sent[-1]["buttons"] == []
    assert not env.box.press("rules:k", STOP["action"])


async def test_buttons_end_when_the_finding_is_over(env):
    env.box.note("rules:k", "open", *NOTE)
    env.box.offer("rules:k", [STOP], "rules")
    env.box.note("rules:k", "closed", *NOTE)
    assert not env.box.press("rules:k", STOP["action"])


async def test_a_page_press_acts_like_the_phone_button(hass):
    feed = Feed(hass, MockConfigEntry(domain="bram"))
    feed.outbox = Outbox(hass, MockConfigEntry(domain="bram"), lambda m: True, lambda: True)
    heard = []

    class Part:
        def answered(self, event):
            heard.append(event.data)

    feed.rules = feed.teller = Part()
    feed.outbox.note("rules:k", "open", *NOTE)
    feed.offer("rules:k", [STOP], "rules")
    feed.handle_message(json.dumps({"type": "press", "key": "rules:k", "action": "BRAM_ACK_k"}))
    feed.handle_message(json.dumps({"type": "press", "key": "rules:k",
                                    "action": STOP["action"], "more": 1}))
    assert heard == []
    feed.handle_message(json.dumps({"type": "press", "key": "rules:k", "action": STOP["action"]}))
    assert heard == [{"action": STOP["action"]}] * 2


async def test_buttons_are_remembered_after_it_is_over_for_suggestions(env):
    env.box.note("rules:k", "open", *NOTE)
    env.box.offer("rules:k", [STOP], "rules")
    env.box.note("rules:k", "closed", *NOTE)
    assert env.box.known("rules:k") == {"buttons": [STOP], "text": NOTE[0], "source": "rules"}
    assert env.box.known(["rules:k"]) is None


async def test_a_suggestion_from_the_server_goes_to_suggestions(hass):
    feed = Feed(hass, MockConfigEntry(domain="bram"))
    got = []

    class Part:
        def received(self, key, why):
            got.append((key, why))

    feed.suggestions = Part()
    feed.handle_message(json.dumps({"type": "suggest", "key": "rules:k", "why": "w"}))
    feed.handle_message(json.dumps({"type": "suggest", "key": "rules:k", "why": "w", "x": 1}))
    assert got == [("rules:k", "w")]
