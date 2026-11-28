"""How often a routine message may reach a phone. Plain rules, no model.

Never used for safety alerts, or for locks and doors at night or while everyone is away:
those always go out (C3). Something becomes quieter when its words say it is a reminder, when the
owner asks for less, or when BRAM learns it by itself from what happened (F4): something that
usually fixes itself within an hour waits an hour, and something that keeps coming back is told
at most once a week. Each is written down with why, and Allow stopped messages undoes it.
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
LEARN_DAYS = 14 * DAY
FIXES_ITSELF = 3600  # back to normal within an hour, by itself
OFTEN = 6  # times in two weeks
NEVER_LEARNED = ("silent:",)  # silent safety sensors are always told

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
        self._seen: dict[str, list[list[float]]] = {}  # [start, end or 0] for two weeks

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._told, self._less = saved.get("told", {}), saved.get("less", [])
        self._seen = saved.get("seen", {})
        return self._hass.bus.async_listen("mobile_app_notification_action", self.answered)

    def allow(self, key: str, text: str, usual: str = UNTIL_FIXED, *,
              finding: str | None = None, source: str = "message",
              asks_again: bool = False) -> bool:
        """Whether to send it now, and if not, why is written down once. asks_again: the caller
        asks again while it lasts, so it may be held to see whether it fixes itself."""
        self._started(key)
        reason = self._decide(key, text, usual)
        if reason is None and grade(text, usual) != EACH_TIME:  # its own rule's events
            reason = self._learned(key, asks_again)
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

    def _started(self, key: str) -> None:
        spans = self._seen.setdefault(key, [])
        if not spans or spans[-1][1]:
            spans.append([dt_util.utcnow().timestamp(), 0])
            self._save()

    def _learned(self, key: str, asks_again: bool) -> str | None:
        """Learned from what happened, with no answers needed. Routine messages only (F4)."""
        if key.startswith(NEVER_LEARNED):
            return None
        now = dt_util.utcnow().timestamp()
        spans = [s for s in self._seen.get(key, []) if now - s[0] < LEARN_DAYS]
        done = [s for s in spans if s[1]]
        quick = sum(1 for s in done if s[1] - s[0] <= FIXES_ITSELF)
        if asks_again and len(done) >= 3 and quick * 3 >= len(done) * 2:
            if now - spans[-1][0] < FIXES_ITSELF:
                return (f"It fixed itself within an hour {quick} of {len(done)} times in two "
                        "weeks. Waiting an hour to see")
        # Coming back within a day is the same event (a flicker), not another time.
        times = sum(1 for i, s in enumerate(spans)
                    if i == 0 or not spans[i - 1][1] or s[0] - spans[i - 1][1] >= FIXED_FOR)
        before = self._told.get(key)
        if times >= OFTEN and before and now - before["last"] < WEEK:
            return f"It came up {times} times in two weeks: told at most once a week"
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
        now = dt_util.utcnow().timestamp()
        if (spans := self._seen.get(key)) and not spans[-1][1]:
            spans[-1][1] = now
            self._held.discard(key)
            self._save()
        if (before := self._told.get(key)) is not None and before["ended"] is None:
            before["ended"] = now
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
        """Undo every Less often, and everything BRAM learned by itself."""
        self._less, self._seen = [], {}
        self._save()

    @callback
    def _save(self) -> None:
        now = dt_util.utcnow().timestamp()
        self._store.async_delay_save(lambda: {"less": self._less, "seen": {
            k: [s for s in v if now - s[0] < LEARN_DAYS] for k, v in self._seen.items()
            if any(now - s[0] < LEARN_DAYS for s in v)}, "told": {
            k: v for k, v in self._told.items()
            if v["ended"] is None or now - v["ended"] < KEEP}}, 5)
