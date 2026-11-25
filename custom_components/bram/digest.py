"""One short summary a day, if the owner sets a time. Fixed text, no model, no server."""
from __future__ import annotations

import datetime
from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import CONF_DIGEST, CONF_ENTITIES, CONF_PHONES, SAFETY
from .feed import Feed, kind_of
from .notifier import notify
from .queries import _low

UNKNOWN = ("unavailable", "unknown", "")


class Digest:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, feed: Feed) -> None:
        self._hass, self._feed = hass, feed
        self._entities: list[str] = entry.options.get(CONF_ENTITIES, [])
        self._phones: list[str] = entry.options.get(CONF_PHONES, [])
        self._at = dt_util.parse_time(entry.options.get(CONF_DIGEST) or "")

    def start(self) -> Callable[[], None]:
        if self._at is None:
            return lambda: None
        return async_track_time_change(
            self._hass, self._send, hour=self._at.hour, minute=self._at.minute, second=0)

    async def _send(self, now: datetime.datetime) -> None:
        await notify(self._hass, self._phones, "BRAM daily summary", self.text(), "bram_digest",
                     safety=False, actions=[])

    @callback
    def text(self) -> str:
        trouble, opened, unlocked, unseen, home, away = [], [], [], [], [], []
        batteries = []
        for entity_id in self._entities:
            state = self._hass.states.get(entity_id)
            name = state.name if state is not None else entity_id
            value = state.state if state is not None else "unavailable"
            # The feed remembers the type if the sensor has lost it for now.
            kind = self._feed.kind(entity_id) or kind_of(
                entity_id, state.attributes.get("device_class") if state else None)
            if value in UNKNOWN:
                unseen.append(name)
            elif kind in SAFETY and value == "on":
                trouble.append(name)
            elif kind == "opening" and value in ("on", "open"):
                opened.append(name)
            elif kind == "lock" and value != "locked":
                unlocked.append(name)
            elif kind == "person":
                (home if value == "home" else away).append(name)
        for state in self._hass.states.async_all("sensor"):
            if _low(state):
                batteries.append(f"{state.name} {state.state}%")
        lines = [f"{label}: {_names(names)}" for label, names in (
            ("SAFETY ALERT", trouble), ("Open", opened), ("Not locked", unlocked),
            ("Can't see", unseen), ("Home", home), ("Away", away),
            ("Low batteries", sorted(batteries))) if names]
        if not (trouble or opened or unlocked or unseen):
            lines.insert(0, "Every lock and door I can see is locked and closed.")
        if not self._feed.connected:
            lines.append("The BRAM Server is not connected.")
        return "\n".join(lines)


def _names(names: list[str]) -> str:
    more = f" and {len(names) - 8} more" if len(names) > 8 else ""
    return ", ".join(names[:8]) + more
