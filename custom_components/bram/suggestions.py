"""Suggestions from what the owner does: a message hidden again and again, or told often with
nothing done. The server notices; this checks and waits for an admin's answer (F4).

Only a Stop these or Less often that a phone was really given can be suggested, so a safety
alert's Acknowledge never can (C3). Fixed text; no model.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PHONES, DOMAIN
from .notifier import notify

REVIEW = "/bram-review"
EXPIRES = 30 * 86400
ANNOUNCE_EVERY = 86400  # at most one phone message a day about suggestions
MAX_WAITING = 10
SOURCES = ("rules", "printers", "problems")  # routine messages only
WORDS = {"Stop these": "stop", "Less often": "less"}


def _id(key: str) -> str:
    return "habit:" + hashlib.sha256(key.encode()).hexdigest()[:16]


class Suggestions:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, known: Callable[[str], Any],
                 act: Callable[[str], None], note: Callable[..., None]) -> None:
        self._hass, self._entry = hass, entry
        self._known, self._act, self._note = known, act, note
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.habits")
        self.data: dict[str, Any] = {"waiting": [], "never": [], "announced": 0}

    async def start(self) -> None:
        self.data = {**self.data, **(await self._store.async_load() or {})}

    @callback
    def received(self, key: object, why: object) -> bool:
        """From the server: a finding worth asking about. Checked against what HA itself sent."""
        if not isinstance(key, str) or not isinstance(why, str) or len(why) > 200:
            return False
        known = self._known(key)
        now = dt_util.utcnow().timestamp()
        waiting = [w for w in self.data["waiting"] if now - w["at"] < EXPIRES]
        if (known is None or known.get("source") not in SOURCES or key in self.data["never"]
                or any(w["key"] == key for w in waiting) or len(waiting) >= MAX_WAITING):
            return False
        buttons = [b for b in known["buttons"] if b["title"] in WORDS]
        if not buttons:
            return False
        waiting.append({"key": key, "why": " ".join(why.split()), "text": known["text"],
                        "buttons": buttons, "at": now})
        self.data["waiting"] = waiting
        self._save()
        if now - self.data["announced"] >= ANNOUNCE_EVERY:
            self.data["announced"] = now
            self._hass.async_create_task(self._announce(known["text"]), "bram suggestion")
        return True

    async def _announce(self, text: str) -> None:
        phones = self._entry.options.get(CONF_PHONES, [])
        if phones:
            await notify(self._hass, phones, "BRAM suggests a change",
                         f"Fewer messages about: {text[:120]}. Tap to review.",
                         "bram_suggestion", safety=False, actions=[], url=REVIEW)

    def review(self) -> list[dict[str, Any]]:
        now = dt_util.utcnow().timestamp()
        return [{
            "id": _id(w["key"]), "title": "Fewer messages about this?",
            "text": f"{w['text']} {w['why']}".strip(), "changes": [],
            "expires": w["at"] + EXPIRES,
            "choices": [*({"answer": WORDS[b["title"]], "label": b["title"],
                           "main": WORDS[b["title"]] == "stop"} for b in w["buttons"]),
                        {"answer": "later", "label": "Not now"},
                        {"answer": "never", "label": "Never suggest this"}],
            "note": "Stop these: no more of this message. Less often: at most once a day. Undo "
                    "either with the BRAM button Allow stopped messages."}
            for w in self.data["waiting"] if now - w["at"] < EXPIRES]

    @callback
    def answer(self, item: str, word: str, who: str) -> bool:
        found = next((w for w in self.data["waiting"] if _id(w["key"]) == item), None)
        if found is None:
            return False
        if word in ("stop", "less"):
            action = next((b["action"] for b in found["buttons"] if WORDS[b["title"]] == word),
                          None)
            if action is None:
                return False
            self._act(action)
        elif word == "never":
            self.data["never"] = [*self.data["never"], found["key"]][-200:]
        elif word != "later":
            return False
        self.data["waiting"] = [w for w in self.data["waiting"] if w is not found]
        said = {"stop": "Stop these", "less": "Less often", "later": "Not now",
                "never": "Never suggest this"}[word]
        # Written down with who answered; a stop itself is noted by the rule that stops (F3).
        source = found["key"].partition(":")[0]
        self._note(found["key"], "held", f"Suggestion answered: {said}"
                   f"{', by ' + who if who else ''}", source if source in SOURCES else "message",
                   "low")
        self._save()
        return True

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 1)
