"""BRAM: watches and alerts. Cannot control anything."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import CONF_ENTITIES, DOMAIN
from .feed import Feed
from .home_alerts import HomeAlerts
from .house_rules import HouseRules

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CONVERSATION, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.runtime_data = feed = Feed(hass, entry)
    feed.version = str((await async_get_integration(hass, DOMAIN)).version)
    wanted = {f"{entry.entry_id}_{e}" for e in entry.options.get(CONF_ENTITIES, [])}
    wanted |= {f"{entry.entry_id}_connected", f"{entry.entry_id}_test",
               f"{entry.entry_id}_allow", f"{entry.entry_id}_assist"}
    registry = er.async_get(hass)
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.unique_id not in wanted:
            registry.async_remove(item.entity_id)
    feed.alerts = HomeAlerts(hass, entry, feed)
    entry.async_on_unload(await feed.alerts.start())
    feed.rules = HouseRules(hass, entry)
    entry.async_on_unload(await feed.rules.start())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, feed.run(), "bram feed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ir.async_delete_issue(hass, DOMAIN, "version")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
