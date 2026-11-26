"""Works out better hours from daily summaries. Suggests; the owner decides (F4).

The summaries come from the server's history, the one record of what happened: the quiet
stretch of each night and how long doors stayed open. Code checks them and does all the
arithmetic; no model. A suggestion changes nothing until the owner approves it. Off by default.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable
from statistics import median
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LEARN,
    CONF_WEEKEND_FROM,
    CONF_WEEKEND_TO,
    DEFAULT_NIGHT_FROM,
    DEFAULT_NIGHT_TO,
    DEFAULT_OPEN_MINUTES,
    DOMAIN,
)
from .feed import Feed

START = datetime.time(18)  # a night is looked at from 6 PM until noon
STEP = 5  # minutes
STEPS = 18 * 60 // STEP
MIN_QUIET, MAX_QUIET = 180, 720
KEEP_DAYS, MIN_DAYS, MIN_WEEKEND, MIN_OPENS = 60, 14, 5, 20
MIN_CHANGE = 30  # minutes
EVERY = datetime.timedelta(days=30)
EXPIRES = datetime.timedelta(days=30)
ISSUE = "suggestion"
MAX_OPENS = 200


def clock(minutes: float) -> str:
    """Minutes after 6 PM, to the nearest quarter hour, as a time."""
    total = (START.hour * 60 + round(minutes / 15) * 15) % 1440
    return f"{total // 60:02}:{total % 60:02}:00"


def after_start(text: str) -> int:
    value = dt_util.parse_time(text) or START
    return (value.hour * 60 + value.minute - START.hour * 60) % 1440


def spoken(text: str) -> str:
    value = dt_util.parse_time(text) or START
    return f"{value.hour % 12 or 12}:{value.minute:02} {'AM' if value.hour < 12 else 'PM'}"


def quiet_gap(active: list[int]) -> list[int] | None:
    """The longest stretch with nothing happening, between two things that did."""
    points = sorted(set(active))
    gaps = [((b - a) * STEP, a, b) for a, b in zip(points, points[1:], strict=False)]
    if not gaps:
        return None
    size, start, end = max(gaps)
    # Too short is not a night; too long is an empty home or a missed evening.
    return [start * STEP, end * STEP] if MIN_QUIET <= size <= MAX_QUIET else None


def weekend(night: str) -> bool:
    return datetime.date.fromisoformat(night).weekday() in (4, 5)  # Friday and Saturday nights


def suggest(learned: dict[str, Any], options: dict[str, Any]) -> dict[str, Any] | None:
    """The one change most worth making, with what supports it."""
    never = learned["never"]
    nights = learned["nights"]
    days = [v for k, v in nights.items() if not weekend(k)]
    ends = [v for k, v in nights.items() if weekend(k)]
    current = (options.get("night_from", DEFAULT_NIGHT_FROM),
               options.get("night_to", DEFAULT_NIGHT_TO))
    ends_now = (options.get(CONF_WEEKEND_FROM) or current[0],
                options.get(CONF_WEEKEND_TO) or current[1])
    found = []
    for key, values, least, now, names, label in (
            ("night", days, MIN_DAYS - 4, current, ("night_from", "night_to"),
             "Sunday to Thursday"),
            ("weekend", ends, MIN_WEEKEND, ends_now, (CONF_WEEKEND_FROM, CONF_WEEKEND_TO),
             "Friday and Saturday")):
        if key in never or len(nights) < MIN_DAYS or len(values) < least:
            continue
        times = [clock(median(v[i] for v in values)) for i in (0, 1)]
        change = max(abs(after_start(a) - after_start(b)) for a, b in zip(times, now, strict=True))
        if change >= MIN_CHANGE:
            found.append((change, {
                "key": key, "set": dict(zip(names, times, strict=True)),
                "text": f"On {len(values)} nights, {label}, your home was usually quiet from "
                        f"{spoken(times[0])} to {spoken(times[1])}. Change those nights from "
                        f"{spoken(now[0])}-{spoken(now[1])} to match?"}))
    opens = sorted(m for day in learned["opens"].values() for m in day)
    if "open" not in never and len(learned["opens"]) >= MIN_DAYS and len(opens) >= MIN_OPENS:
        minutes = min(60, max(5, -(-opens[len(opens) * 9 // 10] // 5) * 5))
        now_minutes = options.get("open_minutes", DEFAULT_OPEN_MINUTES)
        if abs(minutes - now_minutes) >= 10:
            found.append((0, {
                "key": "open", "set": {"open_minutes": minutes},
                "text": f"Of {len(opens)} openings on {len(learned['opens'])} days, 9 in 10 were "
                        f"over within {minutes} minutes. Change left open from {now_minutes} to "
                        f"{minutes} minutes?"}))
    return max(found, key=lambda f: f[0])[1] if found else None


def empty() -> dict[str, Any]:
    return {"nights": {}, "opens": {}, "never": [], "last": None, "suggestion": None,
            "undo": None, "since": None}


def _day(text: object, today: datetime.date) -> bool:
    if not isinstance(text, str) or len(text) != 10:
        return False
    try:
        day = datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return today - datetime.timedelta(days=KEEP_DAYS) <= day < today


def checked(nights: object, opens: object, today: datetime.date) -> tuple[dict, dict] | None:
    """The server's summaries, only if every part is what a summary can be."""
    if not (isinstance(nights, dict) and isinstance(opens, dict)
            and len(nights) <= KEEP_DAYS + 1 and len(opens) <= KEEP_DAYS + 1):
        return None
    for day, gap in nights.items():
        if not (_day(day, today) and isinstance(gap, list)
                and len(gap) == 2 and all(type(v) is int for v in gap)
                and 0 <= gap[0] < gap[1] <= STEPS * STEP
                and MIN_QUIET <= gap[1] - gap[0] <= MAX_QUIET):
            return None
    for day, minutes in opens.items():
        if not (_day(day, today) and isinstance(minutes, list) and len(minutes) <= MAX_OPENS
                and all(type(v) is int and 1 <= v <= 1440 for v in minutes)):
            return None
    return nights, opens


class Learner:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, feed: Feed) -> None:
        self._hass, self._entry, self._feed = hass, entry, feed
        self._on: bool = entry.options.get(CONF_LEARN, False)
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.learned")
        self.data = empty()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        # Notes kept here before the server's history was the one record are dropped.
        self.data = {**empty(), **{k: v for k, v in saved.items() if k in empty()}}
        if not self._on:
            return lambda: None
        self._show()
        stop_tick = async_track_time_interval(self._hass, self._tick, datetime.timedelta(hours=1))

        @callback
        def stop() -> None:
            stop_tick()
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE)
        return stop

    # --- the server's summaries ---

    @callback
    def received(self, nights: object, opens: object) -> bool:
        """Summaries worked out from history. Refused unless each one is well formed."""
        if not self._on:
            return False
        found = checked(nights, opens, dt_util.now().date())
        if found is None:
            return False
        since = self.data["since"] or ""
        self.data["nights"] = {d: v for d, v in found[0].items() if d >= since}
        self.data["opens"] = {d: v for d, v in found[1].items() if d >= since}
        self._consider()
        self._store.async_delay_save(lambda: self.data, 10)
        return True

    async def _tick(self, now: datetime.datetime) -> None:
        self.tick()

    @callback
    def tick(self) -> None:
        self._consider()
        self._store.async_delay_save(lambda: self.data, 10)

    # --- suggesting ---

    @callback
    def _consider(self) -> None:
        now = dt_util.utcnow()
        if (held := self.data["suggestion"]) is not None:
            if now - dt_util.utc_from_timestamp(held["at"]) > EXPIRES:
                self._clear()
            return
        last = self.data["last"]
        if last is not None and now - dt_util.utc_from_timestamp(last) < EVERY:
            return
        if found := suggest(self.data, dict(self._entry.options)):
            self.data["last"] = now.timestamp()
            self.data["suggestion"] = {**found, "at": now.timestamp()}
            self._feed.note("learning:suggestion", "open", found["text"], "learning")
            self._show()

    @callback
    def _show(self) -> None:
        if held := self.data["suggestion"]:
            ir.async_create_issue(
                self._hass, DOMAIN, ISSUE, is_fixable=True, severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE, translation_placeholders={"text": held["text"]},
                data={"entry_id": self._entry.entry_id, "text": held["text"]})

    @callback
    def _clear(self) -> None:
        self.data["suggestion"] = None
        self._feed.note("learning:suggestion", "closed", "Answered or expired", "learning")
        ir.async_delete_issue(self._hass, DOMAIN, ISSUE)
        self._store.async_delay_save(lambda: self.data, 0)

    # --- the owner's answer ---

    @callback
    def approve(self) -> None:
        held = self.data["suggestion"]
        if held is None:
            return
        options = dict(self._entry.options)
        self.data["undo"] = {k: options.get(k) for k in held["set"]}
        self._clear()
        self._hass.config_entries.async_update_entry(
            self._entry, options={**options, **held["set"]})
        self._hass.config_entries.async_schedule_reload(self._entry.entry_id)

    @callback
    def later(self) -> None:
        self._clear()

    @callback
    def never(self) -> None:
        if held := self.data["suggestion"]:
            self.data["never"].append(held["key"])
        self._clear()

    @callback
    def undone(self, options: dict[str, Any]) -> dict[str, Any]:
        """The options as they were before the last approved change."""
        for key, value in (self.data["undo"] or {}).items():
            options.pop(key, None)
            if value is not None:
                options[key] = value
        self.data["undo"] = None
        self._store.async_delay_save(lambda: self.data, 0)
        return options

    async def forget(self) -> None:
        """Start again: nights before today are not counted. History itself is kept."""
        self.data = {**empty(), "since": dt_util.now().date().isoformat()}
        ir.async_delete_issue(self._hass, DOMAIN, ISSUE)
        await self._store.async_save(self.data)
