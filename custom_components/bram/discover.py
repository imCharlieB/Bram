"""Find devices BRAM understands, for the owner to choose from. Shares nothing by itself."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, GROUPS
from .feed import kind_of

# One per device is enough: presence sensors often add a zone or distance entity each.
_BEST = ("occupancy", "presence", "motion", "moving")


def picked_as(entity_id: str, kind: str | None) -> str | None:
    """The kind a device is offered under. Weather sits with climate, for the outside reading."""
    return "temperature" if entity_id.startswith("weather.") else kind


def find(hass: HomeAssistant, groups: list[str], areas: list[str]) -> list[str]:
    """Everything in these groups, in these areas or anywhere if none are given."""
    entities, devices = er.async_get(hass), dr.async_get(hass)
    wanted = {kind for group in groups for kind in GROUPS[group]}
    found: list[str] = []
    motion: dict[str, tuple[int, str]] = {}
    for state in sorted(hass.states.async_all(), key=lambda s: s.entity_id):
        device_class = state.attributes.get("device_class")
        kind = picked_as(state.entity_id, kind_of(state.entity_id, device_class))
        if kind not in wanted or kind == "other":  # far too many to offer
            continue
        entry = entities.async_get(state.entity_id)
        device = devices.async_get(entry.device_id) if entry and entry.device_id else None
        # Settings and health readings of a device are not about the home.
        if entry and (entry.platform == DOMAIN or entry.hidden_by or entry.entity_category):
            continue
        area = (entry.area_id if entry else None) or (device.area_id if device else None)
        # People belong to the home, not to a room.
        if areas and kind != "person" and area not in areas:
            continue
        if kind == "motion" and device is not None:
            rank = _BEST.index(device_class) if device_class in _BEST else len(_BEST)
            if device.id not in motion or rank < motion[device.id][0]:
                motion[device.id] = (rank, state.entity_id)
            continue
        found.append(state.entity_id)
    return found + [entity for _, entity in motion.values()]


def suggest(hass: HomeAssistant, chosen: list[str]) -> list[str]:
    """What BRAM most needs and cannot see yet, most important first."""
    for_safety = find(hass, ["people", "doors", "safety"], [])
    # One motion sensor for each area that has none yet.
    entities, devices = er.async_get(hass), dr.async_get(hass)

    def area(entity_id: str) -> str | None:
        entry = entities.async_get(entity_id)
        device = devices.async_get(entry.device_id) if entry and entry.device_id else None
        return (entry.area_id if entry else None) or (device.area_id if device else None)

    motion = find(hass, ["motion"], [])
    covered = {area(e) for e in chosen if e in motion}
    extra = []
    for entity_id in motion:
        place = area(entity_id)
        if place is not None and place not in covered:
            covered.add(place)
            extra.append(entity_id)
    return [e for e in (*for_safety, *extra) if e not in chosen]
