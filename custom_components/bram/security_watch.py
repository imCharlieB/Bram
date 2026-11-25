"""Tells about new security findings. Fixed text, no model, no server. Off by default."""
from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PHONES, CONF_QUIET_FROM, CONF_QUIET_TO, CONF_SECURITY_WATCH, DOMAIN
from .home_alerts import within
from .notifier import notify
from .security import check


class SecurityWatch:
    """Checks every hour and tells once about anything new. Off by default."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._on: bool = entry.options.get(CONF_SECURITY_WATCH, False)
        self._phones: list[str] = entry.options.get(CONF_PHONES, [])
        self._quiet = (entry.options.get(CONF_QUIET_FROM), entry.options.get(CONF_QUIET_TO))
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.security")
        self._known: dict[str, list[str]] | None = None
        self._told: set[str] = set()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._known, self._told = saved.get("known"), set(saved.get("told", []))
        if not self._on:
            return lambda: None
        return async_track_time_interval(self._hass, self._tick, datetime.timedelta(hours=1))

    async def _tick(self, now: datetime.datetime) -> None:
        await self.run()

    async def run(self) -> None:
        result = await check(self._hass, self._known)
        first = self._known is None
        new = [f for f in result["findings"] if f["key"] not in self._told]
        current = {f["key"] for f in result["findings"]}
        high = any(f["level"] == "high" for f in new)
        # What was there at the start is listed when asked, not announced.
        if new and not first:
            if not self._phones or (
                    not high and within(self._quiet, dt_util.now().time())):
                return
            text = "\n".join(f["text"] for f in new[:6])
            if not await notify(self._hass, self._phones, "BRAM security check", text,
                                "bram_security", safety=False, actions=[]):
                return  # tried again next hour, with nothing forgotten
        if "Accounts and tokens" in result["not_checked"] and first:
            return  # learning from an empty list would call every account new
        self._told = current
        self._known = {kind: sorted(set(ids) | set((self._known or {}).get(kind, [])))
                       for kind, ids in result["ids"].items()}
        await self._store.async_save({"known": self._known, "told": sorted(self._told)})
