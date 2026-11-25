"""What the BRAM Server believes about each chosen entity."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.start import async_at_started

from .const import ICON, MEANING
from .entity import BramEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    @callback
    def add(_: HomeAssistant) -> None:
        async_add_entities(Belief(hass, entry, e) for e in entry.runtime_data.entities)

    # During startup the watched devices have no names yet.
    entry.async_on_unload(async_at_started(hass, add))


class Belief(BramEntity, SensorEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, source: str) -> None:
        super().__init__(entry, source)
        self._source = source
        state = hass.states.get(source)
        known = er.async_get(hass).async_get(source)
        name = state.name if state else known and (known.name or known.original_name)
        self._attr_name = name or source
        self._attr_extra_state_attributes = {"source": source}

    @property
    def available(self) -> bool:
        return self._feed.connected and self._source in self._feed.beliefs

    @property
    def icon(self) -> str:
        return ICON.get(self._feed.kind(self._source) or "", "mdi:eye-outline")

    @property
    def native_value(self) -> str | None:
        meaning = MEANING.get(self._feed.kind(self._source) or "")
        answer = self._feed.beliefs.get(self._source)
        if meaning is None or answer not in ("yes", "no"):
            return None  # shown as unknown
        return meaning[0] if answer == "yes" else meaning[1]
