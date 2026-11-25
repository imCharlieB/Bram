import pytest
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bram.names import device_name, entity_name, machine_made

pytestmark = pytest.mark.usefixtures("custom")


@pytest.mark.parametrize(("name", "made"), [
    ("H2D_0947AJ612800457", True), ("HLK-LD2410_CAA1B2", True), ("Acesensor1 LD2410 3f9a2c", True),
    ("aa:bb:cc:dd", True), ("Neptune4", False), ("Kitchen Motion", False), ("LD2410", False),
    ("Living room AC", False), ("Galaxy Watch Ultra2", False), ("OctoPrint", False)])
def test_machine_made(name, made):
    assert machine_made(name) is made


async def test_names(hass):
    entry = MockConfigEntry(domain="demo")
    entry.add_to_hass(hass)
    room = ar.async_get(hass).async_create("Master Bedroom")
    devices, entities = dr.async_get(hass), er.async_get(hass)

    def device(name, model=None, mine=None, area=None):
        made = devices.async_get_or_create(config_entry_id=entry.entry_id, name=name,
                                           identifiers={("demo", name)}, model=model)
        return devices.async_update_device(made.id, name_by_user=mine, area_id=area)

    assert device_name(hass, device("H2D_0947AJ612800457", "H2D")) == "H2D"
    assert device_name(hass, device("H2D_0947AJ612800458", None)) == "H2D"
    assert device_name(hass, device("X_0947AJ612800459", None, None, room.id)) == (
        "Master Bedroom X")
    assert device_name(hass, device("H2D_0947AJ612800450", "H2D", "Big printer")) == "Big printer"
    assert device_name(hass, device("Neptune4")) == "Neptune4"

    radar = device("HLK-LD2410_CAA1B2", "LD2410", None, room.id)
    made = entities.async_get_or_create("binary_sensor", "demo", "r", device_id=radar.id)
    hass.states.async_set(made.entity_id, "on", {
        "friendly_name": "HLK-LD2410_CAA1B2 Occupancy", "device_class": "occupancy"})
    assert entity_name(hass, hass.states.get(made.entity_id)) == "Master Bedroom presence"
    hass.states.async_set("light.x", "on", {"friendly_name": "Kitchen"})
    assert entity_name(hass, hass.states.get("light.x")) == "Kitchen"
    entities.async_update_entity(made.entity_id, name="Bed radar")
    hass.states.async_set(made.entity_id, "on", {
        "friendly_name": "HLK-LD2410_CAA1B2 Bed radar", "device_class": "occupancy"})
    assert entity_name(hass, hass.states.get(made.entity_id)) == "Bed radar"
