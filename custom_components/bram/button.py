"""Send a test message to the chosen phones."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BramEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([TestMessage(entry, "test"), AllowMessages(entry, "allow")])


class TestMessage(BramEntity, ButtonEntity):
    __test__ = False  # not a pytest class
    _attr_name = "Send test message"
    _attr_icon = "mdi:message-badge"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        if not await self._feed.alerts.test():
            raise HomeAssistantError("No phone received it. Choose phones in BRAM's options.")


class AllowMessages(BramEntity, ButtonEntity):
    _attr_name = "Allow stopped messages"
    _attr_icon = "mdi:bell-ring"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        self._feed.alerts.allow_all()
