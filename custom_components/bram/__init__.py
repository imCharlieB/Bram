"""BRAM: watches and alerts. Cannot control anything."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from . import blueprints, review
from .const import CONF_ENTITIES, DOMAIN
from .digest import Digest
from .feed import Feed
from .home_alerts import HomeAlerts
from .house_rules import HouseRules
from .learning import Learner
from .notifier import set_page
from .outbox import Outbox
from .printer_watch import PrinterWatch
from .problem_watch import ProblemWatch
from .security_watch import SecurityWatch
from .shared import disabled, missing
from .suggestions import Suggestions
from .teller import Teller

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CONVERSATION,
             Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.runtime_data = feed = Feed(hass, entry)
    feed.version = str((await async_get_integration(hass, DOMAIN)).version)
    wanted = {f"{entry.entry_id}_{e}" for e in entry.options.get(CONF_ENTITIES, [])}
    wanted |= {f"{entry.entry_id}_connected", f"{entry.entry_id}_test",
               f"{entry.entry_id}_allow", f"{entry.entry_id}_assist",
               f"{entry.entry_id}_mood"}
    registry = er.async_get(hass)
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.unique_id not in wanted:
            registry.async_remove(item.entity_id)
    set_page(hass, entry.data["host"], entry.data["port"])
    await blueprints.install(hass)
    await review.start(hass)
    feed.outbox = Outbox(hass, entry, feed.send, feed.takes_notes)
    entry.async_on_unload(await feed.outbox.start())
    feed.teller = Teller(hass, entry, feed.note, feed.offer)
    entry.async_on_unload(await feed.teller.start())
    feed.alerts = HomeAlerts(hass, entry, feed)
    entry.async_on_unload(await feed.alerts.start())
    entry.async_on_unload(Digest(hass, entry, feed).start())
    feed.rules = HouseRules(hass, entry, feed.note, feed.teller, feed.send_watching)
    entry.async_on_unload(await feed.rules.start())
    feed.problems = ProblemWatch(hass, entry, feed.rules.is_night, feed.note,
                                 feed.teller)
    entry.async_on_unload(await feed.problems.start())
    feed.printers = PrinterWatch(hass, entry, feed.send_printers, feed.note,
                                 feed.teller)
    entry.async_on_unload(await feed.printers.start())
    feed.learner = Learner(hass, entry, feed)
    feed.suggestions = Suggestions(hass, entry, feed.outbox.known, feed.act, feed.note)
    await feed.suggestions.start()
    entry.async_on_unload(await feed.learner.start())
    entry.async_on_unload(await SecurityWatch(hass, entry, feed.note).start())
    for entity_id in missing(hass, entry.options):
        feed.note(f"missing:{entity_id}", "open", f"{entity_id} no longer exists in Home "
                  "Assistant. Remove it under What BRAM can see", "problems", "low")
    for entity_id in disabled(hass, entry.options):
        feed.note(f"disabled:{entity_id}", "open", f"{entity_id} is turned off in Home "
                  "Assistant, so BRAM does not watch it", "problems", "low")

    @callback
    def changed(event: Event) -> None:
        # Turned off or on again in Home Assistant: BRAM follows at once.
        data = event.data
        old, new = data.get("old_entity_id"), data.get("entity_id")
        chosen = entry.options.get(CONF_ENTITIES, [])
        if data.get("action") == "remove" and new in chosen:
            # Deleted in Home Assistant, so there is nothing left to watch.
            feed.note(f"removed:{new}", "open", f"{new} was deleted in Home Assistant, so BRAM "
                      "stopped watching it", "problems", "low")
            hass.config_entries.async_update_entry(entry, options={
                **entry.options, CONF_ENTITIES: [e for e in chosen if e != new]})
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return
        if data.get("action") == "update" and old in chosen and new not in chosen:
            # Renamed in Home Assistant: the new name is the same device.
            hass.config_entries.async_update_entry(entry, options={
                **entry.options, CONF_ENTITIES: [new if e == old else e for e in chosen]})
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return
        if (data.get("action") == "update" and "disabled_by" in data.get("changes", {})
                and data.get("entity_id") in entry.options.get(CONF_ENTITIES, [])):
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, changed))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, feed.run(), "bram feed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ir.async_delete_issue(hass, DOMAIN, "version")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete everything BRAM kept here."""
    for part in ("", ".rules", ".security", ".learned", ".outbox", ".problems",
                 ".printers", ".told"):
        await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}{part}").async_remove()
