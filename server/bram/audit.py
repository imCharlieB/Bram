"""Append-only audit log. It has no field for conversation text (E10)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL, house_id TEXT NOT NULL, trigger TEXT NOT NULL,
    decision TEXT NOT NULL, reason TEXT NOT NULL, approver TEXT, result TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
    BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
    BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""

KINDS = {
    "say": "decision IN ('would_say', 'noticed', 'alert', 'notice', 'cleared')",
    "message": ("decision IN ('sent', 'send failed', 'ack', 'snooze', 'mute', 'muted',"
                " 'daily limit')"),
    "connection": "trigger IN ('feed', 'pairing')",
    "security": "trigger = 'config page'",
}


class Audit:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    def record(self, house_id: str, trigger: str, decision: str, reason: str, result: str,
               approver: str | None = None) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO audit (at, house_id, trigger, decision, reason, approver, result)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), house_id, trigger, decision, reason, approver, result))

    def entries(self, house_id: str) -> list[dict]:
        rows = self._db.execute("SELECT * FROM audit WHERE house_id = ? ORDER BY id", (house_id,))
        return [dict(r) for r in rows]

    def recent(self, limit: int, before: int | None = None, kind: str = "") -> list[dict]:
        """Newest first. kind is a key of KINDS, or empty for everything."""
        where, values = [], []
        if before is not None:
            where.append("id < ?")
            values.append(before)
        if kind:
            where.append(KINDS[kind])
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        # Only fixed text from this file is put into the query.
        rows = self._db.execute(f"SELECT * FROM audit{clause} ORDER BY id DESC LIMIT ?",  # noqa: S608
                                (*values, limit))
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._db.close()
