"""Works out better hours from daily summaries. Suggests; the owner decides (F4).

Code does all the arithmetic. Nothing here uses a model or the server. Off by default.
"""
from __future__ import annotations

import datetime
import json
from collections.abc import Callable
from statistics import median
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENTITIES,
    CONF_LEARN,
    CONF_WEEKEND_FROM,
    CONF_WEEKEND_TO,
    DEFAULT_NIGHT_FROM,
    DEFAULT_NIGHT_TO,
    DEFAULT_OPEN_MINUTES,
    DOMAIN,
)
from .feed import Feed, kind_of

START = datetime.time(18)  # a night is looked at from 6 PM until noon
STEP = 5  # minutes
STEPS = 18 * 60 // STEP
MIN_SEEN = STEPS * 9 // 10  # otherwise the night was not watched well enough
MIN_QUIET, MAX_QUIET = 180, 720
KEEP_DAYS, MIN_DAYS, MIN_WEEKEND, MIN_OPENS = 60, 14, 5, 20
MIN_CHANGE = 30  # minutes
EVERY = datetime.timedelta(days=30)
EXPIRES = datetime.timedelta(days=30)
ISSUE = "suggestion"


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
    return {"nights": {}, "opens": {}, "pending": {}, "never": [], "last": None,
            "suggestion": None, "undo": None}


class Learner:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, feed: Feed) -> None:
        self._hass, self._entry, self._feed = hass, entry, feed
        self._on: bool = entry.options.get(CONF_LEARN, False)
        self._entities: list[str] = entry.options.get(CONF_ENTITIES, [])
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.learned")
        self.data = empty()
        self._opened: dict[str, datetime.datetime] = {}

    async def start(self) -> Callable[[], None]:
        self.data = {**empty(), **(await self._store.async_load() or {})}
        if not self._on:
            return lambda: None
        self._show()
        stops = [
            async_track_state_change_event(self._hass, self._entities, self._changed),
            async_track_time_interval(self._hass, self._tick, datetime.timedelta(minutes=STEP)),
        ]

        @callback
        def stop() -> None:
            for item in stops:
                item()
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE)
        return stop

    # --- noticing ---

    def _now(self) -> tuple[str, int] | None:
        """Which night it is, and how far in. None in the afternoon."""
        now = dt_util.now()
        day = (now - datetime.timedelta(hours=12)).date()
        if 12 <= now.hour < START.hour:
            return None
        minutes = ((now.hour - START.hour) % 24) * 60 + now.minute
        return day.isoformat(), minutes // STEP

    @callback
    def _changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id, new, old = (event.data[k] for k in ("entity_id", "new_state", "old_state"))
        if new is None or old is None or new.state == old.state:
            return
        kind = self._feed.kind(entity_id) or kind_of(
            entity_id, new.attributes.get("device_class"))
        known = {"on", "off", "open", "closed", "locked", "unlocked"}
        if kind not in ("motion", "opening", "lock") or new.state not in known:
            self._opened.pop(entity_id, None)
            return
        if old.state in known and not (kind == "motion" and new.state == "off"):
            self._active()
        if kind != "opening":
            return
        now = dt_util.utcnow()
        if new.state in ("on", "open") and old.state in known:
            self._opened[entity_id] = now
        elif since := self._opened.pop(entity_id, None):
            day = dt_util.now().date().isoformat()
            day_list = self.data["opens"].setdefault(day, [])
            if len(day_list) < 200:
                day_list.append(max(1, round((now - since).total_seconds() / 60)))

    def _night(self, day: str) -> dict[str, Any]:
        if self.data["pending"].get("night") != day:
            self._finish()
            self.data["pending"] = {"night": day, "active": [], "seen": 0}
        return self.data["pending"]

    @callback
    def _active(self) -> None:
        if place := self._now():
            active = self._night(place[0])["active"]
            if place[1] not in active:
                active.append(place[1])

    async def _tick(self, now: datetime.datetime) -> None:
        self.tick()

    @callback
    def tick(self) -> None:
        if place := self._now():
            self._night(place[0])["seen"] += 1
        else:
            self._finish()
            self._consider()
        self._store.async_delay_save(lambda: self.data, 10)

    @callback
    def _finish(self) -> None:
        """Keep one line about the night, and forget the rest."""
        pending, self.data["pending"] = self.data["pending"], {}
        if pending.get("seen", 0) >= MIN_SEEN and (gap := quiet_gap(pending["active"])):
            self.data["nights"][pending["night"]] = gap
            self._keep("night", pending["night"], gap)
        yesterday = (dt_util.now().date() - datetime.timedelta(days=1)).isoformat()
        if pending and yesterday in self.data["opens"]:
            self._keep("open", yesterday, self.data["opens"][yesterday])
        oldest = (dt_util.now().date() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
        for key in ("nights", "opens"):
            self.data[key] = {d: v for d, v in self.data[key].items() if d >= oldest}

    @callback
    def _keep(self, kind: str, day: str, value: list[int]) -> None:
        """A copy for the server's database."""
        self._feed.note(f"{kind}:{day}", "learned", json.dumps(value), "learning")

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
        self.data = empty()
        self._opened = {}
        self._feed.note("learned", "forgot", "Forgotten", "learning")
        ir.async_delete_issue(self._hass, DOMAIN, ISSUE)
        await self._store.async_remove()
