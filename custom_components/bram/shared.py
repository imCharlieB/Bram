"""What the owner shared, less what they turned off in Home Assistant itself."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENTITIES


def disabled(hass: HomeAssistant, options: Mapping[str, Any]) -> list[str]:
    registry = er.async_get(hass)
    return [e for e in options.get(CONF_ENTITIES, [])
            if (entry := registry.async_get(e)) is not None and entry.disabled_by is not None]


def shared(hass: HomeAssistant, options: Mapping[str, Any]) -> list[str]:
    off = set(disabled(hass, options))
    return [e for e in options.get(CONF_ENTITIES, []) if e not in off]


def missing(hass: HomeAssistant, options: Mapping[str, Any]) -> list[str]:
    """Neither in the registry nor reporting: deleted, as far as anyone can tell."""
    registry = er.async_get(hass)
    return [e for e in options.get(CONF_ENTITIES, [])
            if registry.async_get(e) is None and hass.states.get(e) is None]
