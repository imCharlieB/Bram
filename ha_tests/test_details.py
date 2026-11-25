import base64

import pytest
from homeassistant.core import State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

from custom_components.bram import details
from custom_components.bram.details import _text, detail, image_kind, picture, picture_path


@pytest.mark.parametrize(("entity", "state", "attrs", "text"), [
    ("light.a", "on", {"brightness": 128}, "50%"), ("light.a", "off", {"brightness": 128}, ""),
    ("media_player.a", "playing", {"media_title": "Song", "media_artist": "Band",
                                   "app_name": "Radio", "volume_level": .32},
     "Song by Band, Radio, volume 32%"),
    ("media_player.a", "off", {"media_title": "Song"}, ""),
    ("climate.a", "heat", {"hvac_action": "heating"}, "heating"),
    ("cover.a", "open", {"current_position": 40}, "40%"),
    ("lock.a", "locked", {"battery_level": 80}, "battery 80%"),
    ("weather.a", "rainy", {"temperature": 68, "temperature_unit": "F"}, "68F"),
    ("person.a", "home", {"latitude": 1.5, "longitude": 2.5, "gps_accuracy": 3}, "")])
def test_text(entity, state, attrs, text):
    assert _text(State(entity, state, attrs)) == text


async def test_detail_has_room_and_never_location(hass):
    den = ar.async_get(hass).async_create("Den")
    er.async_get(hass).async_get_or_create("person", "test", "1", suggested_object_id="a")
    er.async_get(hass).async_update_entity("person.a", area_id=den.id)
    hass.states.async_set("person.a", "home", {
        "latitude": 40.5, "longitude": -70.5, "entity_picture": "/api/image/serve/x/512x512"})
    found = detail(hass, hass.states.get("person.a"))
    assert found["area"] == "Den" and len(found["picture"]) == 16 and found["since"] > 0
    assert "40.5" not in str(found) and "serve" not in str(found)
    assert detail(hass, None) == {}
    hass.states.async_set("light.x", "unavailable", {"brightness": 9})
    assert "text" not in detail(hass, hass.states.get("light.x"))


@pytest.mark.parametrize("path", [
    "https://evil.example/a.png", "/api/states", "/local/../../secrets.yaml", None, 5,
    "/api/camera_proxy/camera.a?token=1", "//evil.example/x"])
def test_only_home_assistants_own_pictures(path):
    assert picture_path(State("person.a", "home", {"entity_picture": path})) is None


def test_image_kind():
    assert image_kind(b"\xff\xd8\xffx") == "image/jpeg"
    assert image_kind(b"RIFF0000WEBPx") == "image/webp"
    for bad in (b"", b"<svg onload=1>", b"<html>", b"RIFF0000WAVE"):
        assert image_kind(bad) is None


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50


@pytest.mark.parametrize(("body", "status", "good"), [
    (PNG, 200, True), (b"<svg/>", 200, False), (PNG, 404, False),
    (PNG + b"0" * details.MAX_PICTURE, 200, False)], ids=["good", "svg", "missing", "huge"])
async def test_picture(hass, aioclient_mock, monkeypatch, body, status, good):
    class Http:
        server_port = 8123

    monkeypatch.setattr(hass, "http", Http(), raising=False)
    hass.states.async_set("person.a", "home", {"entity_picture": "/api/image/serve/x/512x512"})
    aioclient_mock.get("http://127.0.0.1:8123/api/image/serve/x/512x512", content=body,
                       status=status)
    result = await picture(hass, "person.a")
    if good:
        assert result == {"kind": "image/png", "data": base64.b64encode(PNG).decode()}
    else:
        assert result == {"error": "none"}
