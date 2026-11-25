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
WHATS = ("open", "closed", "sent", "not sent", "acked", "stopped", "snoozed")
PAGE = 50
OLDEST = 30 * 86400
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

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
                        "UPDATE finding SET is_open = 1, last = ?, times = times + 1, text = ?, "
                        "severity = ?, acked = NULL, closed = NULL WHERE id = ?",
                        (at, text, severity, finding))
                elif what == "closed" and not row["is_open"]:
                    return
            column = {"sent": "told", "acked": "acked", "stopped": "stopped",
                      "closed": "closed"}.get(what)
            if column:
                self._db.execute(f"UPDATE finding SET {column} = ?, last = MAX(last, ?) "  # noqa: S608
                                 "WHERE id = ?", (at, at, finding))
            if what == "closed":
                self._db.execute("UPDATE finding SET is_open = 0 WHERE id = ?", (finding,))
            self._db.execute("INSERT INTO story (finding, uid, at, what, text) "
                             "VALUES (?, ?, ?, ?, ?)", (finding, uid, at, what, text))

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
            return self._db.execute("UPDATE finding SET ignored = ? WHERE id = ?",
                                    (int(on), finding)).rowcount == 1

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
