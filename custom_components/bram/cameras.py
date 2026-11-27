"""What the BRAM Server says about cameras, checked before it is used (E2).

Only the server reads Frigate. Home Assistant keeps each watched camera's latest event for
BRAM's camera messages, not as entities: the Frigate integration already has those.
Text from the server is data, never instructions.
"""
from __future__ import annotations

import re
from typing import Any

NAME = re.compile(r"[A-Za-z0-9_\-]{1,64}")
EVENT_KEYS = {"id", "label", "who", "zones", "start", "end", "picture", "summary"}
MAX_CAMERAS = 64


def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or len(value) > limit:
        return None
    return " ".join("".join(c if c.isprintable() else " " for c in value).split())


def _time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if 0 < value < 1e11 else None


def names(raw: object) -> list[str] | None:
    if not isinstance(raw, list) or len(raw) > MAX_CAMERAS:
        return None
    if not all(isinstance(n, str) and NAME.fullmatch(n) for n in raw):
        return None
    return list(dict.fromkeys(raw))


def patterns(raw: object) -> list[tuple[str, str, tuple[str, ...]]] | None:
    """What the owner said is not news: a camera, a kind of thing, and its zones."""
    if not isinstance(raw, list) or len(raw) > 50:
        return None
    found = []
    for item in raw:
        if (not isinstance(item, dict) or item.keys() != {"camera", "label", "zones"}
                or not isinstance(item["camera"], str) or not NAME.fullmatch(item["camera"])
                or _text(item["label"], 32) is None or not isinstance(item["zones"], list)
                or not all(isinstance(z, str) and len(z) <= 64 for z in item["zones"])):
            return None
        found.append((item["camera"], item["label"], tuple(sorted(item["zones"]))))
    return found


def zones(raw: object) -> dict[str, list[str]] | None:
    """Each camera's zone names from Frigate, only for the settings page."""
    if not isinstance(raw, dict) or len(raw) > MAX_CAMERAS:
        return None
    found = {}
    for name, items in raw.items():
        if (not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(items, list)
                or len(items) > 20
                or not all(isinstance(z, str) and 0 < len(z) <= 64 for z in items)):
            return None
        found[name] = [" ".join(z.split()) for z in items]
    return found


def event(raw: object) -> dict[str, Any] | None:
    """One Frigate event as the server summed it up, or None if anything is off."""
    if not isinstance(raw, dict) or raw.keys() not in (EVENT_KEYS, EVENT_KEYS | {"description"}):
        return None
    words = raw.get("description")
    if words is not None and (_text(words, 300) is None or not _text(words, 300)):
        return None
    found = {"id": _text(raw["id"], 80), "label": _text(raw["label"], 32),
             "who": _text(raw["who"], 64), "summary": _text(raw["summary"], 200),
             "start": _time(raw["start"])}
    zones = raw["zones"]
    if (any(v is None for v in found.values()) or not found["id"]
            or not isinstance(zones, list) or len(zones) > 10
            or not all(isinstance(z, str) and len(z) <= 64 for z in zones)
            or not isinstance(raw["picture"], bool)
            or (raw["end"] is not None and _time(raw["end"]) is None)):
        return None
    return {**found, "description": _text(words, 300) if words is not None else None,
            "zones": [" ".join(z.split()) for z in zones],
            "end": _time(raw["end"]) if raw["end"] is not None else None,
            "picture": raw["picture"]}

