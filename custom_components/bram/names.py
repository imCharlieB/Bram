"""Names people would use.

A name a device gave itself, with a serial number in it, is not one.
"""
from __future__ import annotations

import re

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

# A run of letters and digits mixed, or of hex, long enough to be a serial number or address.
_SERIAL = re.compile(
    r"(?<![a-z0-9])(?=(?:[a-z]*\d){3})(?=[a-z0-9]*[a-z])[a-z0-9]{8,}|"
    r"(?<![a-z0-9])(?=[0-9a-f]*\d)[0-9a-f]{6,}(?![a-z0-9])|[0-9a-f]{2}(?::[0-9a-f]{2}){2,}", re.I)
WORDS = {"motion": "motion", "occupancy": "presence", "presence": "presence", "door": "door",
         "window": "window", "opening": "opening", "garage_door": "garage door",
         "moisture": "leak sensor", "smoke": "smoke alarm", "temperature": "temperature",
         "humidity": "humidity", "battery": "battery", "illuminance": "light level",
         "power": "power", "energy": "energy"}


def machine_made(name: str) -> bool:
    return bool(_SERIAL.search(name))


def _plain(text: str) -> str:
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())


def device_name(hass: HomeAssistant, device: dr.DeviceEntry) -> str:
    """The owner's name, or the device's own if it reads well, or its model and room."""
    if device.name_by_user:
        return _plain(device.name_by_user)[:60]
    name = _plain(device.name or "")
    if name and not machine_made(name):
        return name[:60]
    area = ar.async_get(hass).async_get_area(device.area_id) if device.area_id else None
    model = _plain(device.model or "")
    model = "" if machine_made(model) else model
    # The part before the serial, as in H2D_0947AJ612800457.
    head = _SERIAL.split(name)[0].strip(" _-") if name else ""
    base = model or head or "Device"
    return f"{area.name} {base}"[:60] if area and len(base) < 4 else base[:60]


def entity_name(hass: HomeAssistant, state: State) -> str:
    """As Home Assistant shows it, unless that is a machine-made name."""
    name = _plain(state.name)
    if not machine_made(name):
        return name[:100]
    entry = er.async_get(hass).async_get(state.entity_id)
    if entry is not None and entry.name:
        if not machine_made(entry.name):
            return _plain(entry.name)[:100]  # the owner named it
    device = (dr.async_get(hass).async_get(entry.device_id)
              if entry is not None and entry.device_id else None)
    area_id = (entry.area_id if entry else None) or (device.area_id if device else None)
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    word = WORDS.get(str(state.attributes.get("device_class") or ""), "")
    if area is not None and word:
        return f"{area.name} {word}"[:100]
    if device is not None:
        own = device_name(hass, device)
        return f"{own} {word}".strip()[:100] if own != "Device" else name[:100]
    return name[:100]
