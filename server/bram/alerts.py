"""Alerts: what to send, when, and how often. Fixed text, no model (C1)."""
from __future__ import annotations

import asyncio
import datetime
import logging
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from .audit import Audit

_LOGGER = logging.getLogger(__name__)

# Seconds after each safety send until the next, until acknowledged (C4).
REPEAT = (120, 180, 300, 600, 900, 900, 1800, 1800, 3600, 3600, 3600)
MAX_SAFETY = len(REPEAT) + 1
MAX_NOTICE_TRIES = 5
RETRY = 60
SNOOZE = 4 * 3600
DAILY_NOTICES = 10
HOUSE_DOWN_AFTER = 180
HOUSE_KEY = "home assistant"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert (
    id TEXT PRIMARY KEY, house_id TEXT NOT NULL, key TEXT NOT NULL, text TEXT NOT NULL,
    safety INTEGER NOT NULL, created REAL NOT NULL, acked REAL, cleared REAL);
CREATE TABLE IF NOT EXISTS delivery (
    alert_id TEXT NOT NULL, channel TEXT NOT NULL, next_at REAL, sends INTEGER NOT NULL,
    failures INTEGER NOT NULL, last_sent REAL, PRIMARY KEY (alert_id, channel));
CREATE TABLE IF NOT EXISTS mute (house_id TEXT, key TEXT, PRIMARY KEY (house_id, key));
"""


@dataclass(frozen=True)
class Outgoing:
    alert_id: str
    title: str
    text: str
    safety: bool
    buttons: tuple[tuple[str, str], ...] = ()  # (label, action)


class Channel(Protocol):
    name: str

    def ready(self) -> bool: ...

    async def send(self, message: Outgoing) -> None:
        """Raise on failure."""


class Alerts:
    def __init__(self, path: Path | str, audit: Audit, quiet: Callable[[str], dict] | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._db = sqlite3.connect(path, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._audit, self._clock = audit, clock
        self._quiet = quiet or (lambda channel: {})
        self.channels: list[Channel] = []
        self._down: dict[str, tuple[float, str]] = {}

    # --- raising and clearing ---

    def raise_alert(self, house_id: str, key: str, text: str, *, safety: bool) -> str | None:
        """Start an alert, unless the same thing is already open."""
        if self._db.execute("SELECT 1 FROM alert WHERE house_id = ? AND key = ? AND safety = ?"
                            " AND cleared IS NULL", (house_id, key, safety)).fetchone():
            return None
        if not safety and self._db.execute("SELECT 1 FROM mute WHERE house_id = ? AND key = ?",
                                           (house_id, key)).fetchone():
            self._audit.record(house_id, key, "muted", text, "not sent")
            return None
        alert_id, now = secrets.token_hex(8), self._clock()
        with self._db:
            self._db.execute("INSERT INTO alert VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
                             (alert_id, house_id, key, text, safety, now))
        self._audit.record(house_id, key, "alert" if safety else "notice", text, "raised")
        return alert_id

    def clear(self, house_id: str, key: str, text: str | None = None, *, safety: bool) -> None:
        """The cause is gone. Safety alerts still repeat until acknowledged."""
        now = self._clock()
        with self._db:
            rows = self._db.execute(
                "UPDATE alert SET cleared = ? WHERE house_id = ? AND key = ? AND safety = ?"
                " AND cleared IS NULL RETURNING id", (now, house_id, key, safety)).fetchall()
            if not safety:
                for row in rows:
                    self._db.execute("UPDATE delivery SET next_at = NULL WHERE alert_id = ?",
                                     (row["id"],))
        if rows and text:
            self._audit.record(house_id, key, "cleared", text, "ok")
            alert_id = secrets.token_hex(8)
            with self._db:
                self._db.execute("INSERT INTO alert VALUES (?, ?, ?, ?, 0, ?, NULL, ?)",
                                 (alert_id, house_id, key, text, now, now))

    def house_down(self, house_id: str, name: str) -> None:
        text = f"BRAM has lost contact with Home Assistant ({name}). It cannot see that home."
        self._down.setdefault(house_id, (self._clock() + HOUSE_DOWN_AFTER, text))

    def house_up(self, house_id: str, name: str) -> None:
        self._down.pop(house_id, None)
        # Contact itself is the answer, so nothing is left to acknowledge.
        with self._db:
            self._db.execute("UPDATE delivery SET next_at = NULL WHERE alert_id IN (SELECT id FROM"
                             " alert WHERE house_id = ? AND key = ? AND cleared IS NULL)",
                             (house_id, HOUSE_KEY))
        self.clear(house_id, HOUSE_KEY, f"Home Assistant ({name}) is back.", safety=True)

    def settle(self, house_id: str, key: str) -> None:
        """Answered in Home Assistant, so stop here too."""
        with self._db:
            self._db.execute(
                "UPDATE alert SET acked = coalesce(acked, ?), cleared = coalesce(cleared, ?)"
                " WHERE house_id = ? AND key = ?", (self._clock(), self._clock(), house_id, key))
            self._db.execute("UPDATE delivery SET next_at = NULL WHERE alert_id IN"
                             " (SELECT id FROM alert WHERE house_id = ? AND key = ?)",
                             (house_id, key))

    def forget(self, house_id: str, key: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM delivery WHERE alert_id IN (SELECT id FROM alert WHERE"
                             " house_id = ? AND key = ?)", (house_id, key))
            self._db.execute("DELETE FROM alert WHERE house_id = ? AND key = ?", (house_id, key))
            self._db.execute("DELETE FROM mute WHERE house_id = ? AND key = ?", (house_id, key))

    def forget_house(self, house_id: str) -> None:
        self._down.pop(house_id, None)
        with self._db:
            ids = "SELECT id FROM alert WHERE house_id = ?"
            self._db.execute(f"DELETE FROM delivery WHERE alert_id IN ({ids})", (house_id,))  # noqa: S608
            self._db.execute("DELETE FROM alert WHERE house_id = ?", (house_id,))
            self._db.execute("DELETE FROM mute WHERE house_id = ?", (house_id,))

    # --- answers ---

    def answer(self, action: str, by: str) -> str:
        """Handle a button. An action can only quiet an alert, never anything else."""
        verb, _, alert_id = action.partition(":")
        row = self._db.execute("SELECT * FROM alert WHERE id = ?", (alert_id,)).fetchone()
        if row is None or verb not in ("ack", "snooze", "mute"):
            return "That is no longer active."
        if row["safety"] and verb != "ack":
            return "Safety alerts can only be acknowledged."
        with self._db:
            if verb == "snooze":
                self._db.execute("UPDATE delivery SET next_at = ?, sends = 0, failures = 0"
                                 " WHERE alert_id = ?", (self._clock() + SNOOZE, alert_id))
            else:
                self._db.execute("UPDATE alert SET acked = coalesce(acked, ?) WHERE id = ?",
                                 (self._clock(), alert_id))
                self._db.execute("UPDATE delivery SET next_at = NULL WHERE alert_id = ?",
                                 (alert_id,))
            if verb == "mute":
                self._db.execute("INSERT OR IGNORE INTO mute VALUES (?, ?)",
                                 (row["house_id"], row["key"]))
        done = {"ack": "Acknowledged", "snooze": "Snoozed for 4 hours",
                "mute": "Stopped. You can undo this on the Messages page"}[verb]
        self._audit.record(row["house_id"], row["key"], verb, row["text"], "ok", approver=by)
        return f"{done}."

    def muted(self) -> list[dict]:
        return [dict(r) for r in self._db.execute("SELECT * FROM mute ORDER BY key")]

    def unmute(self, house_id: str, key: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM mute WHERE house_id = ? AND key = ?", (house_id, key))

    # --- sending ---

    async def tick(self) -> None:
        now = self._clock()
        for house_id, (due, text) in list(self._down.items()):
            if now >= due:
                del self._down[house_id]
                self.raise_alert(house_id, HOUSE_KEY, text, safety=True)
        ready = {c.name: c for c in self.channels if c.ready()}
        with self._db:
            for name in ready:
                # A channel turned on later gets what is still open, not old history.
                self._db.execute(
                    "INSERT OR IGNORE INTO delivery SELECT id, ?, ?, 0, 0, NULL FROM alert"
                    " WHERE acked IS NULL AND created > ?", (name, now, now - 86400))
        due = self._db.execute(
            "SELECT a.*, d.channel, d.sends, d.failures FROM delivery d JOIN alert a"
            " ON a.id = d.alert_id WHERE d.next_at <= ? ORDER BY a.safety DESC, a.created",
            (now,)).fetchall()
        # A slow channel must not hold up another.
        await asyncio.gather(*(self._channel(ready[name], [r for r in due if r["channel"] == name])
                               for name in {r["channel"] for r in due} if name in ready))

    async def _channel(self, channel: Channel, rows: list[sqlite3.Row]) -> None:
        for row in rows:
            await self._send(channel, row)

    async def _send(self, channel: Channel, row: sqlite3.Row) -> None:
        now, safety = self._clock(), bool(row["safety"])
        # It may have been answered while an earlier message was being sent.
        current = self._db.execute(
            "SELECT next_at FROM delivery WHERE alert_id = ? AND channel = ?",
            (row["id"], channel.name)).fetchone()
        if current is None or current["next_at"] is None or current["next_at"] > now:
            return
        if not safety:
            later = quiet_until(self._quiet(channel.name), now)
            if later is not None:
                self._schedule(row["id"], channel.name, later)
                return
            sent = self._db.execute(
                "SELECT count(*) FROM delivery d JOIN alert a ON a.id = d.alert_id WHERE"
                " a.safety = 0 AND d.channel = ? AND d.last_sent > ?",
                (channel.name, now - 86400)).fetchone()[0]
            if sent >= DAILY_NOTICES:
                self._schedule(row["id"], channel.name, None)
                self._audit.record(row["house_id"], row["key"], "daily limit", channel.name,
                                   "not sent")
                return
        buttons = [("Acknowledge", f"ack:{row['id']}")]
        if not safety:
            buttons = [] if row["cleared"] else [
                ("OK", f"ack:{row['id']}"), ("Snooze 4 hours", f"snooze:{row['id']}"),
                ("Stop these", f"mute:{row['id']}")]
        text = row["text"]
        if safety and row["cleared"]:
            text += " It has since cleared."
        title = "BRAM alert" if safety else "BRAM"
        if safety and row["sends"]:
            title = f"BRAM alert, reminder {row['sends']}"
        try:
            async with asyncio.timeout(20):
                await channel.send(Outgoing(row["id"], title, text, safety, tuple(buttons)))
        except Exception as err:  # noqa: BLE001 - one broken channel must never stop the rest
            failures = row["failures"] + 1
            give_up = not safety and failures >= MAX_NOTICE_TRIES
            with self._db:
                self._db.execute(
                    "UPDATE delivery SET failures = ?, next_at = CASE WHEN next_at IS NULL THEN"
                    " NULL ELSE ? END WHERE alert_id = ? AND channel = ?",
                    (failures, None if give_up else self._clock() + RETRY, row["id"],
                     channel.name))
            if failures == 1 or give_up:
                self._audit.record(row["house_id"], row["key"], "send failed", channel.name,
                                   type(err).__name__)
            return
        sends = row["sends"] + 1
        again = self._clock() + REPEAT[sends - 1] if safety and sends < MAX_SAFETY else None
        with self._db:
            self._db.execute(
                "UPDATE delivery SET sends = ?, failures = 0, last_sent = ?, next_at = CASE WHEN"
                " next_at IS NULL THEN NULL ELSE ? END WHERE alert_id = ? AND channel = ?",
                (sends, self._clock(), again, row["id"], channel.name))
        self._audit.record(row["house_id"], row["key"], "sent", f"{channel.name}: {row['text']}",
                           "ok")

    def _schedule(self, alert_id: str, channel: str, at: float | None) -> None:
        with self._db:
            self._db.execute("UPDATE delivery SET next_at = ? WHERE alert_id = ? AND channel = ?",
                             (at, alert_id, channel))

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # the alert loop must never die
                _LOGGER.exception("Alert loop error")
            await asyncio.sleep(2)

    def close(self) -> None:
        self._db.close()


def quiet_until(quiet: dict, now: float) -> float | None:
    """When quiet hours end, or None if it is not quiet now."""
    start, end = quiet.get("from"), quiet.get("to")
    if start is None or end is None or start == end:
        return None
    local = datetime.datetime.fromtimestamp(now, ZoneInfo(quiet.get("timezone") or "UTC"))
    hour = local.hour
    inside = start <= hour < end if start < end else hour >= start or hour < end
    if not inside:
        return None
    finish = local.replace(hour=end, minute=0, second=0, microsecond=0)
    if finish <= local:
        finish += datetime.timedelta(days=1)
    return finish.timestamp()
