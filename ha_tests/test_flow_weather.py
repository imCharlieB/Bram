from unittest.mock import patch

import pytest
from flows import go
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.bram  # noqa: F401

pytestmark = pytest.mark.usefixtures("custom")


async def test_weather_is_offered_with_climate_and_back_goes_to_the_start(hass):
    hass.states.async_set("weather.home", "sunny", {"temperature": 70})
    entry = MockConfigEntry(domain="bram", data={"host": "x", "port": 1}, options={
        "entities": []})
    entry.add_to_hass(hass)
    with patch("custom_components.bram.async_setup_entry", return_value=True):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        form = await go(hass, flow["flow_id"], "see")
        schema = {str(k): v for k, v in form["data_schema"].schema.items()}
        assert "weather.home" in schema["climate"].config["include_entities"]
        assert "weather.home" not in schema["other"].config["include_entities"]
        await hass.config_entries.options.async_configure(form["flow_id"], {
            "climate": ["weather.home"]})
        assert entry.options["entities"] == ["weather.home"]
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        menu = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "watching"})
        back = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "init"})
        assert menu["step_id"] == "watching" and back["step_id"] == "init"
        hass.config_entries.options.async_abort(flow["flow_id"])
    for item in hass.config_entries.async_entries():
        item.mock_state(hass, ConfigEntryState.NOT_LOADED)
