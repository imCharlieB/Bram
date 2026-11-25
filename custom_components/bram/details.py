"""More about a shared device: its room, how long, and what it is doing."""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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


def detail(hass: HomeAssistant, state: State | None) -> dict[str, Any]:
    if state is None:
        return {}
    found: dict[str, Any] = {"since": state.last_changed.timestamp()}
    entry = er.async_get(hass).async_get(state.entity_id)
    device = dr.async_get(hass).async_get(entry.device_id) if entry and entry.device_id else None
    area_id = (entry.area_id if entry else None) or (device.area_id if device else None)
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    if area is not None:
        found["area"] = area.name[:40]
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
