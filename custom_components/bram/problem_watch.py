"""Tells about new problems once, and again when fixed. Fixed text, no model, no server."""
from __future__ import annotations

import asyncio
import datetime
import hashlib
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PHONES, CONF_PROBLEM_WATCH, CONF_QUIET_FROM, CONF_QUIET_TO, DOMAIN
from .home_alerts import GROUP_MAX, GROUP_MIN, within
from .notifier import notify
from .problems import Finder, Problem
from .teller import Teller

EVERY = datetime.timedelta(minutes=10)
DAILY = 8
DAY = 86400
MANY = 8  # more than this at once is told as a number
SETTLE = DAY  # something that comes and goes is told once a day at most
MUTE = "BRAM_PROBLEM_"
# After a start, every check needs time before its silence means anything (B2).
STARTING = 2 * 3600


def mark(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class ProblemWatch:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, is_night: Callable[[], bool],
                 note: Callable[..., None] = lambda *a: None,
                 teller: Teller | None = None) -> None:
        self._hass, self._note, self._is_night = hass, note, is_night
        self._teller = teller or Teller(hass, entry)
        self._on: bool = entry.options.get(CONF_PROBLEM_WATCH, False)
        self._phones: list[str] = entry.options.get(CONF_PHONES, [])
        self._quiet = (entry.options.get(CONF_QUIET_FROM), entry.options.get(CONF_QUIET_TO))
        self._finder = Finder(hass, entry)
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.problems")
        self._told: dict[str, list] = {}  # key: text, when told, when it went away or None
        self._muted: list[str] = []
        self._open: dict[str, Problem] = {}
        self._sent: list[float] = []
        self._lock = asyncio.Lock()
        self._started = dt_util.utcnow().timestamp()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._told, self._muted = saved.get("told", {}), saved.get("muted", [])
        if not self._on:
            return lambda: None
        stops = [async_track_time_interval(self._hass, self._tick, EVERY),
                 self._hass.bus.async_listen("mobile_app_notification_action", self._answered)]

        @callback
        def stop() -> None:
            for item in stops:
                item()
        return stop

    async def _tick(self, now: datetime.datetime) -> None:
        if self._hass.is_running:
            await self.run()

    @callback
    def _answered(self, event: Event) -> None:
        action = event.data.get("action")
        if not isinstance(action, str) or not action.startswith(MUTE):
            return
        for key in [*self._told, *self._open]:
            if mark(key) == action[len(MUTE):] and key not in self._muted:
                self._muted.append(key)
                self._note(f"problems:{key}", "stopped", "Stopped from a phone", "problems", "low")
                self._save()

    @callback
    def allow_all(self) -> None:
        self._muted = []
        self._save()

    async def run(self) -> None:
        async with self._lock:
            now = dt_util.utcnow().timestamp()
            found = {p.key: p for p in await self._finder.find(self._is_night())}
            for key, problem in found.items():
                self._note(f"problems:{key}", "open", problem.text, "problems", problem.level)
                if key in self._told:
                    self._told[key][2] = None
            # A check that did not run proves nothing is fixed (B2).
            if self._finder.not_run:
                found = {**self._open, **found}
            for key in self._open.keys() - found.keys():
                self._note(f"problems:{key}", "closed", "Fixed", "problems", "low")
                self._teller.ended(f"problem:{key}")
            self._open = found
            for key, told in list(self._told.items()):
                if key not in found and now - self._started >= STARTING:
                    told[2] = told[2] or now
            await self._tell(now)
            self._told = {k: t for k, t in self._told.items()
                          if t[2] is None or now - t[2] < SETTLE}
            self._save()

    async def _tell(self, now: float) -> None:
        self._sent = [t for t in self._sent if now - t < DAY]
        if not self._phones or within(self._quiet, dt_util.now().time()):
            return
        new = [p for p in self._open.values() if p.tell and p.key not in self._told
               and p.key not in self._muted and self._teller.allow(
                   f"problem:{p.key}", p.text, finding=f"problems:{p.key}", source="problems")]
        new.sort(key=lambda p: p.level != "medium")
        # Fixed is told only for what was told, and only once it has stayed fixed a while.
        fixed = [k for k, t in self._told.items()
                 if t[2] is not None and len(t) == 3 and not k.startswith("stuck:")
                 and now - t[2] >= EVERY.total_seconds()]
        if len(new) > MANY:
            text = (f"I found {len(new)} problems with Home Assistant. First: "
                    + "\n".join(p.text for p in new[:3])
                    + "\nThe rest are under Findings on BRAM's page.")
            if await self._send(now, text, "bram_problems", None):
                for problem in new:
                    self._mark(problem, now)
        else:
            groups = ([[p] for p in new] if len(new) < GROUP_MIN else
                      [new[i:i + GROUP_MAX] for i in range(0, len(new), GROUP_MAX)])
            for group in groups:
                key = group[0].key
                if await self._send(now, "\n".join(p.text for p in group),
                                    f"bram_problem_{mark(key)}",
                                    key if len(group) == 1 else None):
                    for problem in group:
                        self._mark(problem, now)
        if fixed and await self._send(
                now, "Fixed: " + "\n".join(self._told[k][0] for k in fixed[:GROUP_MAX]),
                "bram_fixed", None):
            for key in fixed:
                self._told[key].append(True)

    def _mark(self, problem: Problem, now: float) -> None:
        self._told[problem.key] = [problem.text, now, None]
        self._teller.told(f"problem:{problem.key}", problem.text)
        self._note(f"problems:{problem.key}", "sent", f"Phone: {problem.text}", "problems",
                   problem.level)

    async def _send(self, now: float, text: str, tag: str, key: str | None) -> bool:
        if len(self._sent) >= DAILY:
            return False
        actions = [] if key is None else [{"action": MUTE + mark(key), "title": "Stop these"},
                                          *self._teller.actions(f"problem:{key}")]
        if not await notify(self._hass, self._phones, "BRAM", text, tag, safety=False,
                            actions=actions):
            return False
        self._sent.append(now)
        return True

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {"told": self._told, "muted": self._muted}, 1)
