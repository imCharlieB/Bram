"""Watchdog rules for locks and doors. Fixed text, no model, no server, all off by default."""
from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable, Iterator
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

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
from .home_alerts import GROUP_MAX, GROUP_MIN, within
from .notifier import notify
from .shared import shared
from .teller import EACH_TIME, Teller

SETTLE = 120  # a door in use, or someone just leaving, is not news
OFFLINE_AFTER = 300
DAILY = 20
DAY = 86400
MUTE = "BRAM_QUIET_"
UNKNOWN = ("unavailable", "unknown", "")
# These matter at night, so they do not wait for quiet hours to end.
URGENT = ("night", "away")


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
        self._on = {r for r in ("night", "away", "left_open", "offline") if options.get(r)}
        self._entities: list[str] = shared(hass, options)
        self._phones: list[str] = options.get(CONF_PHONES, [])
        self._quiet = (options.get(CONF_QUIET_FROM), options.get(CONF_QUIET_TO))
        self._night = (options.get("night_from", DEFAULT_NIGHT_FROM),
                       options.get("night_to", DEFAULT_NIGHT_TO))
        self._weekend = (options.get(CONF_WEEKEND_FROM) or self._night[0],
                         options.get(CONF_WEEKEND_TO) or self._night[1])
        self._open_types = {t for t in OPEN_TYPES if options.get(t, True)}
        self._open_seconds = options.get("open_minutes", DEFAULT_OPEN_MINUTES) * 60
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.rules")
        self._kinds: dict[str, str] = {}
        self._since: dict[str, float] = {}
        self._told: set[str] = set()
        self._muted: list[str] = []
        self._sent: list[float] = []
        self._lock = asyncio.Lock()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._kinds = saved.get("kinds", {})
        self._muted = saved.get("muted", [])
        self._told = set(saved.get("told", []))
        stops = [
            async_track_state_change_event(self._hass, self._entities, self._changed),
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

    def _everyone_away(self) -> bool:
        """True only if every shared person is known to be away (B2)."""
        people = [e for e in self._entities if e.startswith("person.")]
        states = [self._hass.states.get(e) for e in people]
        return bool(people) and all(
            s is not None and s.state not in (*UNKNOWN, "home") for s in states)

    def _facts(self) -> Iterator[tuple[str, str, float, str]]:
        """Rule, entity, seconds it must hold, and what to say."""
        night = self.is_night()
        away = self._everyone_away()
        for entity_id in self._entities:
            state = self._hass.states.get(entity_id)
            kind = self._kind(entity_id, state)
            if kind not in ("lock", "opening"):
                continue
            value = state.state if state is not None else "unavailable"
            name = state.name if state is not None else entity_id
            name = " ".join("".join(c if c.isprintable() else " " for c in name).split())[:60]
            if value in UNKNOWN:
                yield "offline", entity_id, OFFLINE_AFTER, f"I can't see {name}. It is offline."
            elif kind == "lock" and value in ("unlocked", "open"):
                if night:
                    yield "night", entity_id, SETTLE, f"{name} is unlocked, and it's night."
                if away:
                    yield "away", entity_id, SETTLE, (
                        f"{name} is unlocked, and everyone I track is away.")
            elif kind == "opening" and value in ("on", "open"):
                minutes = self._open_seconds // 60
                if self._open_type(state) in self._open_types:
                    yield "left_open", entity_id, self._open_seconds, (
                        f"{name} has been open for {minutes} minutes.")
                if away:
                    yield "away", entity_id, SETTLE, (
                        f"{name} is open, and everyone I track is away.")

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
            routine = [d for d in due if not d[0]]
            # Several routine messages at once become one. Urgent ones stay on their own.
            alone = [d for d in due if d[0]] + (routine if len(routine) < GROUP_MIN else [])
            batches = [[d] for d in alone]
            if len(routine) >= GROUP_MIN:
                batches += [routine[i:i + GROUP_MAX] for i in range(0, len(routine), GROUP_MAX)]
            for batch in batches:
                if len(self._sent) >= DAILY:
                    break
                key = batch[0][1]
                actions = [{"action": MUTE + key, "title": "Stop these"},
                           *([] if batch[0][0] else self._teller.actions(f"rule:{key}"))
                           ] if len(batch) == 1 else []
                if await notify(self._hass, self._phones, "BRAM watch",
                                "\n".join(text for _, _, text in batch), f"bram_{key}",
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

    def _watching(self, facts: dict, now: float, quiet: bool) -> None:
        """What is counting down, for BRAM's page. Holds are written down once, with why."""
        items = []
        names = {"left_open": "open", "night": "unlocked at night",
                 "away": "open while everyone is away", "offline": "offline"}
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
        state = self._hass.states.get(entity_id)
        name = state.name if state is not None else entity_id
        return " ".join("".join(c if c.isprintable() else " " for c in name).split())[:60]

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: {
            "kinds": self._kinds, "muted": self._muted, "told": sorted(self._told)}, 1)
