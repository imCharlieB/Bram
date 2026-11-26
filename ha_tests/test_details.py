import base64

import pytest
from homeassistant.core import State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bram import details
from custom_components.bram.details import (
    _text,
    detail,
    image_kind,
    picture,
    picture_path,
    room_sensors,
)


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
    ("person.a", "Work", {}, "at Work"), ("person.a", "not_home", {}, ""),
    ("person.a", "home", {"latitude": 1.5, "longitude": 2.5, "gps_accuracy": 3}, "")])
def test_text(entity, state, attrs, text):
    assert _text(State(entity, state, attrs)) == text


async def test_floor(hass):
    up = fr.async_get(hass).async_create("Upstairs")
    den = ar.async_get(hass).async_create("Den", floor_id=up.floor_id)
    er.async_get(hass).async_get_or_create("light", "test", "1", suggested_object_id="a")
    er.async_get(hass).async_update_entity("light.a", area_id=den.id)
    hass.states.async_set("light.a", "on")
    found = detail(hass, hass.states.get("light.a"))
    assert (found["area"], found["floor"]) == ("Den", "Upstairs")


async def test_person_room_comes_from_their_tracker(hass):
    MockConfigEntry(domain="bermuda", entry_id="b").add_to_hass(hass)
    phone, other = (dr.async_get(hass).async_get_or_create(
        config_entry_id="b", identifiers={("bermuda", n)}) for n in ("phone", "other"))
    registry = er.async_get(hass)
    for domain, name, device in (("device_tracker", "phone", phone),
                                 ("sensor", "phone_area", phone),
                                 ("sensor", "phone_distance", phone),
                                 ("sensor", "other_area", other)):
        registry.async_get_or_create(domain, "bermuda", name, suggested_object_id=name,
                                     device_id=device.id)
    hass.states.async_set("sensor.other_area", "Attic")
    person = {"device_trackers": ["device_tracker.phone"]}
    for state, room, expected in (("home", "Kitchen", "Kitchen"), ("home", "unknown", None),
                                  ("not_home", "Kitchen", None), ("Work", "Kitchen", None)):
        hass.states.async_set("person.a", state, person)
        hass.states.async_set("sensor.phone_area", room)
        assert detail(hass, hass.states.get("person.a")).get("area") == expected
    assert room_sensors(hass, hass.states.get("person.a")) == ["sensor.phone_area"]
    for bad in (None, State("person.a", "home", {"device_trackers": "x"}),
                State("person.a", "home", {"device_trackers": ["device_tracker.gone"]})):
        assert room_sensors(hass, bad) == []


def put(hass, entity, value, name, **attrs):
    hass.states.async_set(entity, value, {"friendly_name": name, **attrs})


async def test_room_sensor_is_matched_by_name(hass):
    ar.async_get(hass).async_create("Master Bedroom")
    put(hass, "person.a", "home", "Alex Smith")
    put(hass, "person.s", "home", "Sam")
    put(hass, "sensor.alex_room", "Master Bedroom", "Alex Room")
    put(hass, "sensor.alexs_phone_area", "unknown", "Alex's Phone Area",
        device_class="bermuda__custom_device_class")
    put(hass, "sensor.alex_distance", "4.2", "Alex Distance")
    put(hass, "sensor.alexander_room", "Master Bedroom", "Alexander Room")
    put(hass, "sensor.guest", "Master Bedroom", "Guest Room")
    person = hass.states.get("person.a")
    assert room_sensors(hass, person) == ["sensor.alex_room", "sensor.alexs_phone_area"]
    assert detail(hass, person)["area"] == "Master Bedroom"
    assert room_sensors(hass, hass.states.get("person.s")) == []
    # The owner's own choice wins.
    assert room_sensors(hass, person, {"person.a": "sensor.x"}) == ["sensor.x"]
    # Two people with one name are never mixed up.
    put(hass, "person.b", "home", "Alex Jones")
    assert room_sensors(hass, person) == []


async def test_chosen_room_sensor(hass):
    rooms = {"person.a": "sensor.my_room"}
    hass.states.async_set("sensor.my_room", "Master Bedroom")
    for state, room, expected in (("home", "Master Bedroom", "Master Bedroom"),
                                  ("home", "unavailable", None), ("home", "not_home", None),
                                  ("not_home", "Master Bedroom", None)):
        hass.states.async_set("person.a", state)
        hass.states.async_set("sensor.my_room", room)
        assert detail(hass, hass.states.get("person.a"), rooms).get("area") == expected


async def test_detail_never_has_coordinates(hass):
    den = ar.async_get(hass).async_create("Den")
    er.async_get(hass).async_get_or_create("person", "test", "1", suggested_object_id="a")
    er.async_get(hass).async_update_entity("person.a", area_id=den.id)
    hass.states.async_set("person.a", "home", {
        "latitude": 40.5, "longitude": -70.5, "entity_picture": "/api/image/serve/x/512x512"})
    found = detail(hass, hass.states.get("person.a"))
    assert "area" not in found and len(found["picture"]) == 16 and found["since"] > 0
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



async def test_a_devices_other_readings(hass):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.bram.details import parts

    entry = MockConfigEntry(domain="econet")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("econet", "1")}, name="Heat Pump")
    registry = er.async_get(hass)

    def add(domain, key, state, **attrs):
        made = registry.async_get_or_create(domain, "econet", key, device_id=device.id,
                                            suggested_object_id=key)
        hass.states.async_set(made.entity_id, state, attrs)
        return made.entity_id

    heater = add("water_heater", "heater", "electric", temperature=120)
    add("sensor", "hot", "66", friendly_name="Heat Pump_available_hot_water",
        unit_of_measurement="%")
    add("binary_sensor", "running", "on", friendly_name="Heat Pump_running")
    add("sensor", "junk", "{'constraints': {'bgcolor': 1}}", friendly_name="Heat Pump_override")
    add("sensor", "water", "unknown", friendly_name="Heat Pump_water_usage")
    assert parts(hass, hass.states.get(heater)) == [
        ["Available hot water", "66%"], ["Running", "yes"]]


async def test_devices_reporting_trouble(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.bram.problems import Finder

    finder = Finder(hass, MockConfigEntry(domain="bram", options={}))
    hass.states.async_set("sensor.heater_alert_count", "0", {"friendly_name": "Heater_alert_count"})
    hass.states.async_set("sensor.heater_tank_health", "90", {"unit_of_measurement": "%"})
    assert finder._trouble() == []
    hass.states.async_set("sensor.heater_alert_count", "2", {"friendly_name": "Heater_alert_count"})
    hass.states.async_set("sensor.heater_tank_health", "40", {"unit_of_measurement": "%",
                                                              "friendly_name": "Tank health"})
    assert [p.text for p in finder._trouble()] == [
        "Heater alert count is 2", "Tank health is down to 40%"]
