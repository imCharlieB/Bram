"""Tells about prints and printers. Fixed text, no model, no server. Never controls a printer.

Not a fire alarm: heat warnings come from the printer's own sensors.
"""
from __future__ import annotations

import asyncio
import datetime
import json
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PHONES,
    CONF_PRINTERS,
    CONF_PRINTERS_CHOSEN,
    CONF_QUIET_FROM,
    CONF_QUIET_TO,
    DOMAIN,
)
from .home_alerts import within
from .notifier import notify
from .printers import Printer, find, read
from .teller import EACH_TIME, UNTIL_FIXED, Teller

EVERY = datetime.timedelta(seconds=30)
PAUSED_AFTER, LOST_AFTER, HEAT_AFTER, COLD_AFTER = 60, 300, 1200, 300
# In the printer's own unit, well above room temperature and any standby warmth.
HOT = {"°C": {"nozzle": 60, "nozzle2": 60, "bed": 45}, "°F": {"nozzle": 140, "nozzle2": 140,
                                                          "bed": 113}}
COLD = {"°C": 25, "°F": 45}
DAILY, DAY = 30, 86400
MUTE = "BRAM_PRINTER_"
KINDS = {"finished": "low", "failed": "medium", "stopped": "low", "paused": "medium",
         "lost": "medium", "hot": "medium", "cold": "medium", "problem": "medium"}


def length(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    hours, rest = divmod(minutes, 60)
    return (f"{hours} h {rest} min" if rest else f"{hours} h") if hours else f"{minutes} min"


class PrinterWatch:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 send: Callable[[list[dict]], bool] = lambda items: True,
                 note: Callable[..., None] = lambda *a: None,
                 teller: Teller | None = None) -> None:
        self._hass, self._send, self._note = hass, send, note
        self._teller = teller or Teller(hass, entry)
        self._on: bool = entry.options.get(CONF_PRINTERS, False)
        self._phones: list[str] = entry.options.get(CONF_PHONES, [])
        # Only a printer the owner switched on is watched or shown.
        self._chosen: list[str] = entry.options.get(CONF_PRINTERS_CHOSEN, [])
        self._quiet = (entry.options.get(CONF_QUIET_FROM), entry.options.get(CONF_QUIET_TO))
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.printers")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._muted: list[str] = []
        self._since: dict[str, float] = {}
        self._told: set[str] = set()
        self._waiting: list[dict[str, Any]] = []
        self._sent: list[float] = []
        self._last: list[dict] | None = None
        self._last_sent = 0.0
        self._lock = asyncio.Lock()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._jobs, self._muted = saved.get("jobs", {}), saved.get("muted", [])
        self._waiting = saved.get("waiting", [])
        if not self._on:
            return lambda: None
        stops = [async_track_time_interval(self._hass, self._tick, EVERY),
                 self._hass.bus.async_listen("mobile_app_notification_action", self.answered)]

        @callback
        def stop() -> None:
            for item in stops:
                item()
        return stop

    async def _tick(self, now: datetime.datetime) -> None:
        if self._hass.is_running:
            await self.run()

    @callback
    def answered(self, event: Event) -> None:
        action = event.data.get("action")
        if isinstance(action, str) and action.startswith(MUTE):
            key = action[len(MUTE):]
            if key.partition(":")[0] in KINDS and len(key) < 100 and key not in self._muted:
                self._muted.append(key)
                self._note(f"printers:{key}", "stopped", "Stopped", "printers", "low")
                self._save()

    @callback
    def allow_all(self) -> None:
        self._muted = []
        self._save()

    async def run(self) -> None:
        async with self._lock:
            now = dt_util.utcnow().timestamp()
            items = []
            for printer in find(self._hass):
                if printer.id not in self._chosen:
                    continue
                says = read(self._hass, printer)
                self._job(printer, says, now)
                self._conditions(printer, says, now)
                items.append(says)
            # Sent when something changed, and now and then for a server that restarted.
            if (items != self._last or now - self._last_sent >= 60) and self._send(items):
                self._last, self._last_sent = items, now
            await self._tell(now)

    # --- prints ---

    def _job(self, printer: Printer, says: dict[str, Any], now: float) -> None:
        job, state = self._jobs.get(printer.id), says["state"]
        if state in ("printing", "paused"):
            if job is None or job.get("ended") or (
                    job["file"] and says.get("file") and job["file"] != says["file"]):
                job = self._jobs[printer.id] = {"file": says.get("file", ""), "start": now,
                                                "seen": state == "printing"
                                                and says.get("progress", 0) <= 2}
            job["file"] = says.get("file") or job["file"]
            job["progress"] = says.get("progress", job.get("progress"))
            job["weight"] = says.get("weight", job.get("weight"))
            self._save()
            return
        if job is None or job.get("ended") or state in ("off", "unknown"):
            return
        result = state if state in ("finished", "failed", "stopped") else (
            # Some printers never say how it ended, only how far it got.
            "finished" if (job.get("progress") or 0) >= 99 else "stopped")
        job["ended"] = True
        what = f"{printer.name}: {job['file'] or 'the print'}"
        took = f" after {length(now - job['start'])}" if job["seen"] else ""
        text = {"finished": f"{what} is finished{took}.", "failed": f"{what} failed{took}.",
                "stopped": f"{what} was stopped{took}."}[result]
        self._note(f"printers:{result}:{printer.id}", "open", text, "printers", KINDS[result])
        if result != "failed":
            self._note(f"printers:{result}:{printer.id}", "closed", text, "printers", "low")
        self._note(f"print:{printer.id}", "print", json.dumps({
            "printer": printer.name, "file": job["file"], "start": round(job["start"]),
            "end": round(now), "result": result, "whole": job["seen"],
            "progress": job.get("progress"), "weight": job.get("weight")}), "printers", "low")
        self._queue(result, printer, text)
        self._save()

    # --- things that are wrong ---

    def _conditions(self, printer: Printer, says: dict[str, Any], now: float) -> None:
        state, job = says["state"], self._jobs.get(printer.id)
        active = job is not None and not job.get("ended")
        unit = says.get("unit", "")
        left = f" at {says['progress']}%" if "progress" in says else ""
        hot = [p for p, at in HOT.get(unit, {}).items() if says.get(p, 0) >= at
               and says.get(f"{p}_target", 0) > 0]
        cold = [p for p in ("nozzle", "bed") if unit in COLD and p in says
                and says.get(f"{p}_target", 0) - says[p] >= COLD[unit]]
        words = {"nozzle": "nozzle", "nozzle2": "left nozzle", "bed": "bed"}
        now_true = {
            "paused": (state == "paused", PAUSED_AFTER, f"{printer.name} is paused{left}."),
            "lost": (state in ("off", "unknown") and active, LOST_AFTER,
                     f"{printer.name} stopped answering during a print."),
            "hot": (state in ("idle", "finished", "stopped", "failed") and bool(hot), HEAT_AFTER,
                    f"{printer.name} is not printing, but its "
                    f"{' and '.join(words[p] for p in hot)} heater is still on."),
            "cold": (state == "printing" and bool(cold), COLD_AFTER + 600,
                     f"{printer.name} is printing, but its "
                     f"{' and '.join(words[p] for p in cold)} is far below its target."),
            "problem": (bool(says.get("problem")) and state != "off", PAUSED_AFTER,
                        f"{printer.name} reports a problem"
                        + (f": {says['problem_text']}" if says.get("problem_text") else ".")),
        }
        for kind, (true, wait, text) in now_true.items():
            key = f"{kind}:{printer.id}"
            # Not knowing is neither wrong nor fixed (B2).
            if state in ("off", "unknown") and kind != "lost" and key in self._since:
                continue
            if not true:
                self._since.pop(key, None)
                if key in self._told:
                    self._told.discard(key)
                    self._note(f"printers:{key}", "closed", "Over", "printers", "low")
                    self._teller.ended(f"printer:{key}")
                continue
            if now - self._since.setdefault(key, now) >= wait and key not in self._told:
                self._told.add(key)
                self._note(f"printers:{key}", "open", text, "printers", KINDS[kind])
                if self._teller.allow(f"printer:{key}", text,
                                      EACH_TIME if kind in ("paused",) else UNTIL_FIXED,
                                      finding=f"printers:{key}", source="printers"):
                    self._queue(kind, printer, text)
        if state == "printing":
            self._note(f"printers:failed:{printer.id}", "closed", "Printing again", "printers",
                       "low")

    def pending(self) -> list[dict]:
        """Prints counting down to their end, for BRAM's page."""
        now = dt_util.utcnow().timestamp()
        return [{"kind": "printer", "text": f"{says['name']}: {says.get('file') or 'print'}",
                 "since": self._jobs.get(says["id"], {}).get("start", now),
                 "due": now + says["left"]}
                for says in (self._last or []) if says.get("state") == "printing"
                and "left" in says]

    # --- telling ---

    def _queue(self, kind: str, printer: Printer, text: str) -> None:
        key = f"{kind}:{printer.id}"
        if key in self._muted:
            return
        self._waiting = [w for w in self._waiting if w["key"] != key]
        self._waiting.append({"key": key, "text": text, "tries": 0})

    async def _tell(self, now: float) -> None:
        if not self._phones or within(self._quiet, dt_util.now().time()):
            return
        self._sent = [t for t in self._sent if now - t < DAY]
        waiting, self._waiting = self._waiting, []
        for item in waiting:
            if len(self._sent) >= DAILY:
                return
            actions = [{"action": MUTE + item["key"], "title": "Stop these"},
                       *self._teller.actions(f"printer:{item['key']}")]
            if await notify(self._hass, self._phones, "BRAM printer", item["text"],
                            f"bram_printer_{item['key']}", safety=False, actions=actions,
                            finding=f"printers:{item['key']}"):
                self._sent.append(now)
                self._teller.told(f"printer:{item['key']}", item["text"])
                self._teller.offer(f"printers:{item['key']}", actions, "printers")
                self._note(f"printers:{item['key']}", "sent", f"Phone: {item['text']}",
                           "printers", "low")
            elif item["tries"] < 10:
                self._waiting.append({**item, "tries": item["tries"] + 1})
        if waiting:
            self._save()

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: {
            "jobs": self._jobs, "muted": self._muted, "waiting": self._waiting}, 5)
