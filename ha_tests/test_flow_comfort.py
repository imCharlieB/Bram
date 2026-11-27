from unittest.mock import patch

import pytest
from flows import go
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.bram  # noqa: F401

pytestmark = pytest.mark.usefixtures("custom")


async def test_comfort_limits_in_the_homes_unit(hass):
    entry = MockConfigEntry(domain="bram", data={"host": "x", "port": 1}, options={
        "entities": [], "comfort_skip": ["sensor.old"]})
    entry.add_to_hass(hass)
    with patch("custom_components.bram.async_setup_entry", return_value=True):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        form = await go(hass, flow["flow_id"], "comfort")
        defaults = {str(k): k.default() for k in form["data_schema"].schema
                    if callable(getattr(k, "default", None))}
        assert defaults["hot_above"] == 29 and defaults["too_hot"] is False  # Celsius here
        await hass.config_entries.options.async_configure(form["flow_id"], {
            "too_hot": True, "too_cold": False, "freezing": True, "humid": False,
            "hot_above": 30, "cold_below": 15, "freeze_below": 3, "humid_above": 75})
    assert entry.options["too_hot"] and entry.options["hot_above"] == 30
    assert "comfort_skip" not in entry.options  # emptied means none left out
    for item in hass.config_entries.async_entries():
        item.mock_state(hass, ConfigEntryState.NOT_LOADED)
