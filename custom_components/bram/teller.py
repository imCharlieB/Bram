"""How often a routine message may reach a phone. Plain rules, no model.

Never used for safety alerts, or for locks and doors at night or while everyone is away:
those always go out (C3). Nothing becomes quieter unless its words say it is a reminder, or the
owner asks for less.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

DAY = 86400
FIXED_FOR = DAY  # something that was fixed is news again after a day
MONTH = 30 * DAY
WEEK = 7 * DAY
OFFER_LESS = 3  # from the third time in a week, the owner may ask for it less often
KEEP = 35 * DAY
LESS = "BRAM_LESS_"

# Looking after things, rather than something wrong.
MAINTENANCE = re.compile(
    r"lubricat|maintenan|clean|replac|calibrat|\bdue\b|\bwear|lifetime|\bservice|\boil\b|"
    r"grease|filter|firmware|update (is )?(available|waiting)|new version|reminder|"
    r"\bempty\b|refill|descal|consumable|end of life", re.I)

EACH_TIME, UNTIL_FIXED, MONTHLY = "each time", "until fixed", "monthly"


def grade(text: str, usual: str = UNTIL_FIXED) -> str:
    """What the words say about how often it is worth telling."""
    return MONTHLY if MAINTENANCE.search(text) else usual


def _mark(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class Teller:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 note: Callable[..., None] = lambda *a: None,
                 offer: Callable[..., None] = lambda *a: None) -> None:
        self._hass, self._note, self.offer = hass, note, offer
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.told")
        self._told: dict[str, dict[str, Any]] = {}
        self._less: list[str] = []
        self._held: set[str] = set()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._told, self._less = saved.get("told", {}), saved.get("less", [])
        return self._hass.bus.async_listen("mobile_app_notification_action", self.answered)

    def allow(self, key: str, text: str, usual: str = UNTIL_FIXED, *,
              finding: str | None = None, source: str = "message") -> bool:
        """Whether to send it now, and if not, why is written down once."""
        reason = self._decide(key, text, usual)
        if reason is None:
            self._held.discard(key)
            return True
        if finding is not None and key not in self._held:
            self._held.add(key)
            self._note(finding, "held", reason, source, "low")
        return False

    def _decide(self, key: str, text: str, usual: str) -> str | None:
        now = dt_util.utcnow().timestamp()
        kind = grade(text, usual)
        before = self._told.get(key)
        if before is None or before["text"] != text:
            return None  # never told, or something new
        if kind == MONTHLY:
            return None if now - before["last"] >= MONTH else (
                "A reminder: already told this month")
        if key in self._less and now - before["last"] < DAY:
            return "You asked for this at most once a day"
        if kind == EACH_TIME:
            return None  # its own rule already waits for it to last
        if before["ended"] is None:
            return "Still the same problem: already told"
        if now - before["ended"] < FIXED_FOR:
            before["ended"] = None  # came back: still the same event
            self._save()
            return "Came back within a day: the same problem"
        return None

    def actions(self, key: str) -> list[dict[str, str]]:
        """A Less often button, once something has been told a few times this week."""
        now = dt_util.utcnow().timestamp()
        before = self._told.get(key)
        recent = [t for t in before["times"] if now - t < WEEK] if before else []
        if len(recent) + 1 < OFFER_LESS or key in self._less:
            return []
        return [{"action": LESS + _mark(key), "title": "Less often"}]

    @callback
    def told(self, key: str, text: str) -> None:
        now = dt_util.utcnow().timestamp()
        before = self._told.get(key)
        same = before is not None and before["text"] == text
        times = [t for t in (before["times"] if same else []) if now - t < WEEK] + [now]
        self._told[key] = {"text": text, "times": times, "last": now, "ended": None}
        self._save()

    @callback
    def ended(self, key: str) -> None:
        if (before := self._told.get(key)) is not None and before["ended"] is None:
            before["ended"] = dt_util.utcnow().timestamp()
            self._save()

    @callback
    def answered(self, event: Event) -> None:
        action = event.data.get("action")
        if not isinstance(action, str) or not action.startswith(LESS):
            return
        for key, before in self._told.items():
            if _mark(key) == action[len(LESS):] and key not in self._less:
                self._less.append(key)
                self._note(f"less:{key}", "open", f"You asked for this at most once a day: "
                           f"{before['text']}", "message", "low")
                self._save()

    @callback
    def allow_all(self) -> None:
        """Undo every Less often."""
        self._less = []
        self._save()

    @callback
    def _save(self) -> None:
        now = dt_util.utcnow().timestamp()
        self._store.async_delay_save(lambda: {"less": self._less, "told": {
            k: v for k, v in self._told.items()
            if v["ended"] is None or now - v["ended"] < KEEP}}, 5)
