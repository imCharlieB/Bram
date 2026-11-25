"""BRAM's mood. It changes wording only."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MOODS
from .entity import BramEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([Mood(entry, "mood")])


class Mood(BramEntity, SelectEntity):
    _attr_name = "Mood"
    _attr_icon = "mdi:drama-masks"
    _attr_options = list(MOODS.values())

    @property
    def available(self) -> bool:
        return self._feed.connected and self._feed.mood is not None

    @property
    def current_option(self) -> str | None:
        return MOODS.get(self._feed.mood or "")

    async def async_select_option(self, option: str) -> None:
        mode = next(m for m, name in MOODS.items() if name == option)
        if not self._feed.send({"type": "mood", "mode": mode}):
            raise HomeAssistantError("The BRAM Server is not connected.")
