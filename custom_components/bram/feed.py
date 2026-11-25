"""Read-only feed of the entities the owner chose."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Iterable

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from . import gate
from .client import connect
from .const import CONF_ENTITIES, CONF_FINGERPRINT

_LOGGER = logging.getLogger(__name__)
HEARTBEAT = 30
RETRY_MAX = 300
QUEUE_SIZE = 1000

_BINARY = {"moisture": "leak", "smoke": "smoke", "door": "opening", "window": "opening",
           "opening": "opening", "garage_door": "opening",
           "motion": "motion", "occupancy": "motion", "presence": "motion", "moving": "motion"}
_COVER = {"door", "garage", "gate", "window"}


def kind_of(entity_id: str, device_class: str | None) -> str | None:
    """The kind BRAM understands, or None."""
    domain = entity_id.split(".", 1)[0]
    if domain in ("person", "lock", "light"):
        return domain
    if domain == "binary_sensor":
        return _BINARY.get(device_class or "")
    if domain == "cover" and device_class in _COVER:
        return "opening"
    return None


class Feed:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._entities: list[str] = entry.options.get(CONF_ENTITIES, [])
        self._kinds: dict[str, str] = {}
        self._listeners: list[Callable[[], None]] = []
        self.version: str | None = None
        self.connected = False
        self.beliefs: dict[str, str] = {}

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
    def _set_connected(self, connected: bool) -> None:
        self.connected = connected
        self.beliefs.clear()
        self._notify()

    @callback
    def handle_message(self, raw: str) -> None:
        """Accept display-only beliefs about chosen entities. Refuse everything else."""
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if (isinstance(data, dict) and data.keys() == {"type", "entity_id", "answer"}
                and data["type"] == "belief" and data["entity_id"] in self._entities
                and data["answer"] in ("yes", "no", "unknown")):
            self.beliefs[data["entity_id"]] = data["answer"]
            self._notify()
            return
        _LOGGER.warning("Refused a server request: %s", gate.decide(data).reason)

    def _state(self, entity_id: str, state: State | None) -> dict[str, str]:
        if state is not None:
            kind = kind_of(entity_id, state.attributes.get("device_class"))
            if kind:
                self._kinds[entity_id] = kind
        # A missing entity is reported as unavailable, never left out (B2).
        return {"entity_id": entity_id, "kind": self._kinds.get(entity_id, "unsupported"),
                "state": state.state if state is not None else "unavailable"}

    def _snapshot(self, entities: Iterable[str]) -> dict:
        return {"type": "snapshot",
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
        snapshot = self._snapshot(self._entities)

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
            unsubscribe()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
