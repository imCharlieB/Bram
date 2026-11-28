"""Nightly checks BRAM suggests from what it learned: a door, window, or lock that is often still
open or unlocked at the same hour. The server finds the pattern in history; this checks it and
waits for an admin's answer on the review page (F4). Fixed text; no model.

An approved check is kept in BRAM's options, and the house rules look at it each night.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_LEARN, CONF_PHONES, DEFAULT_NIGHT_FROM, DEFAULT_NIGHT_TO, DOMAIN
from .home_alerts import within
from .names import name_of
from .notifier import notify
from .shared import shared

REVIEW = "/bram-review"
HOURS = (20, 21, 22, 23, 0, 1)
AWAY = -1  # not an hour: while everyone is away
LEFT_ON = ("light", "switch", "fan")
KEYS = {"entity_id", "name", "kind", "hour", "times", "of"}
EXPIRES = 30 * 86400
ANNOUNCE_EVERY = 86400
MAX_WAITING = 3
CHECKS = "checks"


def spoken_hour(hour: int) -> str:
    return datetime.time(hour).strftime("%I %p").lstrip("0")


def item(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or raw.keys() != KEYS:
        return None
    if isinstance(raw["hour"], bool) or not isinstance(raw["hour"], int):
        return None
    evening = raw["kind"] in ("opening", "lock") and raw["hour"] in HOURS
    away = raw["kind"] in LEFT_ON and raw["hour"] == AWAY
    if (not isinstance(raw["entity_id"], str) or not (evening or away)
            or not all(isinstance(raw[k], int) and not isinstance(raw[k], bool) and
                       0 < raw[k] <= 60 for k in ("times", "of"))
            or raw["times"] > raw["of"]):
        return None
    return dict(raw)


class Checks:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 note: Callable[..., None] = lambda *a: None) -> None:
        self._hass, self._entry, self._note = hass, entry, note
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.checks")
        self.data: dict[str, Any] = {"waiting": [], "never": [], "announced": 0}

    async def start(self) -> None:
        self.data = {**self.data, **(await self._store.async_load() or {})}

    def _covered(self, found: dict[str, Any]) -> bool:
        """Already told by a rule that is on, or already a check."""
        options = self._entry.options
        if any(c["entity_id"] == found["entity_id"] for c in options.get(CHECKS, [])):
            return True
        if found["hour"] == AWAY:
            return found["entity_id"] in options.get("away_on", [])
        night = (options.get("night_from", DEFAULT_NIGHT_FROM),
                 options.get("night_to", DEFAULT_NIGHT_TO))
        at_night = within(night, datetime.time(found["hour"], 1))
        rule = "night" if found["kind"] == "lock" else "open_night"
        return bool(options.get(rule)) and at_night

    @callback
    def received(self, items: object) -> int:
        """Patterns from the server's history. Each is checked here; none changes anything."""
        if not self._entry.options.get(CONF_LEARN) or not isinstance(items, list):
            return 0
        now = dt_util.utcnow().timestamp()
        mine = set(shared(self._hass, self._entry.options))
        waiting = [w for w in self.data["waiting"] if now - w["at"] < EXPIRES]
        added = 0
        for raw in items[:10]:
            found = item(raw)
            if (found is None or found["entity_id"] not in mine
                    or found["entity_id"] in self.data["never"] or self._covered(found)
                    or any(w["entity_id"] == found["entity_id"] for w in waiting)
                    or len(waiting) >= MAX_WAITING):
                continue
            waiting.append({**found, "at": now})
            added += 1
        self.data["waiting"] = waiting
        if added:
            self._save()
            if now - self.data["announced"] >= ANNOUNCE_EVERY:
                self.data["announced"] = now
                self._hass.async_create_task(self._announce(), "bram check suggestion")
        return added

    async def _announce(self) -> None:
        phones = self._entry.options.get(CONF_PHONES, [])
        if phones:
            await notify(self._hass, phones, "BRAM suggests a check",
                         "Something is often left open at night. Tap to review.",
                         "bram_suggestion", safety=False, actions=[], url=REVIEW)

    def review(self) -> list[dict[str, Any]]:
        now = dt_util.utcnow().timestamp()
        shown = []
        for w in self.data["waiting"]:
            if now - w["at"] >= EXPIRES or self._covered(w):
                continue
            name = name_of(self._hass, w["entity_id"])
            if w["hour"] == AWAY:
                shown.append({
                    "id": f"check:{w['entity_id']}",
                    "title": f"Tell you when {name} is left on while everyone is away?",
                    "text": f"On {w['times']} of the last {w['of']} days everyone was away, "
                            f"{name} was on for ten minutes or more. BRAM can tell you when it "
                            "is left on after everyone leaves. It never turns anything off.",
                    "changes": [{"name": "Left on while away", "now": "Not told",
                                 "new": f"Told about {name}"}],
                    "expires": w["at"] + EXPIRES,
                    "note": "Nothing changes unless you approve. Remove it later under BRAM, "
                            "Configure, Learning."})
                continue
            at = spoken_hour(w["hour"])
            state = "unlocked" if w["kind"] == "lock" else "open"
            shown.append({
                "id": f"check:{w['entity_id']}", "title": f"Check {name} at {at}?",
                "text": f"On {w['times']} of the last {w['of']} nights, {name} was still "
                        f"{state} at {at}. BRAM can check it at {at} each night and tell you "
                        f"if it is {state}.",
                "changes": [{"name": "Nightly check", "now": "None",
                             "new": f"{name}, at {at}"}],
                "expires": w["at"] + EXPIRES,
                "note": "Nothing changes unless you approve. Remove a check later under BRAM, "
                        "Configure, Learning."})
        return shown

    @callback
    def answer(self, item_id: str, word: str, who: str) -> bool:
        found = next((w for w in self.data["waiting"] if f"check:{w['entity_id']}" == item_id),
                     None)
        if found is None or word not in ("approve", "later", "never"):
            return False
        self.data["waiting"] = [w for w in self.data["waiting"] if w is not found]
        said = {"approve": "Approved", "later": "Not now", "never": "Never suggest this"}[word]
        self._note(f"learning:check:{found['entity_id']}", "held",
                   f"Suggested check answered: {said}{', by ' + who if who else ''}",
                   "learning", "low")
        if word == "never":
            self.data["never"] = [*self.data["never"], found["entity_id"]][-200:]
        self._save()
        if word == "approve" and found["hour"] == AWAY:
            options = dict(self._entry.options)
            options["away_on"] = sorted({*options.get("away_on", []), found["entity_id"]})
            self._hass.config_entries.async_update_entry(self._entry, options=options)
            self._hass.config_entries.async_schedule_reload(self._entry.entry_id)
        elif word == "approve":
            options = dict(self._entry.options)
            checks = [c for c in options.get(CHECKS, [])
                      if c["entity_id"] != found["entity_id"]]
            options[CHECKS] = [*checks, {"entity_id": found["entity_id"],
                                         "hour": found["hour"]}]
            self._hass.config_entries.async_update_entry(self._entry, options=options)
            self._hass.config_entries.async_schedule_reload(self._entry.entry_id)
        return True

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 1)
