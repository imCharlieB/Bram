"""More about a shared device: its room, how long, and what it is doing."""
from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_ROOMS = ("bermuda", "mqtt_room")
_NOWHERE = ("unavailable", "unknown", "none", "not_home", "away", "")
MAX_PICTURE = 400_000
# Only pictures Home Assistant itself serves; never an outside address.
PICTURES = ("/api/image/serve/", "/api/media_player_proxy/", "/local/")
_MAGIC = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"),
          (b"GIF8", "image/gif"))


def picture_path(state: State | None) -> str | None:
    path = state.attributes.get("entity_picture") if state is not None else None
    if isinstance(path, str) and path.startswith(PICTURES) and ".." not in path:
        return path
    return None


def room_sensors(hass: HomeAssistant, person: State | None,
                 rooms: dict[str, str] | None = None) -> list[str]:
    """The sensor the owner chose, or those on the devices that track this person."""
    if person is not None and (chosen := (rooms or {}).get(person.entity_id)):
        return [chosen]
    entities = er.async_get(hass)
    trackers = person.attributes.get("device_trackers") if person is not None else None
    found: list[str] = []
    for tracker in trackers if isinstance(trackers, (list, tuple)) else []:
        entry = entities.async_get(tracker)
        if entry is None or entry.device_id is None:
            continue
        found += [e.entity_id for e in er.async_entries_for_device(entities, entry.device_id)
                  if e.domain == "sensor" and e.platform in _ROOMS
                  and (e.entity_id.endswith("_area") or str(e.unique_id).endswith("_area")
                       or e.platform != "bermuda")]
    return found or _named_after(hass, person)


def _first(name: str) -> str:
    return re.split(r"[^a-z]+", name.lower().strip())[0]


def _named_after(hass: HomeAssistant, person: State | None) -> list[str]:
    """Sensors with this person's name whose value is one of the home's rooms."""
    first = _first(person.name) if person is not None else ""
    others = [_first(p.name) for p in hass.states.async_all("person")
              if person is not None and p.entity_id != person.entity_id]
    # Two people called the same cannot be told apart by name.
    if len(first) < 3 or first in others:
        return []
    rooms = {area.name.lower() for area in ar.async_get(hass).async_list_areas()}
    found = []
    for state in hass.states.async_all("sensor"):
        if _first(state.name.replace("'", "")) not in (first, f"{first}s"):
            continue
        if (state.state.lower() in rooms
                or state.attributes.get("device_class") == "bermuda__custom_device_class"
                and state.entity_id.endswith("_area")):
            found.append(state.entity_id)
    return sorted(found)


def detail(hass: HomeAssistant, state: State | None,
           rooms: dict[str, str] | None = None) -> dict[str, Any]:
    if state is None:
        return {}
    found: dict[str, Any] = {"since": state.last_changed.timestamp()}
    entry = er.async_get(hass).async_get(state.entity_id)
    device = dr.async_get(hass).async_get(entry.device_id) if entry and entry.device_id else None
    area_id = (entry.area_id if entry else None) or (device.area_id if device else None)
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    if area is not None:
        found["area"] = area.name[:40]
        floor = fr.async_get(hass).async_get_floor(area.floor_id) if area.floor_id else None
        if floor is not None:
            found["floor"] = floor.name[:40]
    if state.entity_id.startswith("person."):
        # A person has no room of their own, only the one they are in now.
        found.pop("area", None)
        found.pop("floor", None)
        if state.state == "home":
            for sensor in room_sensors(hass, state, rooms):
                room = hass.states.get(sensor)
                if room is not None and room.state.lower() not in _NOWHERE:
                    found["area"] = room.state[:40]
                    break
    if state.state not in ("unavailable", "unknown") and (text := _text(state)):
        found["text"] = text[:160]
    if path := picture_path(state):
        found["picture"] = hashlib.sha256(path.encode()).hexdigest()[:16]
    return found


def _text(state: State) -> str:
    a, parts = state.attributes, []

    def percent(key: str, label: str, top: float = 100) -> None:
        if isinstance(value := a.get(key), (int, float)):
            parts.append(f"{label}{round(value / top * 100)}%")

    domain = state.entity_id.split(".", 1)[0]
    if domain == "person" and state.state not in ("home", "not_home"):
        parts.append(f"at {state.state}")  # a named place, never coordinates
    if domain == "light" and state.state == "on":
        percent("brightness", "", 255)
    elif domain == "media_player" and state.state in ("playing", "paused", "on"):
        what = [str(a[k]) for k in ("media_title", "media_artist") if a.get(k)]
        if what:
            parts.append(" by ".join(what))
        if a.get("source") or a.get("app_name"):
            parts.append(str(a.get("app_name") or a["source"]))
        percent("volume_level", "volume ", 1)
    elif domain == "climate" and a.get("hvac_action"):
        parts.append(str(a["hvac_action"]))
    elif domain == "cover":
        percent("current_position", "")
    elif domain == "fan":
        percent("percentage", "")
    elif domain == "weather" and isinstance(a.get("temperature"), (int, float)):
        parts.append(f"{a['temperature']:g}{a.get('temperature_unit', '')}")
    for key in ("battery_level", "battery"):
        if isinstance(a.get(key), (int, float)):
            percent(key, "battery ")
            break
    return ", ".join(parts)


async def picture(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    """The picture Home Assistant shows for this device."""
    path = picture_path(hass.states.get(entity_id))
    if path is None or hass.http is None:
        return {"error": "none"}
    scheme = "https" if hass.config.api and hass.config.api.use_ssl else "http"
    async with async_get_clientsession(hass, verify_ssl=False).get(
            f"{scheme}://127.0.0.1:{hass.http.server_port}{path}",
            allow_redirects=False) as response:
        if response.status != 200:
            return {"error": "none"}
        data = b""
        async for part in response.content.iter_chunked(65536):
            data += part
            if len(data) > MAX_PICTURE:
                return {"error": "none"}
    kind = image_kind(data)
    if kind is None:
        return {"error": "none"}
    return {"kind": kind, "data": base64.b64encode(data).decode()}


def image_kind(data: bytes) -> str | None:
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return next((kind for magic, kind in _MAGIC if data.startswith(magic)), None)
