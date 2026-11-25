"""Notices what matters, for the log and for escalation. Fixed text, no model (C1).

Home Assistant itself sends home alerts, so they never depend on this server.
"""
from __future__ import annotations

from .audit import Audit
from .world import Answer, Event, World

NOTABLE = {
    "leak": "Water leak detected.",
    "smoke": "Smoke detected. Check now.",
    "co": "Carbon monoxide detected. Get out and call for help.",
    "gas": "Gas detected. Get out and call for help.",
    "heat": "Dangerous heat detected.",
    "hazard": "Safety problem detected.",
}
_WHAT = {"leak": "leak", "smoke": "smoke", "co": "carbon monoxide", "gas": "gas",
         "heat": "heat", "hazard": "safety"}
UNCHECKED = {k: f"A {w} sensor stopped reporting, so I cannot check it." for k, w in _WHAT.items()}
RECOVERED = {k: f"A {w} sensor is reporting again, and it is {'dry' if k == 'leak' else 'clear'}."
             for k, w in _WHAT.items()}


def named(text: str, event: Event) -> str:
    """Names are data: printable characters only, and short."""
    name = "".join(c if c.isprintable() else " " for c in event.name)
    name = " ".join(name.split())[:60]
    return f"{text} ({name})" if name else text


class Watcher:
    def __init__(self, world: World, audit: Audit) -> None:
        self._world, self._audit = world, audit
        self._last: dict[str, Answer] = {}

    def handle(self, event: Event) -> str | None:
        """Update the world and return what BRAM has to say, if anything."""
        self._world.update(event)
        now = self._world.check(event.entity_id)
        before = self._last.get(event.entity_id)
        self._last[event.entity_id] = now
        if now == before or event.kind not in NOTABLE:
            return None
        house, key, text = event.house_id, event.entity_id, None
        if now is Answer.YES:
            text = named(NOTABLE[event.kind], event)
        elif now is Answer.UNKNOWN:
            text = named(UNCHECKED[event.kind], event)
        elif before is Answer.UNKNOWN:
            text = named(RECOVERED[event.kind], event)
        if text:
            self._audit.record(house, key, "noticed", text, "ok")
        return text
