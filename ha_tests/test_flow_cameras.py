from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.bram  # noqa: F401

pytestmark = pytest.mark.usefixtures("custom")


async def step(hass, flow_id, *names):
    result = None
    for name in names:
        result = await hass.config_entries.options.async_configure(flow_id, {"next_step_id": name})
    return result


async def test_set_up_one_camera(hass):
    entry = MockConfigEntry(domain="bram", data={"host": "x", "port": 1}, options={
        "entities": [], "camera_car": True})
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(camera_names=["RoofCamera", "front_door"],
                                         camera_zones={"RoofCamera": ["driveway", "street"]})
    with patch("custom_components.bram.async_setup_entry", return_value=True):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        pick = await step(hass, flow["flow_id"], "watching", "cameras", "camera_pick")
        names = [o["value"] for o in pick["data_schema"].schema["camera"].config["options"]]
        assert names == ["RoofCamera", "front_door"]
        form = await hass.config_entries.options.async_configure(flow["flow_id"],
                                                                 {"camera": "RoofCamera"})
        assert form["description_placeholders"] == {"camera": "roof camera"}
        zones = next(v for k, v in form["data_schema"].schema.items() if str(k) == "zones")
        assert zones.config["options"] == ["driveway", "street"]  # from Frigate
        done = await hass.config_entries.options.async_configure(flow["flow_id"], {
            "doors": ["lock.front"], "zones": ["driveway"], "rules": ["camera_car"]})
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["camera_setup"] == {"RoofCamera": {
        "doors": ["lock.front"], "zones": ["driveway"], "rules": ["camera_car"]}}
    assert entry.options["camera_car"]  # the rest kept
    for item in hass.config_entries.async_entries():
        item.mock_state(hass, ConfigEntryState.NOT_LOADED)


async def test_no_cameras_yet(hass):
    entry = MockConfigEntry(domain="bram", data={"host": "x", "port": 1}, options={})
    entry.add_to_hass(hass)
    with patch("custom_components.bram.async_setup_entry", return_value=True):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        result = await step(hass, flow["flow_id"], "watching", "cameras", "camera_pick")
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "no_cameras"
    for item in hass.config_entries.async_entries():
        item.mock_state(hass, ConfigEntryState.NOT_LOADED)
