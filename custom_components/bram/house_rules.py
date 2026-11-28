"""Watchdog rules for locks, doors, motion, and comfort. Fixed text, no model, no server, all off
by default."""
from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable, Iterator
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_PHONES,
    CONF_QUIET_FROM,
    CONF_QUIET_TO,
    CONF_WEEKEND_FROM,
    CONF_WEEKEND_TO,
    DEFAULT_NIGHT_FROM,
    DEFAULT_NIGHT_TO,
    DEFAULT_OPEN_MINUTES,
    DOMAIN,
    OPEN_TYPES,
)
from .feed import kind_of
from .home_alerts import GROUP_MAX, within
from .names import name_of
from .notifier import notify
from .shared import shared
from .teller import EACH_TIME, Teller

SETTLE = 120  # a door in use, or someone just leaving, is not news
OFFLINE_AFTER = 300
DAILY = 20
DAY = 86400
MUTE = "BRAM_QUIET_"
UNKNOWN = ("unavailable", "unknown", "")
RULES = ("night", "away", "left_open", "offline", "open_night", "open_climate", "motion_away",
         "too_hot", "too_cold", "freezing", "humid", "check")
# These matter at night, so they do not wait for quiet hours to end.
URGENT = ("night", "away", "open_night", "motion_away", "freezing", "check")
CHECK_FOR = 45  # minutes after its hour that a nightly check still tells
COMFORT_WAIT = 1800  # a room must stay too hot or too cold this long
FREEZE_WAIT = 900
RUNNING = ("heating", "cooling")
UNITS = {"°F": UnitOfTemperature.FAHRENHEIT, "°C": UnitOfTemperature.CELSIUS,
         "F": UnitOfTemperature.FAHRENHEIT, "C": UnitOfTemperature.CELSIUS}
# Limits in the home's own unit when the owner has not set them.
LIMITS = {UnitOfTemperature.FAHRENHEIT: {"hot_above": 85, "cold_below": 55, "freeze_below": 38},
          UnitOfTemperature.CELSIUS: {"hot_above": 29, "cold_below": 13, "freeze_below": 3}}
HUMID_ABOVE = 70
# Routine messages that come up within the same moment go out as one. Important ones (night,
# away) go at once; safety alerts are not here and never wait (C3).
GATHER = 20  # seconds
# Several of the same at once, in one sentence, such as two windows open when everyone leaves.
TOGETHER = {
    "away": "Everyone I track is away, and these are open or unlocked: {names}.",
    "night": "It's night, and these are unlocked: {names}.",
    "open_night": "It's night, and these are open: {names}.",
    "left_open": "These have been open for {minutes} minutes: {names}.",
    "offline": "I can't see these. They are offline: {names}.",
    "motion_away": "Motion while everyone I track is away: {names}.",
}


def limits(unit: str, options: dict[str, Any]) -> dict[str, float]:
    """The comfort limits in the home's unit, with defaults for any not set."""
    base = LIMITS.get(unit, LIMITS[UnitOfTemperature.CELSIUS])
    return {**{k: float(options.get(k, v)) for k, v in base.items()},
            "humid_above": float(options.get("humid_above", HUMID_ABOVE))}


class HouseRules:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 note: Callable[..., None] = lambda *a: None,
                 teller: Teller | None = None,
                 report: Callable[[list[dict]], bool] = lambda items: True) -> None:
        self._note = note
        self._report = report
        self._held: set[str] = set()
        self._last_report: list[dict] | None = None
        self._teller = teller or Teller(hass, entry)
        self._noted: set[str] = set()
        self._hass = hass
        options = entry.options
        self._on = {r for r in RULES if options.get(r)}
        # Nightly checks the owner approved from what BRAM learned.
        self._checks: dict[str, int] = {c["entity_id"]: c["hour"] for c in options.get(
            "checks", []) if isinstance(c, dict) and isinstance(c.get("hour"), int)}
        if self._checks:
            self._on.add("check")
        self._unit = hass.config.units.temperature_unit
        self._limits = limits(self._unit, dict(options))
        self._skip: set[str] = set(options.get("comfort_skip", []))
        self._moved: set[str] = set()
        self._entities: list[str] = shared(hass, options)
        self._phones: list[str] = options.get(CONF_PHONES, [])
        self._quiet = (options.get(CONF_QUIET_FROM), options.get(CONF_QUIET_TO))
        self._night = (options.get("night_from", DEFAULT_NIGHT_FROM),
                       options.get("night_to", DEFAULT_NIGHT_TO))
        self._weekend = (options.get(CONF_WEEKEND_FROM) or self._night[0],
                         options.get(CONF_WEEKEND_TO) or self._night[1])
        # Helpers or sensors that are on while someone is asleep, such as a bedtime switch.
        self._asleep: list[str] = list(options.get("asleep", []))
        self._open_types = {t for t in OPEN_TYPES if options.get(t, True)}
        self._open_seconds = options.get("open_minutes", DEFAULT_OPEN_MINUTES) * 60
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.rules")
        self._kinds: dict[str, str] = {}
        self._since: dict[str, float] = {}
        self._told: set[str] = set()
        self._muted: list[str] = []
        self._sent: list[float] = []
        self._lock = asyncio.Lock()
        self._due_since: dict[str, float] = {}

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._kinds = saved.get("kinds", {})
        self._muted = saved.get("muted", [])
        self._told = set(saved.get("told", []))
        stops = [
            async_track_state_change_event(self._hass, [*self._entities, *self._asleep],
                                           self._changed),
            self._hass.bus.async_listen("mobile_app_notification_action", self.answered),
            async_track_time_interval(self._hass, self._tick, datetime.timedelta(seconds=30)),
        ]

        @callback
        def stop() -> None:
            for item in stops:
                item()
        return stop

    @callback
    def _changed(self, event: Event) -> None:
        self._hass.async_create_task(self.run(), "bram rules")

    async def _tick(self, now: datetime.datetime) -> None:
        await self.run()

    @callback
    def answered(self, event: Event) -> None:
        action = event.data.get("action")
        if isinstance(action, str) and action.startswith(MUTE):
            key = action[len(MUTE):]
            rule, _, entity_id = key.partition(":")
            if rule in self._on and entity_id in self._entities and key not in self._muted:
                self._muted.append(key)
                self._note(f"rules:{key}", "stopped", "Stopped from a phone", "rules", "low")
                self._save()

    @callback
    def allow_all(self) -> None:
        self._muted = []
        self._save()

    # --- what is true now ---

    def _kind(self, entity_id: str, state: State | None) -> str | None:
        if state is not None:
            kind = kind_of(entity_id, state.attributes.get("device_class"))
            known = self._kinds.get(entity_id)
            # A sensor that briefly loses its type must stay what it was known to be.
            if kind and kind != known and not (kind == "other" and known):
                self._kinds[entity_id] = kind
                self._save()
        return self._kinds.get(entity_id)

    def is_night(self) -> bool:
        """Night hours, and also while anyone's asleep helper is on. A helper that is
        unavailable changes nothing, so the hours still count (B2)."""
        if any((s := self._hass.states.get(e)) is not None and s.state == "on"
               for e in self._asleep):
            return True
        now = dt_util.now()
        # Friday and Saturday nights run into the next morning.
        weekend = (now - datetime.timedelta(hours=12)).weekday() in (4, 5)
        return within(self._weekend if weekend else self._night, now.time())

    @staticmethod
    def _open_type(state: State | None) -> str:
        device_class = state.attributes.get("device_class") if state is not None else None
        if device_class == "window":
            return "open_windows"
        if device_class in ("garage", "garage_door", "gate"):
            return "open_garages"
        return "open_doors"

    def everyone_away(self) -> bool:
        """True only if every shared person is known to be away (B2)."""
        people = [e for e in self._entities if e.startswith("person.")]
        states = [self._hass.states.get(e) for e in people]
        return bool(people) and all(
            s is not None and s.state not in (*UNKNOWN, "home") for s in states)

    def _running(self) -> str | None:
        """A shared thermostat heating or cooling now, as words, or None."""
        for entity_id in self._entities:
            state = self._hass.states.get(entity_id)
            if (entity_id.startswith("climate.") and state is not None
                    and state.attributes.get("hvac_action") in RUNNING):
                return f"{self._name(entity_id)} is {state.attributes['hvac_action']}"
        return None

    def _temperature(self, entity_id: str, state: State) -> float | None:
        """A room's temperature in the home's unit, or None if it is not known (B2)."""
        if entity_id.startswith("climate."):
            value, unit = state.attributes.get("current_temperature"), self._unit
        else:
            value, unit = state.state, UNITS.get(
                str(state.attributes.get("unit_of_measurement", "")), "")
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if unit not in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS):
            return None
        return TemperatureConverter.convert(number, unit, self._unit)

    def _facts(self) -> Iterator[tuple[str, str, float, str]]:
        """Rule, entity, seconds it must hold, and what to say."""
        night = self.is_night()
        away = self.everyone_away()
        running = self._running() if "open_climate" in self._on else None
        if not away:
            self._moved.clear()
        unit = "\u00b0F" if self._unit == UnitOfTemperature.FAHRENHEIT else "\u00b0C"
        clock = dt_util.now()
        for entity_id, hour in self._checks.items():
            state = self._hass.states.get(entity_id)
            if (state is not None and clock.hour == hour and clock.minute < CHECK_FOR
                    and state.state in ("on", "open", "unlocked")):
                said = "unlocked" if state.state == "unlocked" else "open"
                at = datetime.time(hour).strftime("%I %p").lstrip("0")
                yield "check", entity_id, 0, (f"{self._name(entity_id)} is still {said}. "
                                              f"Your nightly check at {at}.")
        for entity_id in self._entities:
            state = self._hass.states.get(entity_id)
            kind = self._kind(entity_id, state)
            value = state.state if state is not None else "unavailable"
            name = self._name(entity_id)
            if kind in ("lock", "opening") and value in UNKNOWN:
                yield "offline", entity_id, OFFLINE_AFTER, f"I can't see {name}. It is offline."
            elif kind == "lock" and value in ("unlocked", "open"):
                if night:
                    yield "night", entity_id, SETTLE, f"{name} is unlocked, and it's night."
                if away:
                    yield "away", entity_id, SETTLE, (
                        f"{name} is unlocked, and everyone I track is away.")
            elif kind == "opening" and value in ("on", "open"):
                minutes = self._open_seconds // 60
                chosen = self._open_type(state) in self._open_types
                if chosen:
                    yield "left_open", entity_id, self._open_seconds, (
                        f"{name} has been open for {minutes} minutes.")
                if away:
                    yield "away", entity_id, SETTLE, (
                        f"{name} is open, and everyone I track is away.")
                if night and chosen:
                    yield "open_night", entity_id, SETTLE, f"{name} is open, and it's night."
                if running:
                    yield "open_climate", entity_id, self._open_seconds, (
                        f"{name} has been open for {minutes} minutes while {running}.")
            elif kind == "motion":
                # Once seen while everyone is away, it stays news until someone is home.
                if away and value == "on":
                    self._moved.add(entity_id)
                if entity_id in self._moved:
                    yield "motion_away", entity_id, 0, (
                        f"Motion at {name} while everyone I track is away.")
            elif (kind in ("temperature", "climate") and state is not None
                  and entity_id not in self._skip):
                degrees = self._temperature(entity_id, state)
                if degrees is None:
                    continue
                shown = f"{round(degrees)}{unit}"
                if degrees < self._limits["freeze_below"]:
                    yield "freezing", entity_id, FREEZE_WAIT, (
                        f"{name} is {shown}, near freezing. Pipes may freeze.")
                elif degrees < self._limits["cold_below"]:
                    yield "too_cold", entity_id, COMFORT_WAIT, (
                        f"{name} is {shown}, below your "
                        f"{round(self._limits['cold_below'])}{unit} limit.")
                elif degrees > self._limits["hot_above"]:
                    yield "too_hot", entity_id, COMFORT_WAIT, (
                        f"{name} is {shown}, above your "
                        f"{round(self._limits['hot_above'])}{unit} limit.")
            elif kind == "humidity" and state is not None and entity_id not in self._skip:
                try:
                    percent = float(value)
                except ValueError:
                    continue
                if percent > self._limits["humid_above"]:
                    yield "humid", entity_id, COMFORT_WAIT, (
                        f"{name} is {round(percent)}% humid, above your "
                        f"{round(self._limits['humid_above'])}% limit.")

    # --- telling ---

    async def run(self) -> None:
        async with self._lock:
            now = dt_util.utcnow().timestamp()
            facts = {f"{rule}:{entity}": (rule, wait, text)
                     for rule, entity, wait, text in self._facts() if rule in self._on}
            self._since = {k: self._since.get(k, now) for k in facts}
            if not self._told <= facts.keys():
                self._told &= facts.keys()  # over, so the next time is news again
                self._save()
            for key in self._noted - facts.keys():
                self._note(f"rules:{key}", "closed", "Over", "rules", "low")
                self._teller.ended(f"rule:{key}")
            self._noted &= facts.keys()
            for key, (rule, wait, text) in facts.items():
                if now - self._since[key] >= wait:
                    self._noted.add(key)
                    self._note(f"rules:{key}", "open", text, "rules",
                               "medium" if rule in URGENT else "low")
            quiet = within(self._quiet, dt_util.now().time())
            self._sent = [t for t in self._sent if now - t < DAY]
            due = []
            for key, (rule, wait, text) in facts.items():
                if (key in self._told or key in self._muted or now - self._since[key] < wait
                        or (quiet and rule not in URGENT) or not self._phones):
                    continue
                if rule not in URGENT and not self._teller.allow(
                        f"rule:{key}", text, EACH_TIME, finding=f"rules:{key}", source="rules"):
                    self._told.add(key)  # held back: one event, listed in Findings
                    continue
                due.append((rule in URGENT, key, text))
            self._watching(facts, now, quiet)
            due = self._gathered(due, now)
            routine = [d for d in due if not d[0]]
            # What came due together is one message: the urgent ones in one, the routine
            # ones in another, each in one sentence where they are the same kind.
            urgent = [d for d in due if d[0]]
            batches = [part[i:i + GROUP_MAX] for part in (urgent, routine)
                       for i in range(0, len(part), GROUP_MAX)]
            for batch in batches:
                if len(self._sent) >= DAILY:
                    break
                key = batch[0][1]
                actions = [{"action": MUTE + key, "title": "Stop these"},
                           *([] if batch[0][0] else self._teller.actions(f"rule:{key}"))
                           ] if len(batch) == 1 else []
                if await notify(self._hass, self._phones, "BRAM watch",
                                self._together(batch), f"bram_{key}",
                                safety=False, actions=actions,
                                finding=f"rules:{key}" if len(batch) == 1 else None):
                    self._told.update(k for _, k, _ in batch)
                    if actions:
                        self._teller.offer(f"rules:{key}", actions, "rules")
                    for urgent, k, text in batch:
                        self._note(f"rules:{k}", "sent", f"Phone: {text}", "rules", "low")
                        if not urgent:
                            self._teller.told(f"rule:{k}", text)
                    self._sent.append(now)
                    self._save()

    def _gathered(self, due: list[tuple[bool, str, str]],
                  now: float) -> list[tuple[bool, str, str]]:
        """Hold routine messages for a moment, so whatever comes up with them is one message.
        Important ones go at once."""
        routine = {k for urgent, k, _ in due if not urgent}
        self._due_since = {k: self._due_since.get(k, now) for k in routine}
        if routine and now - min(self._due_since.values()) < GATHER:
            return [d for d in due if d[0]]
        return due

    def _together(self, batch: list[tuple[bool, str, str]]) -> str:
        """One message for a batch: one sentence when all are the same rule, else lines."""
        rules = {k.partition(":")[0] for _, k, _ in batch}
        rule = next(iter(rules))
        if len(batch) == 1 or len(rules) > 1 or rule not in TOGETHER:
            return "\n".join(text for _, _, text in batch)
        names = [self._name(k.partition(":")[2]) for _, k, _ in batch]
        listed = ", ".join(names[:-1]) + f", and {names[-1]}" if len(names) > 2 else \
            " and ".join(names)
        return TOGETHER[rule].format(names=listed, minutes=self._open_seconds // 60)

    def _watching(self, facts: dict, now: float, quiet: bool) -> None:
        """What is counting down, for BRAM's page. Holds are written down once, with why."""
        items = []
        names = {"left_open": "open", "night": "unlocked at night",
                 "away": "open while everyone is away", "offline": "offline",
                 "open_night": "open at night", "open_climate": "open while heating or cooling",
                 "motion_away": "moved while everyone is away", "too_hot": "too hot",
                 "too_cold": "too cold", "freezing": "near freezing", "humid": "humid",
                 "check": "still open at its nightly check"}
        for key, (rule, wait, _text) in facts.items():
            if key in self._muted:
                continue
            name = self._name(key.partition(":")[2])
            item = {"kind": "rule", "text": f"{name} {names[rule]}", "since": self._since[key]}
            if key in self._told:
                item["told"] = True
            else:
                item["due"] = self._since[key] + wait
                if quiet and rule not in URGENT and now >= item["due"] and key not in self._held:
                    self._held.add(key)
                    self._note(f"rules:{key}", "held", "Quiet hours: told when they end",
                               "rules", "low")
            items.append(item)
        self._held &= facts.keys()
        if "night" in self._on and not within(self._night, dt_util.now().time()):
            start = dt_util.parse_time(self._night[0])
            if start is not None:
                at = dt_util.now().replace(hour=start.hour, minute=start.minute, second=0,
                                           microsecond=0)
                if at <= dt_util.now():
                    at += datetime.timedelta(days=1)
                items.append({"kind": "night", "text": "Night starts: every lock is checked",
                              "due": at.timestamp()})
        if items != self._last_report and self._report(items):
            self._last_report = items

    def _name(self, entity_id: str) -> str:
        return name_of(self._hass, entity_id)

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: {
            "kinds": self._kinds, "muted": self._muted, "told": sorted(self._told)}, 1)
