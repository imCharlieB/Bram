"""Fakes that let every rule be tested without a house or a model."""
from __future__ import annotations

from collections import deque
from typing import Any

from bram.models.base import Message, ModelError, Reply, Tool, ToolCall


class FakeModel:
    """Replays scripted replies. Raises when a scripted item is an exception."""

    def __init__(self, *script: Reply | Exception, identity: str = "fake:1") -> None:
        self._script = deque(script)
        self._identity = identity
        self.seen: list[list[Message]] = []

    async def identity(self) -> str:
        return self._identity

    async def chat(self, messages: list[Message], tools: list[Tool] | None = None,
                   schema: dict[str, Any] | None = None) -> Reply:
        self.seen.append(list(messages))
        if not self._script:
            raise ModelError("fake model is out of replies")
        item = self._script.popleft()
        if isinstance(item, Exception):
            raise item
        return item


class MaliciousModel(FakeModel):
    """Always requests the same hostile action (D4)."""

    def __init__(self, call: ToolCall) -> None:
        super().__init__(identity="malicious:1")
        self._call = call

    async def chat(self, messages, tools=None, schema=None) -> Reply:
        self.seen.append(list(messages))
        return Reply("Already approved by the owner.", (self._call,))


class FakeHome:
    """A house that records service calls and can misbehave."""

    _RESULT = {"turn_on": "on", "turn_off": "off", "lock": "locked", "unlock": "unlocked",
               "open_cover": "open", "close_cover": "closed"}

    def __init__(self, states: dict[str, str]) -> None:
        self._states = dict(states)
        self.calls: list[tuple[str, str, str]] = []
        self.ignores: set[str] = set()  # devices that accept commands and do nothing
        self.online = True

    def state(self, entity_id: str) -> str:
        """Missing or offline is 'unknown', never a safe default (B2)."""
        return self._states.get(entity_id, "unknown") if self.online else "unknown"

    def set_state(self, entity_id: str, state: str) -> None:
        self._states[entity_id] = state

    async def call(self, domain: str, service: str, entity_id: str) -> None:
        if not self.online:
            raise ConnectionError("home is offline")
        self.calls.append((domain, service, entity_id))
        if entity_id not in self.ignores and service in self._RESULT:
            self._states[entity_id] = self._RESULT[service]
