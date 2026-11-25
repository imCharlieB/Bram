"""What BRAM currently believes, with an explicit unknown (B2)."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

UNUSABLE = {"unknown", "unavailable", "none", ""}
# Meaning of each state, per kind. Anything else is unknown.
MEANING = {
    "person": {"home": True, "not_home": False},
    "leak": {"on": True, "off": False},
    "smoke": {"on": True, "off": False},
    "opening": {"on": True, "off": False, "open": True, "closed": False},
    "motion": {"on": True, "off": False},
    "light": {"on": True, "off": False},
    "lock": {"unlocked": True, "locked": False},
}


class Answer(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Event:
    house_id: str
    entity_id: str
    kind: str
    state: str


class World:
    """Live state of one house. Trusted only while its feed is connected and recent."""

    def __init__(self, house_id: str, max_silence: float = 90,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.house_id = house_id
        self._max_silence = max_silence
        self._clock = clock
        self._last_heard: float | None = None
        self._events: dict[str, Event] = {}

    def heartbeat(self) -> None:
        self._last_heard = self._clock()

    def disconnected(self) -> None:
        """Forget everything; a reconnect must send a fresh snapshot."""
        self._last_heard = None
        self._events.clear()

    def update(self, event: Event) -> None:
        if event.house_id != self.house_id:
            raise ValueError("event belongs to another house")
        self._events[event.entity_id] = event
        self.heartbeat()

    @property
    def live(self) -> bool:
        return (self._last_heard is not None
                and self._clock() - self._last_heard <= self._max_silence)

    def check(self, entity_id: str) -> Answer:
        """Is this device in its notable state (home, leaking, open, unlocked)?"""
        event = self._events.get(entity_id)
        if not self.live or event is None or event.state.lower() in UNUSABLE:
            return Answer.UNKNOWN
        meaning = MEANING.get(event.kind, {}).get(event.state.lower())
        # A person in another named zone is known to be away.
        if meaning is None and event.kind == "person":
            meaning = False
        if meaning is None:
            return Answer.UNKNOWN
        return Answer.YES if meaning else Answer.NO

    def anyone_home(self) -> Answer:
        people = [self.check(i) for i, e in self._events.items() if e.kind == "person"]
        if Answer.YES in people:
            return Answer.YES
        if not people or Answer.UNKNOWN in people:
            return Answer.UNKNOWN
        return Answer.NO
