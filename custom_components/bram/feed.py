"""Read-only feed of the entities the owner chose."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
from collections.abc import Callable, Iterable
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from . import cameras, gate
from .client import connect
from .const import CONF_FINGERPRINT, CONF_ROOMS, DOMAIN, MOODS
from .details import WITH_PARTS, detail, room_sensors, siblings
from .names import entity_name
from .queries import answer
from .shared import shared

_LOGGER = logging.getLogger(__name__)
HEARTBEAT = 30
ANSWER_TIMEOUT = 60
_VERSION = re.compile(r"\d{1,4}\.\d{1,4}\.\d{1,4}")
RETRY_MAX = 300
QUEUE_SIZE = 1000

_BINARY = {"moisture": "leak", "smoke": "smoke", "carbon_monoxide": "co", "gas": "gas",
           "heat": "heat", "safety": "hazard", "tamper": "hazard",
           "door": "opening", "window": "opening",
           "opening": "opening", "garage_door": "opening",
           "motion": "motion", "occupancy": "motion", "presence": "motion", "moving": "motion"}
_APPLIANCES = ("water_heater", "vacuum", "lawn_mower", "humidifier")
_OTHER = ("sensor", "weather", "alarm_control_panel", "siren", "input_boolean", "input_select",
          "update", "sun")
_COVER = {"door", "garage", "gate", "window"}


def kind_of(entity_id: str, device_class: str | None) -> str | None:
    """The kind BRAM understands, or None."""
    domain = entity_id.split(".", 1)[0]
    if domain in ("person", "lock", "light", "switch", "fan", "climate"):
        return domain
    if domain == "media_player":
        return "media"
    if domain == "assist_satellite":
        return "satellite"
    if domain == "valve":
        return "valve"
    if domain in _APPLIANCES:
        return "appliance"
    if domain == "sensor" and device_class in ("temperature", "humidity"):
        return device_class
    if domain in _OTHER:
        return "other"
    if domain == "binary_sensor":
        return _BINARY.get(device_class or "", "other")
    if domain == "cover" and device_class in _COVER:
        return "opening"
    return None


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version))


def say(state: State) -> str:
    """The state, with the numbers that matter for thermostats and readings."""
    if state.state in ("unavailable", "unknown"):
        return state.state
    if state.entity_id.startswith("climate."):
        parts = [state.state]
        for key, word in (("current_temperature", "now"), ("temperature", "set to")):
            if isinstance(value := state.attributes.get(key), (int, float)):
                parts.append(f"{word} {value:g}")
        return ", ".join(parts)
    if state.entity_id.startswith("water_heater."):
        temperature = state.attributes.get("temperature")
        return (f"{state.state}, set to {temperature:g}" if isinstance(temperature, (int, float))
                else state.state)[:60]
    if state.entity_id.startswith(("sensor.", "weather.")):
        return f"{state.state} {state.attributes.get('unit_of_measurement') or ''}".strip()[:60]
    return state.state[:60]


class Feed:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._entities: list[str] = shared(hass, entry.options)
        self._kinds: dict[str, str] = {}
        self._rooms: dict[str, str] = entry.options.get(CONF_ROOMS, {})
        self._listeners: list[Callable[[], None]] = []
        self.version: str | None = None
        self.alerts: Any = None  # set during setup
        self.rules: Any = None
        self.learner: Any = None
        self.suggestions: Any = None
        self.outbox: Any = None
        self.problems: Any = None
        self.printers: Any = None
        self.teller: Any = None
        self.camera_watch: Any = None
        self._queue: asyncio.Queue[dict] | None = None
        self._queries: set[asyncio.Task] = set()
        self._asked: dict[str, asyncio.Future[str]] = {}
        self.connected = False
        self.beliefs: dict[str, str] = {}
        self.server_version: str | None = None
        self.mood: str | None = None
        # Cameras the server watches for this home, and each one's latest event (E2).
        self.camera_names: list[str] = []
        self.camera_events: dict[str, dict] = {}
        self.camera_zones: dict[str, list[str]] = {}  # from Frigate, for the settings

    @property
    def entities(self) -> list[str]:
        return self._entities

    def kind(self, entity_id: str) -> str | None:
        return self._kinds.get(entity_id)

    @callback
    def listen(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def send(self, message: dict) -> bool:
        """Queue a message for the server. False if it cannot be sent now."""
        if self._queue is None:
            return False
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            return False
        return True

    @callback
    def note(self, key: str, what: str, text: str, source: str, severity: str = "low") -> None:
        """For the server's record. Never needed for an alert to work."""
        if self.outbox is not None:
            self.outbox.note(key, what, text, source, severity)

    @callback
    def act(self, action: str) -> None:
        """A Stop these or Less often, handled as the phone button that was offered."""
        pressed = Event("mobile_app_notification_action", {"action": action})
        for part in (self.alerts, self.rules, self.problems, self.printers, self.teller,
                     self.camera_watch):
            if part is not None:
                part.answered(pressed)

    @callback
    def offer(self, key: str, actions: list[dict[str, str]], source: str) -> None:
        """Buttons a phone was given, so BRAM's page can offer the same ones."""
        if self.outbox is not None:
            self.outbox.offer(key, actions, source)

    @callback
    def send_printers(self, items: list[dict]) -> bool:
        if not self.connected or self.server_version is None or _key(
                self.server_version) < (0, 27):
            return False
        return self.send({"type": "printers", "items": items[:20]})

    @callback
    def send_watching(self, items: list[dict]) -> bool:
        """What is counting down. Display only."""
        if not self.connected or self.server_version is None or _key(
                self.server_version) < (0, 31):
            return False
        mine = list(items)
        if self.printers is not None:
            mine += self.printers.pending()
        return self.send({"type": "watching", "items": mine[:30]})

    @callback
    def takes_notes(self) -> bool:
        return (self.connected and self.server_version is not None
                and _key(self.server_version) >= (0, 24))

    @callback
    def camera_not_news(self, camera: str, event_id: str) -> bool:
        """Not news, pressed on a phone: the server keeps it with the rest (0.45 or later)."""
        if not self.connected or self.server_version is None or _key(
                self.server_version) < (0, 45):
            return False
        return self.send({"type": "camera_quiet_add", "camera": camera, "id": event_id[:80]})

    async def ask(self, text: str, conversation: str) -> str:
        """Ask the server. The answer is only ever words to say."""
        key = secrets.token_hex(8)
        waiting = self._asked[key] = self._hass.loop.create_future()
        try:
            if not self.send({"type": "ask", "id": key, "text": text[:2000],
                              "conversation": conversation[:64]}):
                return "I can't reach the BRAM Server right now."
            async with asyncio.timeout(ANSWER_TIMEOUT):
                return await waiting
        except TimeoutError:
            return "That took too long. Please try again."
        finally:
            self._asked.pop(key, None)

    @callback
    def _set_connected(self, connected: bool) -> None:
        self.connected = connected
        self.beliefs.clear()
        self.server_version = None
        if not connected:
            for waiting in self._asked.values():
                if not waiting.done():
                    waiting.set_result("I lost contact with the BRAM Server.")
        self._notify()

    async def _query(self, data: dict) -> None:
        try:
            async with asyncio.timeout(15):
                result = await answer(self._hass, self._entry, self._kinds, data["what"],
                                      data["entity_id"])
        except Exception:
            _LOGGER.exception("Could not answer a question from the server")
            result = {"error": "failed"}
        self.send({"type": "result", "id": data["id"], "result": result})

    @callback
    def _compare(self) -> None:
        """Show a repair while the two halves of BRAM differ."""
        # Fixes may differ between the two sides; features should not.
        if self.version is None or (
                self.server_version and _key(self.server_version)[:2] == _key(self.version)[:2]):
            ir.async_delete_issue(self._hass, DOMAIN, "version")
            return
        server = self.server_version
        older = server is None or _key(server) < _key(self.version)
        ir.async_create_issue(
            self._hass, DOMAIN, "version", is_fixable=False, severity=ir.IssueSeverity.WARNING,
            translation_key="server_outdated" if older else "integration_outdated",
            translation_placeholders={"server": server or "older", "here": self.version})

    @callback
    def handle_message(self, raw: str) -> None:
        """Accept display-only beliefs about chosen entities. Refuse everything else."""
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if (isinstance(data, dict) and data.keys() == {"type", "id", "what", "entity_id"}
                and data["type"] == "query" and isinstance(data["id"], str)
                and len(data["id"]) <= 32 and len(self._queries) < 5):
            # Reads only, and only what the owner turned on.
            task = self._hass.async_create_task(self._query(data), "bram query")
            self._queries.add(task)
            task.add_done_callback(self._queries.discard)
            return
        if (isinstance(data, dict) and data.keys() == {"type", "id", "text"}
                and data["type"] == "answer" and isinstance(data["id"], str)
                and isinstance(data["text"], str) and data["id"] in self._asked):
            if not self._asked[data["id"]].done():
                self._asked[data["id"]].set_result(data["text"][:4000])
            return
        if (isinstance(data, dict) and data.keys() == {"type", "id"}
                and data["type"] == "noted" and isinstance(data["id"], str)):
            if self.outbox is not None:
                self.outbox.confirmed(data["id"])
            return
        if (isinstance(data, dict) and data.keys() == {"type", "key", "action"}
                and data["type"] == "press" and self.outbox is not None
                and self.outbox.press(data["key"], data["action"])):
            self.act(data["action"])
            return
        if (isinstance(data, dict) and data.keys() == {"type", "key", "why"}
                and data["type"] == "suggest" and self.suggestions is not None):
            # Only a suggestion; nothing changes until an admin answers it (F4).
            self.suggestions.received(data["key"], data["why"])
            return
        if (isinstance(data, dict) and data.keys() == {"type", "nights", "opens"}
                and data["type"] == "learned" and self.learner is not None):
            # Summaries for suggestions only; the owner approves any change (F4).
            self.learner.received(data["nights"], data["opens"])
            return
        if (isinstance(data, dict) and data.keys() == {"type", "names", "last"}
                and data["type"] == "cameras"):
            found = cameras.names(data["names"])
            if found is not None and isinstance(data["last"], dict):
                self.camera_names = found
                events = {n: cameras.event(e) for n, e in data["last"].items() if n in found}
                self.camera_events = {n: e for n, e in events.items() if e is not None}
                self._notify()
                return
        if (isinstance(data, dict) and data.keys() == {"type", "patterns"}
                and data["type"] == "camera_quiet" and self.camera_watch is not None):
            found = cameras.patterns(data["patterns"])
            if found is not None:
                self.camera_watch.quiet = found
                return
        if (isinstance(data, dict) and data.keys() == {"type", "zones"}
                and data["type"] == "camera_zones"):
            found = cameras.zones(data["zones"])
            if found is not None:
                self.camera_zones = found
                return
        if (isinstance(data, dict) and data.keys() == {"type", "camera", "event"}
                and data["type"] == "camera" and data["camera"] in self.camera_names):
            found = cameras.event(data["event"])
            if found is not None:
                self.camera_events[data["camera"]] = found
                if self.camera_watch is not None:
                    self._hass.async_create_task(
                        self.camera_watch.weigh(data["camera"], found), "bram camera")
                self._notify()
                return
        if (isinstance(data, dict) and data.keys() == {"type", "mode"}
                and data["type"] == "mood" and data["mode"] in tuple(MOODS)):
            self.mood = data["mode"]
            self._notify()
            return
        if (isinstance(data, dict) and data.keys() == {"type", "version"}
                and data["type"] == "hello" and isinstance(data["version"], str)
                and _VERSION.fullmatch(data["version"])):
            self.server_version = data["version"]
            self._compare()
            if self.outbox is not None:
                self.outbox.reconnected()
            return
        if (isinstance(data, dict) and data.keys() == {"type", "entity_id", "answer"}
                and data["type"] == "belief" and data["entity_id"] in self._entities
                and data["answer"] in ("yes", "no", "unknown")):
            self.beliefs[data["entity_id"]] = data["answer"]
            if self.server_version is None:  # older servers never say
                self._compare()
            self._notify()
            return
        _LOGGER.warning("Refused a server request: %s", gate.decide(data).reason)

    def _state(self, entity_id: str, state: State | None) -> dict[str, str]:
        if state is not None:
            kind = kind_of(entity_id, state.attributes.get("device_class"))
            # A sensor that briefly loses its type must stay what it was known to be.
            if kind and not (kind == "other" and entity_id in self._kinds):
                self._kinds[entity_id] = kind
        # A missing entity is reported as unavailable, never left out (B2).
        return {"entity_id": entity_id, "kind": self._kinds.get(entity_id, "unsupported"),
                "state": say(state) if state is not None else "unavailable",
                "name": entity_name(self._hass, state) if state is not None else "",
                "detail": detail(self._hass, state, self._rooms)}

    def _snapshot(self, entities: Iterable[str]) -> dict:
        return {"type": "snapshot", "version": self.version or "",
                "states": [self._state(e, self._hass.states.get(e)) for e in entities]}

    async def run(self) -> None:
        """Stay connected until cancelled."""
        delay, warned = 5, False
        while True:
            try:
                ws = await connect(
                    async_get_clientsession(self._hass), self._entry.data["host"],
                    self._entry.data["port"], self._entry.data[CONF_FINGERPRINT],
                    self._entry.data["token"])
                async with ws:
                    _LOGGER.info("Connected to the BRAM Server")
                    delay, warned = 5, False
                    self._set_connected(True)
                    try:
                        await self._session(ws)
                    finally:
                        self._set_connected(False)
            except (aiohttp.ClientError, TimeoutError, ConnectionError) as err:
                if not warned:
                    _LOGGER.warning("BRAM Server connection failed: %s", type(err).__name__)
                    warned = True
            await asyncio.sleep(delay)
            delay = min(delay * 2, RETRY_MAX)

    async def _session(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        queue: asyncio.Queue[dict] = asyncio.Queue(QUEUE_SIZE)
        overflow = asyncio.Event()

        @callback
        def changed(event: Event[EventStateChangedData]) -> None:
            try:
                queue.put_nowait({"type": "state", "state": self._state(
                    event.data["entity_id"], event.data["new_state"])})
            except asyncio.QueueFull:
                overflow.set()  # reconnect with a fresh snapshot rather than lose a change

        # Nothing can change between these two lines: neither one awaits.
        unsubscribe = async_track_state_change_event(self._hass, self._entities, changed)
        # A person's room changes without the person changing.
        rooms: dict[str, list[str]] = {}
        for person in (e for e in self._entities if e.startswith("person.")):
            for sensor in room_sensors(
                    self._hass, self._hass.states.get(person), self._rooms):
                rooms.setdefault(sensor, []).append(person)

        @callback
        def moved(event: Event[EventStateChangedData]) -> None:
            for person in rooms.get(event.data["entity_id"], []):
                self.send({"type": "state", "state": self._state(
                    person, self._hass.states.get(person))})

        # A device's other readings change without the device itself changing.
        for owner in (e for e in self._entities if e.startswith(WITH_PARTS)):
            for part in siblings(self._hass, owner):
                rooms.setdefault(part, []).append(owner)
        stop_rooms = async_track_state_change_event(self._hass, list(rooms), moved)
        snapshot = self._snapshot(self._entities)
        self._queue = queue

        async def send() -> None:
            await ws.send_json(snapshot)
            while not overflow.is_set():
                try:
                    async with asyncio.timeout(HEARTBEAT):
                        message = await queue.get()
                except TimeoutError:
                    message = {"type": "heartbeat"}
                await ws.send_json(message)

        async def receive() -> None:
            async for message in ws:
                if message.type is aiohttp.WSMsgType.TEXT:
                    self.handle_message(message.data)

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            self._queue = None
            unsubscribe()
            stop_rooms()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
