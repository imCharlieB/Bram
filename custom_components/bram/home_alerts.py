"""Safety and silent-sensor alerts. Fixed text, no model, no server (C1, C2)."""
from __future__ import annotations

import asyncio
import datetime
import secrets
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENTITIES,
    CONF_ESCALATE,
    CONF_PHONES,
    CONF_QUIET_FROM,
    CONF_QUIET_TO,
    CONF_SAFETY_PHONES,
    DOMAIN,
)
from .feed import Feed, kind_of
from .notifier import dismiss, notify

# Seconds after each safety send until the next, until acknowledged (C4).
REPEAT = (120, 180, 300, 600, 900, 900, 1800, 1800, 3600, 3600, 3600)
RETRY = 60
SILENT_AFTER = 300
SERVER_AFTER = 180
ESCALATE_AFTER = 300
DAILY_NOTICES = 10
GROUP_MIN, GROUP_MAX = 3, 8
DAY = 86400

TEXT = {"leak": "Water leak detected", "smoke": "Smoke detected. Check now",
        "co": "CARBON MONOXIDE detected. Get out and call for help",
        "gas": "GAS detected. Get out and call for help", "heat": "Dangerous heat detected",
        "hazard": "Safety problem detected"}
SILENT = {"leak": "leaks", "smoke": "smoke", "co": "carbon monoxide", "gas": "gas",
          "heat": "heat", "hazard": "problems"}
CLEAR = {"leak": "is dry", "heat": "is normal"}
ACK, MUTE = "BRAM_ACK_", "BRAM_MUTE_"


def within(hours: tuple[str | None, str | None], now: datetime.time) -> bool:
    start, end = (dt_util.parse_time(t) if t else None for t in hours)
    if start is None or end is None or start == end:
        return False
    return start <= now < end if start < end else now >= start or now < end


class HomeAlerts:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, feed: Feed) -> None:
        self._hass, self._feed = hass, feed
        options = entry.options
        self._entities: list[str] = options.get(CONF_ENTITIES, [])
        self._phones: list[str] = options.get(CONF_PHONES, [])
        # These get leak, smoke, and other safety alerts, and nothing else.
        self._safety_phones = [*dict.fromkeys(
            [*self._phones, *options.get(CONF_SAFETY_PHONES, [])])]
        self._quiet = (options.get(CONF_QUIET_FROM), options.get(CONF_QUIET_TO))
        self._escalate: bool = options.get(CONF_ESCALATE, False)
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._alerts: dict[str, dict[str, Any]] = {}
        self._muted: list[str] = []
        self._kinds: dict[str, str] = {}
        self._silent: dict[str, float] = {}
        self._told_silent: dict[str, str] = {}
        self._waiting: list[dict[str, Any]] = []
        self._sent_notices: list[float] = []
        self._server_lost: float | None = None
        self._told_server = False
        self._lock = asyncio.Lock()

    async def start(self) -> Callable[[], None]:
        saved = await self._store.async_load() or {}
        self._kinds = saved.get("kinds", {})
        self._muted = saved.get("muted", [])
        self._alerts = {e: a for e, a in saved.get("alerts", {}).items() if e in self._entities}
        stops = [
            async_track_state_change_event(self._hass, self._entities, self._changed),
            self._hass.bus.async_listen("mobile_app_notification_action", self._answered),
            async_track_time_interval(self._hass, self._tick, datetime.timedelta(seconds=10)),
            self._feed.listen(self._server_changed),
        ]
        for entity_id in self._entities:
            self._look(entity_id, self._hass.states.get(entity_id))
        self._server_changed()

        @callback
        def stop() -> None:
            for item in stops:
                item()
        return stop

    # --- what happened ---

    @callback
    def _changed(self, event: Event[EventStateChangedData]) -> None:
        self._look(event.data["entity_id"], event.data["new_state"])

    @callback
    def _look(self, entity_id: str, state: State | None) -> None:
        if state is not None:
            kind = kind_of(entity_id, state.attributes.get("device_class"))
            if kind in TEXT:
                self._kinds[entity_id] = kind
        kind = self._kinds.get(entity_id)
        if kind is None:
            return
        name = self._name(entity_id, state)
        value = state.state if state is not None else "unavailable"
        if value == "on":
            self._heard(entity_id, name)
            self._raise(entity_id, f"{TEXT[kind]}: {name}")
        elif value == "off":
            self._heard(entity_id, f"{name} {CLEAR.get(kind, 'is clear')}")
            self._feed.note(f"safety:{entity_id}", "closed",
                            f"{name} {CLEAR.get(kind, 'is clear')}", "safety", "high")
            if entity_id in self._alerts:
                self._alerts[entity_id]["cleared"] = True
                if self._alerts[entity_id]["acked"]:
                    self._finish(entity_id)
                self._save()
        else:  # unknown is never clear (B2)
            self._silent.setdefault(entity_id, self._now() + SILENT_AFTER)

    def _name(self, entity_id: str, state: State | None) -> str:
        name = state.name if state is not None else entity_id
        name = "".join(c if c.isprintable() else " " for c in name)
        return " ".join(name.split())[:60] or entity_id

    @callback
    def _heard(self, entity_id: str, now_text: str) -> None:
        self._silent.pop(entity_id, None)
        if self._told_silent.pop(entity_id, None):
            self._feed.note(f"silent:{entity_id}", "closed", now_text, "silent", "high")
            self._notice(f"{entity_id} back", f"Reporting again: {now_text}", entity_id, False)

    @callback
    def _raise(self, entity_id: str, text: str) -> None:
        self._feed.note(f"safety:{entity_id}", "open", text, "safety", "high")
        old = self._alerts.get(entity_id)
        if old is not None and not old["cleared"]:
            return
        self._alerts[entity_id] = {
            "id": secrets.token_hex(8), "text": text, "created": self._now(), "sends": 0,
            "next": self._now(), "acked": False, "cleared": False, "escalated": False}
        self._save()
        self._hass.async_create_task(self.run(), "bram alert")

    @callback
    def _finish(self, entity_id: str) -> None:
        alert = self._alerts.pop(entity_id)
        dismiss(self._hass, f"bram_{alert['id']}")
        self._deescalate(entity_id, alert)

    @callback
    def _deescalate(self, entity_id: str, alert: dict[str, Any]) -> None:
        if alert["escalated"]:
            self._feed.send({"type": "deescalate", "entity_id": entity_id})

    @callback
    def _answered(self, event: Event) -> None:
        action = event.data.get("action")
        if not isinstance(action, str):
            return
        for entity_id, alert in list(self._alerts.items()):
            if action == ACK + alert["id"]:
                alert["acked"], alert["next"] = True, None
                self._feed.note(f"safety:{entity_id}", "acked", "Acknowledged on a phone",
                                "safety", "high")
                dismiss(self._hass, f"bram_{alert['id']}")
                self._deescalate(entity_id, alert)
                if alert["cleared"]:
                    self._alerts.pop(entity_id)
                self._save()
                return
        if action.startswith(MUTE) and action[len(MUTE):] in self._entities:
            entity_id = action[len(MUTE):]
            if entity_id not in self._muted:
                self._muted.append(entity_id)
                self._feed.note(f"silent:{entity_id}", "stopped", "Stopped from a phone",
                                "silent", "high")
                self._save()

    @callback
    def _server_changed(self) -> None:
        if not self._feed.connected:
            if self._server_lost is None:
                self._server_lost = self._now()
            return
        self._server_lost = None
        if self._told_server:
            self._told_server = False
            self._notice("server", "The BRAM Server is back.", None, False)

    # --- sending ---

    @callback
    def _notice(self, key: str, text: str, entity_id: str | None, mutable: bool) -> None:
        if entity_id in self._muted:
            return
        self._waiting = [w for w in self._waiting if w["key"] != key]
        self._waiting.append({"key": key, "text": text, "entity_id": entity_id,
                              "mutable": mutable, "tries": 0})

    async def _tick(self, now: datetime.datetime) -> None:
        await self.run()

    async def run(self) -> None:
        """Send whatever is due. One at a time, so nothing is sent twice."""
        async with self._lock:
            await self._safety()
            await self._notices()

    async def _safety(self) -> None:
        for entity_id, alert in list(self._alerts.items()):
            now = self._now()
            if (self._escalate and not alert["acked"] and not alert["escalated"]
                    and now - alert["created"] >= ESCALATE_AFTER
                    and self._feed.send({"type": "escalate", "entity_id": entity_id})):
                alert["escalated"] = True
            if alert["next"] is None or alert["next"] > now:
                continue
            text = alert["text"] + (". It has since cleared." if alert["cleared"] else ".")
            title = f"BRAM alert, reminder {alert['sends']}" if alert["sends"] else "BRAM alert"
            sent = await notify(
                self._hass, self._safety_phones, title, text, f"bram_{alert['id']}", safety=True,
                actions=[{"action": ACK + alert["id"], "title": "Acknowledge"}])
            if sent or alert["sends"] == 0:
                self._feed.note(f"safety:{entity_id}", "sent" if sent else "not sent",
                                f"Phone: {text}", "safety", "high")
            if alert["acked"] or self._alerts.get(entity_id) is not alert:
                dismiss(self._hass, f"bram_{alert['id']}")
                continue  # answered or replaced while it was being sent
            if not sent and self._safety_phones:
                alert["next"] = self._now() + RETRY
            else:
                alert["sends"] += 1
                done = alert["sends"] > len(REPEAT)
                alert["next"] = None if done else self._now() + REPEAT[alert["sends"] - 1]
                if done and alert["cleared"]:
                    self._finish(entity_id)
            self._save()

    async def _notices(self) -> None:
        now = self._now()
        for entity_id, due in list(self._silent.items()):
            if now >= due:
                del self._silent[entity_id]
                name = self._name(entity_id, self._hass.states.get(entity_id))
                self._told_silent[entity_id] = name
                text = (f"{name} stopped reporting, so I cannot check for "
                        f"{SILENT[self._kinds[entity_id]]}.")
                self._feed.note(f"silent:{entity_id}", "open", text, "silent", "high")
                self._notice(f"{entity_id} silent", text, entity_id, True)
        if (self._server_lost is not None and now - self._server_lost >= SERVER_AFTER
                and not self._told_server):
            self._told_server = True
            self._notice("server", "The BRAM Server is not answering. Home alerts still work.",
                         None, False)
        if not self._waiting or not self._phones or self._is_quiet():
            return
        self._sent_notices = [t for t in self._sent_notices if now - t < DAY]
        waiting, self._waiting = self._waiting, []
        while waiting:
            if len(self._sent_notices) >= DAILY_NOTICES:
                return
            # Several at once become one message. Safety alerts never come here.
            batch, waiting = ((waiting[:GROUP_MAX], waiting[GROUP_MAX:])
                              if len(waiting) >= GROUP_MIN else (waiting[:1], waiting[1:]))
            first = batch[0]
            actions = [{"action": MUTE + first["entity_id"], "title": "Stop these"}
                       ] if len(batch) == 1 and first["mutable"] else []
            if await notify(self._hass, self._phones, "BRAM",
                            "\n".join(item["text"] for item in batch),
                            f"bram_{first['key']}", safety=False, actions=actions):
                self._sent_notices.append(now)
                for item in batch:
                    if item["key"].endswith(" silent"):
                        self._feed.note(f"silent:{item['entity_id']}", "sent",
                                        f"Phone: {item['text']}", "silent", "high")
                continue
            for item in batch:
                if item["tries"] < 30:
                    item["tries"] += 1
                    self._waiting.append(item)

    @callback
    def allow_all(self) -> None:
        """Undo every Stop these."""
        self._muted = []
        self._save()

    async def test(self) -> bool:
        return await notify(self._hass, self._safety_phones, "BRAM", "This is a test message.",
                            "bram_test", safety=False, actions=[])

    def _is_quiet(self) -> bool:
        return within(self._quiet, dt_util.now().time())

    def _now(self) -> float:
        return dt_util.utcnow().timestamp()

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: {
            "alerts": self._alerts, "muted": self._muted, "kinds": self._kinds}, 0)
