"""Camera messages: Frigate's events, read by the BRAM Server, weighed against the rest of the
home here. Fixed rules and fixed words, no model; all off by default.

The picture in a message comes from the Frigate integration when it is installed. BRAM adds no
camera entities of its own.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PHONES, CONF_QUIET_FROM, CONF_QUIET_TO, DOMAIN
from .home_alerts import within
from .notifier import notify
from .teller import EACH_TIME, Teller

RULES = ("camera_away", "camera_night", "camera_package", "camera_stranger")
# A person while everyone is away or at night does not wait for quiet hours.
URGENT = ("camera_away", "camera_night")
DEFAULT_REPEAT = 30  # minutes before the same thing on the same camera is news again
ACROSS = 120  # seconds: one person walking past several cameras is one message
TOO_OLD = 600  # an event this old when BRAM first hears of it is not news
DAILY = 30
DAY = 86400
MUTE = "BRAM_CAMERA_"
PROXY = "/api/frigate/notifications/{id}/snapshot.jpg"


def picture(hass: HomeAssistant, event_id: str) -> str | None:
    """Frigate's own picture for a phone message, if its integration is installed."""
    if "frigate" not in hass.config.components:
        return None
    return PROXY.format(id=quote(event_id, safe=""))


def place(camera: str) -> str:
    return camera.replace("_", " ").replace("-", " ").strip()


class CameraWatch:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 away: Callable[[], bool], night: Callable[[], bool],
                 note: Callable[..., None] = lambda *a: None,
                 teller: Teller | None = None) -> None:
        self._hass, self._away, self._night, self._note = hass, away, night, note
        self._teller = teller or Teller(hass, entry)
        options = entry.options
        self._on = {r for r in RULES if options.get(r)}
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
        return self._hass.bus.async_listen("mobile_app_notification_action", self.answered)

    @callback
    def answered(self, event: Event) -> None:
        action = event.data.get("action")
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

    def _rule(self, event: dict) -> tuple[str, str] | None:
        """Which rule this event meets, and what to say. The most urgent first."""
        camera, label, who = place(event["camera"]), event["label"], event["who"]
        if label == "person":
            someone = who or "Someone"
            if "camera_away" in self._on and self._away():
                return "camera_away", f"{someone} at {camera}, and everyone I track is away."
            if "camera_night" in self._on and self._night():
                return "camera_night", f"{someone} at {camera}, and it's night."
            if "camera_stranger" in self._on and not who:
                return "camera_stranger", f"A person Frigate does not know at {camera}."
        if label == "package" and "camera_package" in self._on:
            return "camera_package", f"A package at {camera}."
        return None

    async def weigh(self, camera: str, event: dict) -> None:
        """Called for each event the server passes on, new or changed."""
        now = dt_util.utcnow().timestamp()
        self._seen = {k: v for k, v in self._seen.items() if now - v < DAY}
        if event["id"] in self._seen or now - event["start"] > TOO_OLD:
            return
        found = self._rule({**event, "camera": camera})
        if found is None:
            return  # not yet: Frigate may still name the person or add a zone
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
        actions = [{"action": MUTE + key, "title": "Stop these"},
                   *([] if rule in URGENT else self._teller.actions(f"camera:{key}"))]
        self._note(f"cameras:{key}", "open", text, "cameras",
                   "medium" if rule in URGENT else "low")
        if await notify(self._hass, self._phones, "BRAM camera", text, f"bram_camera_{what}",
                        safety=False, actions=actions, finding=f"cameras:{key}",
                        image=picture(self._hass, event["id"])):
            self._last[key] = self._last[across] = now
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
    def _save(self) -> None:
        self._store.async_delay_save(lambda: {"muted": self._muted, "last": self._last}, 1)
