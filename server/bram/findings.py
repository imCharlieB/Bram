"""Everything BRAM found, with its story: found, told, acknowledged, over.

Fixed text from code. No conversation text is ever stored here (E10).
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from .history import number

SOURCES = ("safety", "silent", "rules", "security", "monitors", "connection", "message",
           "learning", "problems", "printers")
SEVERITIES = ("high", "medium", "low")
WHATS = ("open", "closed", "sent", "not sent", "acked", "stopped", "snoozed", "held")
DECIDED = ("sent", "not sent", "acked", "stopped", "snoozed", "held")
PAGE = 50
OLDEST = 30 * 86400
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
# Buttons Home Assistant offered on a phone, which the page may show. Never Acknowledge.
PRESSABLE = re.compile(r"BRAM_(QUIET|PRINTER|PROBLEM|MUTE|LESS)_[\w:.\-]{1,200}")
TITLES = ("Stop these", "Less often")
# Suggestions from what the owner does: only routine messages, never safety (C3).
HABIT_SOURCES = ("rules", "printers", "problems")
HABIT_DAYS = 14
HIDDEN_TIMES, TOLD_TIMES = 3, 5
ASK_AGAIN = 30 * 86400

_SCHEMA = """
CREATE TABLE IF NOT EXISTS finding (
    id INTEGER PRIMARY KEY, house_id TEXT NOT NULL, key TEXT NOT NULL, source TEXT NOT NULL,
    severity TEXT NOT NULL, text TEXT NOT NULL, is_open INTEGER NOT NULL,
    ignored INTEGER NOT NULL DEFAULT 0, first REAL NOT NULL, last REAL NOT NULL,
    times INTEGER NOT NULL, told REAL, acked REAL, stopped REAL, closed REAL,
    UNIQUE (house_id, key));
CREATE TABLE IF NOT EXISTS story (
    id INTEGER PRIMARY KEY, finding INTEGER NOT NULL, uid TEXT UNIQUE, at REAL NOT NULL,
    what TEXT NOT NULL, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS story_finding ON story (finding, at);
CREATE TABLE IF NOT EXISTS print (
    id INTEGER PRIMARY KEY, house_id TEXT NOT NULL, uid TEXT UNIQUE, printer TEXT NOT NULL,
    file TEXT NOT NULL, start REAL NOT NULL, end REAL NOT NULL, result TEXT NOT NULL,
    whole INTEGER NOT NULL, progress REAL, weight REAL);
CREATE TABLE IF NOT EXISTS learned (
    house_id TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL, value TEXT NOT NULL,
    PRIMARY KEY (house_id, kind, day)) WITHOUT ROWID;
"""


def _line(value: object, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError("bad text")
    return " ".join("".join(c if c.isprintable() else " " for c in value).split())[:limit]


class Findings:
    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time,
                 keep_prints: Callable[[], bool] = lambda: False) -> None:
        self.keep_prints = keep_prints
        self._db = sqlite3.connect(path, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        columns = [r[1] for r in self._db.execute("PRAGMA table_info(finding)")]
        with self._db:
            if "buttons" not in columns:
                self._db.execute("ALTER TABLE finding ADD COLUMN buttons TEXT NOT NULL "
                                 "DEFAULT '[]'")
            if "suggested" not in columns:
                self._db.execute("ALTER TABLE finding ADD COLUMN suggested REAL")
        self._clock = clock

    # --- writing ---

    def from_home(self, house_id: str, data: dict) -> None:
        """A note from Home Assistant. Sent again if not confirmed, so the same one is ignored."""
        uid = data.get("id")
        if not isinstance(uid, str) or not re.fullmatch(r"[0-9a-f]{16}", uid):
            raise ValueError("bad note")
        source, what = data.get("source"), data.get("what")
        if source not in SOURCES:
            raise ValueError("bad source")
        at, now = data.get("at"), self._clock()
        if (isinstance(at, bool) or not isinstance(at, (int, float))
                or not now - OLDEST <= at <= now + 60):
            at = now
        key, text = _line(data.get("key"), 255), _line(data.get("text"), 1000)
        if what in ("learned", "forgot"):
            self._learned(house_id, what, key, data["text"])
            return
        if what == "print":
            self._print(house_id, f"{house_id}:{uid}", data["text"])
            return
        if what == "buttons":
            self._buttons(house_id, key, data.get("buttons"))
            return
        if what not in WHATS or data.get("severity") not in SEVERITIES:
            raise ValueError("bad note")
        self.note(house_id, key, what, text, source, data["severity"], at=float(at),
                  uid=f"{house_id}:{uid}")

    def note(self, house_id: str, key: str, what: str, text: str, source: str, severity: str,
             at: float | None = None, uid: str | None = None) -> None:
        at = self._clock() if at is None else at
        with self._db:
            if uid is not None and self._db.execute(
                    "SELECT 1 FROM story WHERE uid = ?", (uid,)).fetchone():
                return
            row = self._db.execute("SELECT * FROM finding WHERE house_id = ? AND key = ?",
                                   (house_id, key)).fetchone()
            if row is None:
                if what == "closed":
                    return
                opening = what == "open"
                finding = self._db.execute(
                    "INSERT INTO finding (house_id, key, source, severity, text, is_open, first, "
                    "last, times) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1) RETURNING id",
                    (house_id, key, source, severity, text, int(opening), at, at)).fetchone()[0]
            else:
                finding = row["id"]
                if what == "open":
                    if row["is_open"]:
                        self._db.execute("UPDATE finding SET last = MAX(last, ?), text = ? "
                                         "WHERE id = ?", (at, text, finding))
                        return
                    self._db.execute(
                        # Hidden until it happened again: it has.
                        "UPDATE finding SET is_open = 1, last = ?, times = times + 1, text = ?, "
                        "severity = ?, acked = NULL, closed = NULL, ignored = 0 WHERE id = ?",
                        (at, text, severity, finding))
                elif what == "closed" and not row["is_open"]:
                    return
            column = {"sent": "told", "acked": "acked", "stopped": "stopped",
                      "closed": "closed"}.get(what)
            if column:
                self._db.execute(f"UPDATE finding SET {column} = ?, last = MAX(last, ?) "  # noqa: S608
                                 "WHERE id = ?", (at, at, finding))
            if what == "closed":
                self._db.execute("UPDATE finding SET is_open = 0, buttons = '[]' WHERE id = ?",
                                 (finding,))
            self._db.execute("INSERT INTO story (finding, uid, at, what, text) "
                             "VALUES (?, ?, ?, ?, ?)", (finding, uid, at, what, text))

    def _buttons(self, house_id: str, key: str, buttons: object) -> None:
        if (not isinstance(buttons, list) or len(buttons) > 3 or not all(
                isinstance(b, dict) and b.keys() == {"action", "title"}
                and isinstance(b["action"], str) and PRESSABLE.fullmatch(b["action"])
                and b["title"] in TITLES for b in buttons)):
            raise ValueError("bad buttons")
        with self._db:
            self._db.execute("UPDATE finding SET buttons = ? WHERE house_id = ? AND key = ?",
                             (json.dumps(buttons), house_id, key))

    def button(self, finding: object, action: object) -> tuple[str, str] | None:
        """The home and key of an open finding that offers this button."""
        if type(finding) is not int or not isinstance(action, str):
            return None
        row = self._db.execute("SELECT house_id, key, buttons FROM finding "
                               "WHERE id = ? AND is_open = 1", (finding,)).fetchone()
        if row is None or action not in [b["action"] for b in json.loads(row["buttons"])]:
            return None
        return row["house_id"], row["key"]

    def pressed(self, finding: int, action: str) -> None:
        """Gone from the page at once. Home Assistant sends what is left."""
        row = self._db.execute("SELECT buttons FROM finding WHERE id = ?", (finding,)).fetchone()
        if row is None:
            return
        buttons = json.loads(row["buttons"])
        stop = any(b["action"] == action and b["title"] == "Stop these" for b in buttons)
        left = [] if stop else [b for b in buttons if b["action"] != action]
        with self._db:
            self._db.execute("UPDATE finding SET buttons = ? WHERE id = ?",
                             (json.dumps(left), finding))

    def _print(self, house_id: str, uid: str, raw: str) -> None:
        """Kept only with history on (E10)."""
        if not self.keep_prints():
            return
        data = json.loads(raw) if len(raw) <= 2000 else None
        if not isinstance(data, dict) or data.get("result") not in ("finished", "failed",
                                                                    "stopped"):
            raise ValueError("bad print")
        start, end = number(data.get("start")), number(data.get("end"))
        if start is None or end is None or not 0 < start <= end <= self._clock() + 60:
            raise ValueError("bad print")
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO print (house_id, uid, printer, file, start, end, result, "
                "whole, progress, weight) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (house_id, uid, _line(data.get("printer"), 60), _line(data.get("file"), 100),
                 start, end, data["result"], int(data.get("whole") is True),
                 number(data.get("progress")), number(data.get("weight"))))

    def prints(self, house_id: str, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self._db.execute(
            "SELECT printer, file, start, end, result, whole, progress, weight FROM print "
            "WHERE house_id = ? ORDER BY end DESC LIMIT ?", (house_id, limit))]

    def forget_prints(self) -> None:
        with self._db:
            self._db.execute("DELETE FROM print")

    def _learned(self, house_id: str, what: str, key: str, raw: object) -> None:
        with self._db:
            if what == "forgot":
                self._db.execute("DELETE FROM learned WHERE house_id = ?", (house_id,))
                return
            kind, _, day = key.partition(":")
            value = json.loads(raw) if isinstance(raw, str) and len(raw) <= 2000 else None
            if (kind not in ("night", "open") or not _DAY.fullmatch(day)
                    or not isinstance(value, list) or len(value) > 200
                    or not all(type(v) is int for v in value)):
                raise ValueError("bad summary")
            self._db.execute("INSERT OR REPLACE INTO learned VALUES (?, ?, ?, ?)",
                             (house_id, kind, day, json.dumps(value)))

    def ignore(self, finding: object, on: bool) -> bool:
        """Only where it is listed. Never changes whether an alert is sent (C3)."""
        if type(finding) is not int:
            return False
        with self._db:
            done = self._db.execute("UPDATE finding SET ignored = ? WHERE id = ?",
                                    (int(on), finding)).rowcount == 1
            if done and on:
                # Counted, so hiding the same thing again and again can become a suggestion.
                self._db.execute("INSERT INTO story (finding, at, what, text) VALUES "
                                 "(?, ?, 'hidden', 'Hidden on the page')",
                                 (finding, self._clock()))
            return done

    def habits(self, house_id: str) -> list[tuple[str, str]]:
        """Findings worth asking about, with why in fixed words: hidden again and again, or
        told often with nothing done. Each is asked about at most once in 30 days."""
        now = self._clock()
        since = now - HABIT_DAYS * 86400
        found = []
        rows = self._db.execute(
            "SELECT id, key FROM finding WHERE house_id = ? AND stopped IS NULL "
            "AND source IN (?, ?, ?) "
            "AND (suggested IS NULL OR suggested < ?) AND last >= ?",
            (house_id, *HABIT_SOURCES, now - ASK_AGAIN, since)).fetchall()
        for row in rows:
            counts = dict(self._db.execute(
                "SELECT what, COUNT(*) FROM story WHERE finding = ? AND at >= ? GROUP BY what",
                (row["id"], since)).fetchall())
            if counts.get("hidden", 0) >= HIDDEN_TIMES:
                found.append((row["key"], f"You hid it {counts['hidden']} times in two weeks."))
            elif counts.get("sent", 0) >= TOLD_TIMES and not any(
                    counts.get(w) for w in ("acked", "stopped", "hidden")):
                found.append((row["key"], f"I told your phone {counts['sent']} times in two "
                                          "weeks and nothing was done about it."))
        return found

    def suggested(self, house_id: str, key: str) -> None:
        with self._db:
            self._db.execute("UPDATE finding SET suggested = ? WHERE house_id = ? AND key = ?",
                             (self._clock(), house_id, key))

    # --- reading ---

    def list(self, which: str, before: float | None = None, house_id: str | None = None,
             limit: int = PAGE) -> list[dict]:
        where = {"open": "is_open = 1 AND ignored = 0", "closed": "is_open = 0 AND ignored = 0",
                 "ignored": "ignored = 1"}[which]
        return [dict(r) for r in self._db.execute(
            f"SELECT * FROM finding WHERE {where} AND (? IS NULL OR last < ?) "  # noqa: S608
            "AND (? IS NULL OR house_id = ?) ORDER BY last DESC LIMIT ?",
            (before, before, house_id, house_id, limit))]

    def story(self, finding: int) -> list[dict]:
        return [dict(r) for r in self._db.execute(
            "SELECT at, what, text FROM story WHERE finding = ? ORDER BY at DESC, id DESC "
            "LIMIT 100", (finding,))]

    def decisions(self, since: float, house_id: str | None = None,
                  limit: int = 12) -> list[dict]:
        """What BRAM told, held back, or was told to stop, newest first, with what it was about."""
        marks = ",".join("?" * len(DECIDED))
        return [dict(r) for r in self._db.execute(
            "SELECT story.at, story.what, story.text, finding.text AS about, finding.source "  # noqa: S608
            "FROM story JOIN finding ON finding.id = story.finding "
            f"WHERE story.what IN ({marks}) AND story.at >= ? "
            "AND (? IS NULL OR finding.house_id = ?) ORDER BY story.at DESC LIMIT ?",
            (*DECIDED, since, house_id, house_id, limit))]

    def sent_since(self, since: float) -> int:
        return self._db.execute("SELECT COUNT(*) FROM story WHERE what = 'sent' AND at >= ?",
                                (since,)).fetchone()[0]

    def learned(self, house_id: str, kind: str | None = None) -> int:
        return self._db.execute(
            "SELECT COUNT(*) FROM learned WHERE house_id = ? AND (? IS NULL OR kind = ?)",
            (house_id, kind, kind)).fetchone()[0]

    def forget_house(self, house_id: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM story WHERE finding IN "
                             "(SELECT id FROM finding WHERE house_id = ?)", (house_id,))
            self._db.execute("DELETE FROM finding WHERE house_id = ?", (house_id,))
            self._db.execute("DELETE FROM learned WHERE house_id = ?", (house_id,))
            self._db.execute("DELETE FROM print WHERE house_id = ?", (house_id,))

    def close(self) -> None:
        self._db.close()
