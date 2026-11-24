"""Log-only watcher: records what BRAM would say. It sends and controls nothing."""
from __future__ import annotations

from .audit import Audit
from .world import Answer, Event, World

# Fixed text, no model (C1).
NOTABLE = {
    "leak": "Water leak detected.",
    "smoke": "Smoke detected. Check now.",
}
UNCHECKED = {
    "leak": "A leak sensor stopped reporting, so I cannot check it.",
    "smoke": "A smoke sensor stopped reporting, so I cannot check it.",
}


class Watcher:
    def __init__(self, world: World, audit: Audit) -> None:
        self._world = world
        self._audit = audit
        self._last: dict[str, Answer] = {}

    def handle(self, event: Event) -> str | None:
        """Update the world and return what BRAM would say, if anything."""
        self._world.update(event)
        now = self._world.check(event.entity_id)
        before = self._last.get(event.entity_id)
        self._last[event.entity_id] = now
        if now == before:
            return None
        text = None
        if now is Answer.YES:
            text = NOTABLE.get(event.kind)
        elif now is Answer.UNKNOWN:
            text = UNCHECKED.get(event.kind)
        if text:
            self._audit.record(event.house_id, event.entity_id, "would_say", text, "log_only")
        return text
