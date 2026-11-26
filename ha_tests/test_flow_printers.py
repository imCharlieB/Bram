from unittest.mock import patch

import pytest
from flows import go
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.bram  # noqa: F401

pytestmark = pytest.mark.usefixtures("custom")


async def test_each_printer_has_its_own_switch(hass):
    with patch("custom_components.bram.async_setup_entry", return_value=True):
        await choose(hass)
    for entry in hass.config_entries.async_entries():
        entry.mock_state(hass, ConfigEntryState.NOT_LOADED)


async def choose(hass):
    entry = MockConfigEntry(domain="bram", data={"host": "x", "port": 1}, options={
        "entities": [], "printers_chosen": ["gone"], "printers_off": ["old"]})
    entry.add_to_hass(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    done = await go(hass, flow["flow_id"], "printers")
    assert done["reason"] == "no_printers"
    source = MockConfigEntry(domain="moonraker", state=ConfigEntryState.LOADED)
    source.add_to_hass(hass)
    for name in ("Big", "Small"):
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=source.entry_id, identifiers={("moonraker", name)}, name=name)
        er.async_get(hass).async_get_or_create("sensor", "moonraker", f"{name}_print_state",
                                               device_id=device.id, config_entry=source)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    form = await go(hass, flow["flow_id"], "printers")
    assert [str(k) for k in form["data_schema"].schema] == ["printers", "Big", "Small"]
    await hass.config_entries.options.async_configure(
        form["flow_id"], {"printers": True, "Big": True, "Small": False})
    small = next(e.device_id for e in er.async_get(hass).entities.values()
                 if e.unique_id == "Small_print_state")
    big = next(e.device_id for e in er.async_get(hass).entities.values()
               if e.unique_id == "Big_print_state")
    assert small != big
    assert entry.options["printers"] and entry.options["printers_chosen"] == ["gone", big]
    assert "printers_off" not in entry.options
