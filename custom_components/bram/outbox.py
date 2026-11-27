"""Notes for the server's record of findings. Kept until the server confirms each one.

Only tells the server what Home Assistant already decided. Nothing waits for it.
"""
from __future__ import annotations

import datetime
import re
import secrets
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

MAX_WAITING = 500
BATCH = 20
RESEND = 60
# By now every watcher has looked again, so what nobody sees is over.
SETTLED = 2 * 3600
# What BRAM's page may press for you: Stop these and Less often. Never Acknowledge (C3, C4).
PRESSABLE = re.compile(r"BRAM_(QUIET|PRINTER|PROBLEM|MUTE|LESS)_[\w:.\-]{1,200}")
TITLES = ("Stop these", "Less often")
MAX_OFFERED = 200


class Outbox:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 send: Callable[[dict], bool], ready: Callable[[], bool]) -> None:
        self._send, self._ready = send, ready
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.outbox")
        self._waiting: list[dict[str, Any]] = []
        self._open: dict[str, list[str]] = {}
        self._offered: dict[str, list[dict[str, str]]] = {}
        # The last buttons and words for each finding, kept after it is over, for suggestions.
        self._known: dict[str, dict[str, Any]] = {}
        self._seen: set[str] = set()
        self._tried: dict[str, float] = {}
        self._started = 0.0
        self._settled = False

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._waiting, self._open = saved.get("waiting", []), saved.get("open", {})
        self._offered = saved.get("offered", {})
        self._known = saved.get("known", {})
        self._started = self._now()
        return async_track_time_interval(self._hass, self._tick, datetime.timedelta(seconds=15))

    @callback
    def note(self, key: str, what: str, text: str, source: str, severity: str) -> None:
        if what == "open":
            self._seen.add(key)
            if key in self._open:
                return
            self._open[key] = [text, source, severity]
        elif what == "closed":
            self._offered.pop(key, None)
            if self._open.pop(key, None) is None:
                return
        self._queue({"key": key[:255], "what": what, "text": text[:1000], "source": source,
                     "severity": severity})

    @callback
    def offer(self, key: str, actions: list[dict[str, str]], source: str) -> None:
        """The buttons a phone was just given for this finding, so the page can show them."""
        kept = [{"action": a["action"], "title": a["title"]} for a in actions
                if PRESSABLE.fullmatch(str(a.get("action", ""))) and a.get("title") in TITLES]
        if not kept:
            return
        self._offered.pop(key, None)
        self._offered[key] = kept
        self._known.pop(key, None)
        self._known[key] = {"buttons": kept, "text": self._open.get(key, [""])[0],
                            "source": source}
        for table in (self._offered, self._known):
            for old in list(table)[:-MAX_OFFERED]:
                del table[old]
        self._buttons(key, source)

    def known(self, key: object) -> dict[str, Any] | None:
        """The buttons and words last given on a phone for this finding, if any."""
        return self._known.get(key) if isinstance(key, str) else None

    @callback
    def press(self, key: object, action: object) -> bool:
        """Only a button that was offered for this finding, once."""
        offered = self._offered.get(key) if isinstance(key, str) else None
        if not offered or not isinstance(action, str) or action not in [
                a["action"] for a in offered]:
            return False
        stop = next(a for a in offered if a["action"] == action)["title"] == "Stop these"
        left = [] if stop else [a for a in offered if a["action"] != action]
        if left:
            self._offered[key] = left
        else:
            del self._offered[key]
        source = self._open.get(key, ["", "message", ""])[1]
        self._buttons(key, source)
        return True

    @callback
    def _buttons(self, key: str, source: str) -> None:
        self._queue({"key": key[:255], "what": "buttons", "text": "", "source": source,
                     "severity": "low", "buttons": self._offered.get(key, [])})

    @callback
    def _queue(self, item: dict[str, Any]) -> None:
        self._waiting.append({"type": "note", "id": secrets.token_hex(8), "at": self._now(),
                              **item})
        del self._waiting[:-MAX_WAITING]
        self._save()
        self.flush()

    @callback
    def confirmed(self, uid: str) -> None:
        self._waiting = [w for w in self._waiting if w["id"] != uid]
        self._tried.pop(uid, None)
        self._save()

    async def _tick(self, now: datetime.datetime) -> None:
        self.tick()

    @callback
    def tick(self) -> None:
        if not self._settled and self._now() - self._started >= SETTLED:
            self._settled = True
            for key in [k for k in self._open if k not in self._seen]:
                _, source, severity = self._open[key]
                self.note(key, "closed", "No longer seen", source, severity)
        self.flush()

    @callback
    def flush(self) -> None:
        if not self._ready():
            return
        now = self._now()
        for item in self._waiting[:BATCH]:
            if now - self._tried.get(item["id"], 0) >= RESEND:
                if not self._send(item):
                    return
                self._tried[item["id"]] = now

    @callback
    def reconnected(self) -> None:
        self._tried.clear()
        self.flush()

    def _now(self) -> float:
        return dt_util.utcnow().timestamp()

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {"waiting": self._waiting, "open": self._open, "offered": self._offered,
                     "known": self._known}, 1)
