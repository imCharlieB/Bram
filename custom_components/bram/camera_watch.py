"""Camera messages: Frigate's events, read by the BRAM Server, weighed against the rest of the
home here. Fixed rules and fixed words, no model; all off by default.

The picture in a message comes from the Frigate integration when it is installed. BRAM adds no
camera entities of its own.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PHONES, CONF_QUIET_FROM, CONF_QUIET_TO, DOMAIN
from .home_alerts import within
from .names import name_of
from .notifier import notify
from .teller import EACH_TIME, Teller

RULES = ("camera_away", "camera_door", "camera_night", "camera_stranger", "camera_package",
         "camera_car")
# A person while everyone is away, at an open or unlocked door, or at night does not wait.
URGENT = ("camera_away", "camera_door", "camera_night")
OPEN = {"on": "open", "open": "open", "opening": "opening", "unlocked": "unlocked",
        "unlocking": "unlocking"}
DEFAULT_REPEAT = 30  # minutes before the same thing on the same camera is news again
ACROSS = 120  # seconds: one person walking past several cameras is one message
TOO_OLD = 600  # an event this old when BRAM first hears of it is not news
STAY = 30  # seconds a car must stay: one driving past is gone sooner
DAILY = 30
DAY = 86400
MUTE = "BRAM_CAMERA_"
NOT_NEWS = "BRAM_CAMNEWS_"  # this event is not news: keep quiet about the same
PROXY = "/api/frigate/notifications/{id}/{kind}.jpg"


def picture(hass: HomeAssistant, event: dict) -> str | None:
    """Frigate's own picture for a phone message, if its integration is installed: the
    snapshot, or the thumbnail when snapshots are off in Frigate."""
    if "frigate" not in hass.config.components:
        return None
    return PROXY.format(id=quote(event["id"], safe=""),
                        kind="snapshot" if event["picture"] else "thumbnail")


def place(camera: str) -> str:
    """A camera's name as said in a sentence: RoofCamera and roof_camera are roof camera."""
    return " ".join(re.sub(r"([a-z])([A-Z])", r"\1 \2", camera).replace("_", " ")
                    .replace("-", " ").split()).lower()


class CameraWatch:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 away: Callable[[], bool], night: Callable[[], bool],
                 note: Callable[..., None] = lambda *a: None,
                 teller: Teller | None = None,
                 latest: Callable[[str], dict | None] = lambda camera: None,
                 not_news: Callable[[str, str], bool] = lambda camera, event_id: False) -> None:
        self._not_news = not_news  # tells the server, which keeps the list (BRAM's page)
        self._sent_events: dict[str, tuple[str, str, tuple[str, ...]]] = {}
        self._latest = latest  # the camera's newest event, to look again at a car
        self._waiting: list[Callable[[], None]] = []
        self._hass, self._away, self._night, self._note = hass, away, night, note
        self._teller = teller or Teller(hass, entry)
        options = entry.options
        self._on = {r for r in RULES if options.get(r)}
        # For each camera: the doors it looks at, the Frigate zones that count, and its rules.
        self._setup: dict[str, dict] = dict(options.get("camera_setup", {}))
        # Said on BRAM's page to be not news: (camera, kind of thing, zones).
        self.quiet: list[tuple[str, str, tuple[str, ...]]] = []
        self._repeat = int(options.get("camera_repeat", DEFAULT_REPEAT)) * 60
        self._phones: list[str] = options.get(CONF_PHONES, [])
        self._quiet = (options.get(CONF_QUIET_FROM), options.get(CONF_QUIET_TO))
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.cameras")
        self._seen: dict[str, float] = {}  # event id: when it was weighed
        self._last: dict[str, float] = {}  # camera:what, and what alone: when it was told
        self._muted: list[str] = []
        self._sent: list[float] = []

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._muted = saved.get("muted", [])
        self._last = saved.get("last", {})
        stop = self._hass.bus.async_listen("mobile_app_notification_action", self.answered)

        @callback
        def stop_all() -> None:
            stop()
            self.stop()
        return stop_all

    @callback
    def answered(self, event: Event) -> None:
        action = event.data.get("action")
        if isinstance(action, str) and action.startswith(NOT_NEWS):
            told = self._sent_events.pop(action[len(NOT_NEWS):], None)
            if told is not None and told not in self.quiet:
                self.quiet.append(told)  # at once here; the server keeps it for good
                self._not_news(told[0], action[len(NOT_NEWS):])
                self._note(f"cameras:{told[0]}:{told[1]}", "stopped",
                           "Not news, from a phone", "cameras", "low")
            return
        if isinstance(action, str) and action.startswith(MUTE):
            key = action[len(MUTE):]
            if key.count(":") == 1 and key not in self._muted:
                self._muted.append(key)
                self._note(f"cameras:{key}", "stopped", "Stopped from a phone", "cameras", "low")
                self._save()

    @callback
    def allow_all(self) -> None:
        self._muted = []
        self._save()

    def _open_door(self, doors: list[str]) -> str | None:
        """The first linked door or lock that is open or unlocked, in words. Unknown is never
        open (B2): it is not a reason to say a door is open."""
        for entity_id in doors:
            state = self._hass.states.get(entity_id)
            if state is not None and state.state in OPEN:
                return f"{name_of(self._hass, entity_id)} is {OPEN[state.state]}"
        return None

    def _rule(self, event: dict) -> tuple[str, str] | None:
        """Which rule this event meets, and what to say. The most urgent first."""
        setup = self._setup.get(event["camera"], {})
        on = self._on & set(setup.get("rules") or RULES)
        zones = set(setup.get("zones") or [])
        if zones and not zones & set(event["zones"]):
            return None  # not in a zone that counts, such as the sidewalk
        camera, label, who = place(event["camera"]), event["label"], event["who"]
        if label == "person":
            someone = who or "Someone"
            if "camera_away" in on and self._away():
                return "camera_away", f"{someone} at {camera}, and everyone I track is away."
            if "camera_door" in on and (door := self._open_door(setup.get("doors", []))):
                return "camera_door", f"{someone} at {camera}, and {door}."
            if "camera_night" in on and self._night():
                return "camera_night", f"{someone} at {camera}, and it's night."
            if "camera_stranger" in on and not who:
                return "camera_stranger", f"A person Frigate does not know at {camera}."
        if label == "package" and "camera_package" in on:
            return "camera_package", f"A package at {camera}."
        if label == "car" and "camera_car" in on:
            return "camera_car", f"A car at {camera}."
        return None

    async def weigh(self, camera: str, event: dict) -> None:
        """Called for each event the server passes on, new or changed."""
        now = dt_util.utcnow().timestamp()
        self._seen = {k: v for k, v in self._seen.items() if now - v < DAY}
        if event["id"] in self._seen or now - event["start"] > TOO_OLD:
            return
        if (camera, event["label"], tuple(sorted(event["zones"]))) in self.quiet:
            return  # the owner said this is not news
        found = self._rule({**event, "camera": camera})
        if found is None:
            return  # not yet: Frigate may still name the person or add a zone
        if found[0] == "camera_car":
            lasted = (event["end"] or now) - event["start"]
            if lasted < STAY:
                if event["end"] is None:  # still there: look again once it has stayed
                    self._later(camera, event["id"], STAY - lasted)
                return  # gone already: it drove past
        self._seen[event["id"]] = now
        rule, text = found
        what = "person" if event["label"] == "person" else event["label"]
        key, across = f"{camera}:{what}", f"*:{what}"
        if key in self._muted or not self._phones:
            return
        # The same thing on the same camera, or the same moment on several cameras, once.
        if now - self._last.get(key, 0) < self._repeat or now - self._last.get(across, 0) < ACROSS:
            return
        if within(self._quiet, dt_util.now().time()) and rule not in URGENT:
            self._note(f"cameras:{key}", "held", f"Quiet hours: {text}", "cameras", "low")
            return
        if rule not in URGENT and not self._teller.allow(
                f"camera:{key}", text, EACH_TIME, finding=f"cameras:{key}", source="cameras"):
            return
        self._sent = [t for t in self._sent if now - t < DAY]
        if len(self._sent) >= DAILY:
            return
        if event["zones"]:
            text += f" In {', '.join(z.replace('_', ' ') for z in event['zones'])}."
        if event.get("description"):  # the model's words, if ready; it never holds this (C6)
            text += f" {event['description']}"
        actions = [{"action": MUTE + key, "title": "Stop these"},
                   *([] if rule in URGENT else self._teller.actions(f"camera:{key}"))]
        self._note(f"cameras:{key}", "open", text, "cameras",
                   "medium" if rule in URGENT else "low")
        # Not news, on the phone too. Not offered on BRAM's page: it has its own.
        buttons = [*actions, {"action": NOT_NEWS + event["id"], "title": "Not news"}]
        if await notify(self._hass, self._phones, "BRAM camera", text, f"bram_camera_{what}",
                        safety=False, actions=buttons, finding=f"cameras:{key}",
                        image=picture(self._hass, event)):
            self._last[key] = self._last[across] = now
            self._sent_events[event["id"]] = (camera, event["label"],
                                              tuple(sorted(event["zones"])))
            while len(self._sent_events) > 100:
                self._sent_events.pop(next(iter(self._sent_events)))
            self._sent.append(now)
            self._note(f"cameras:{key}", "sent", f"Phone: {text}", "cameras", "low")
            self._teller.offer(f"cameras:{key}", actions, "cameras")
            if rule not in URGENT:
                self._teller.told(f"camera:{key}", text)
            self._save()
        else:
            self._note(f"cameras:{key}", "not sent", "No phone accepted it", "cameras", "low")
        self._note(f"cameras:{key}", "closed", "Over", "cameras", "low")

    @callback
    def _later(self, camera: str, event_id: str, wait: float) -> None:
        @callback
        def again() -> None:
            latest = self._latest(camera)
            if latest is not None and latest["id"] == event_id:
                self._hass.async_create_task(self.weigh(camera, latest), "bram camera")

        # A plain timer on the event loop; nothing here can call a service (A1).
        self._waiting.append(self._hass.loop.call_later(wait + 1, again).cancel)

    @callback
    def stop(self) -> None:
        for cancel in self._waiting:
            cancel()
        self._waiting.clear()

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: {"muted": self._muted, "last": self._last}, 1)
