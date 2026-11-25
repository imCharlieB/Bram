import logging
from types import SimpleNamespace

import pytest
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.bram.queries import MAX_ERRORS, answer, clean, problems

DOOR = "binary_sensor.back"


@pytest.mark.parametrize(("text", "gone"), [
    ("Login failed for http://admin:hunter2@10.0.0.5:8123/x?token=abc", ["hunter2", "10.0.0.5"]),
    ("password=hunter2 bad", ["hunter2"]), ("Bad api_key: 'sk-abc123'", ["sk-abc123"]),
    ('{"access_token": "zzz9", "x": 1}', ["zzz9"]), ("Bearer abc.def.ghi rejected", ["abc.def"]),
    ("mail bob.smith@example.org failed", ["bob.smith"]), ("user bob denied", ["bob"]),
    ("host 192.168.1.20:80 down", ["192.168.1.20"]), ("mac aa:bb:cc:dd:ee:ff lost", ["bb:cc"]),
    ("at 40.712776, -74.005974", ["40.7127", "74.0059"]),
    ("peer fe80::1ff:fe23:4567:890a", ["fe23"]),
    ("refresh_token='a b c' expired", ["a b c"]), ("X-Api-Key: k1", ["k1"]),
    ("{'client_secret': 's1', 'userName': 'bob'}", ["s1", "bob"]),
    ("Authorization: Bearer shorttok", ["shorttok"]), ("db_password : p4ss", ["p4ss"]),
    ("wss://host/?code=99", ["99"]), ("PIN=1234", ["1234"]), ("token = abc9", ["abc9"]),
    ("password : p", [": p"]),
    ("token: 'x1', secret: \"y2\"", ["x1", "y2"]), ("Basic dXNlcjpw", ["dXNlcjpw"]),
    ("nas.local refused", ["nas.local"]), ("read /config/secrets/bob.yaml", ["bob.yaml"]),
    ("id 1234567890abcdef1234 gone", ["1234567890abcdef"]), ("call +1 555 123 4567 now", ["555"]),
    ("first\nsecond secret line", ["second"])])
def test_private_things_are_removed(text, gone):
    for item in gone:
        assert item not in clean(text), clean(text)


def test_useful_words_stay():
    assert clean("Timeout waiting for sensor after 10 seconds") == (
        "Timeout waiting for sensor after 10 seconds")
    assert len(clean("x " * 500)) <= 160 and clean("") == ""


def record(name, level, text, count):
    return {"name": name, "level": level, "message": ["old", text], "count": count,
            "first_occurred": 1_700_000_000.0, "timestamp": 1_700_003_600.0, "exception": "SECRET",
            "source": ("SECRET.py", 1)}


async def test_problems_are_grouped_cleaned_and_limited(hass):
    items = [record("homeassistant.components.zha", "ERROR", "Lost token=abc123", 5),
             record("custom_components.x", "WARNING", "slow", 900),
             record("y", "DEBUG", "noise", 1),
             *[record(f"z{i}", "ERROR", "bad", 1) for i in range(30)]]
    hass.data["system_log"] = SimpleNamespace(records=SimpleNamespace(to_list=lambda: items))
    ir.async_create_issue(hass, "demo", "a", is_fixable=False, translation_key="broken",
                          severity=ir.IssueSeverity.WARNING)
    hass.states.async_set("sensor.b", "9", {"device_class": "battery", "friendly_name": "Remote"})
    hass.states.async_set("sensor.ok", "90", {"device_class": "battery"})
    hass.states.async_set("sensor.u", "unavailable", {"device_class": "battery"})
    hass.states.async_set("update.core", "on", {"friendly_name": "Core"})
    result = problems(hass)
    assert len(result["errors"]) == MAX_ERRORS and result["more_errors"] == 20
    assert result["errors"][0]["from"] == "zha" and result["errors"][0]["times"] == 5
    assert "demo: broken" in result["repairs"] and result["updates"] == ["Core"]
    assert result["low_batteries"] == ["Remote 9%"] and result["unavailable"] == 1
    assert "abc123" not in str(result) and "SECRET" not in str(result)
    del hass.data["system_log"]


@pytest.mark.parametrize(("options", "what", "entity", "error"), [
    ({}, "problems", None, "off"), ({}, "history", DOOR, "off"),
    ({"share_history": True, "entities": []}, "history", DOOR, "refused"),
    ({"share_history": True, "share_problems": True}, "states", None, "refused"),
    ({"share_problems": True}, "history", DOOR, "off"), ({}, None, None, "refused"),
    ({"share_history": True, "entities": [DOOR]}, "history", ["x"], "refused")])
async def test_everything_else_is_refused(hass, options, what, entity, error):
    entry = MockConfigEntry(domain="bram", options=options)
    assert await answer(hass, entry, {}, what, entity) == {"error": error}


async def test_history(recorder_mock, hass, enable_custom_integrations):
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    entry = MockConfigEntry(domain="bram", options={"share_history": True, "entities": [DOOR]})
    for value in ("off", "on", "off", "unavailable", "on"):
        hass.states.async_set(DOOR, value)
        await hass.async_block_till_done()
    hass.states.async_set("lock.other", "unlocked")
    await async_wait_recording_done(hass)
    result = await answer(hass, entry, {DOOR: "opening"}, "history", DOOR)
    assert [c[1] for c in result["changes"]] == ["open", "unknown", "closed", "open", "closed"]
    assert result["counts"] == {"open": 2, "closed": 2, "unknown": 1}
    assert "unlocked" not in str(result)
