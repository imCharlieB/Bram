"""Memory: what people asked BRAM to remember, and where a conversation left off.

Optional, and off until the owner turns it on (E10). With it off, nothing here is written.
People can see, correct, and delete every memory (E7). A memory is told by a person and kept
as a told fact, apart from anything BRAM only guessed (B3). Its words are data for the
model, never instructions (D1).
"""
from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_TEXT = 300
MAX_MEMORIES = 500
CHAT_KEEP = 7 * 86400  # a conversation not touched for a week is let go
CHAT_MESSAGES = 12
STOP = {"the", "a", "an", "is", "are", "my", "our", "of", "to", "and", "that", "this", "what",
        "who", "when", "where", "do", "you", "i", "me", "it", "in", "on", "at", "for", "about"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT, person TEXT NOT NULL, kind TEXT NOT NULL,
    text TEXT NOT NULL, source TEXT NOT NULL, at REAL NOT NULL, changed REAL NOT NULL);
CREATE TABLE IF NOT EXISTS talk (
    person TEXT NOT NULL, n INTEGER NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
    at REAL NOT NULL, PRIMARY KEY (person, n));
"""


def clean(text: object, limit: int = MAX_TEXT) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())[:limit]


def words(text: str) -> set[str]:
    """The words that matter, so the neighbor's name matches the neighbor."""
    found = set()
    for word in re.findall(r"[a-z0-9']+", text.lower()):
        word = re.sub(r"'s$", "", word).strip("'")
        if word not in STOP and len(word) > 1:
            found.add(word)
    return found


class Memory:
    def __init__(self, path: Path | str, on: Callable[[], bool],
                 clock: Callable[[], float] = time.time) -> None:
        self._on, self._clock = on, clock
        self._db = sqlite3.connect(path, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    @property
    def on(self) -> bool:
        return bool(self._on())

    # --- told facts ---

    def add(self, person: str, text: object, source: str) -> dict[str, Any] | None:
        """Keep something a person asked BRAM to remember. Nothing if memory is off (E10)."""
        text = clean(text)
        if not self.on or not text:
            return None
        now = self._clock()
        with self._db:
            same = self._db.execute("SELECT id FROM memory WHERE person = ? AND lower(text) = ?",
                                    (person, text.lower())).fetchone()
            if same:
                return self.get(same["id"])
            found = self._db.execute(
                "INSERT INTO memory (person, kind, text, source, at, changed) "
                "VALUES (?, 'told', ?, ?, ?, ?) RETURNING id",
                (person, text, source, now, now)).fetchone()[0]
            over = self._db.execute("SELECT COUNT(*) FROM memory").fetchone()[0] - MAX_MEMORIES
            if over > 0:  # the oldest go first
                self._db.execute("DELETE FROM memory WHERE id IN (SELECT id FROM memory "
                                 "ORDER BY changed LIMIT ?)", (over,))
        return self.get(found)

    def get(self, memory_id: object) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM memory WHERE id = ?", (memory_id,)).fetchone()
        return dict(row) if row else None

    def all(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._db.execute("SELECT * FROM memory ORDER BY changed DESC")]

    def correct(self, memory_id: object, text: object) -> dict[str, Any] | None:
        """A person changes what was remembered (E7)."""
        text = clean(text)
        if not text or self.get(memory_id) is None:
            return None
        with self._db:
            self._db.execute("UPDATE memory SET text = ?, changed = ? WHERE id = ?",
                             (text, self._clock(), memory_id))
        return self.get(memory_id)

    def delete(self, memory_id: object) -> bool:
        with self._db:
            return self._db.execute("DELETE FROM memory WHERE id = ?",
                                    (memory_id,)).rowcount == 1

    def forget(self, about: str) -> list[str]:
        """Forget every memory that has all the words asked about. What was forgotten."""
        wanted = words(about)
        if not wanted:
            return []
        gone = [m for m in self.all() if wanted <= words(m["text"])]
        with self._db:
            self._db.executemany("DELETE FROM memory WHERE id = ?", [(m["id"],) for m in gone])
        return [m["text"] for m in gone]

    def relevant(self, question: str, limit: int = 20) -> list[dict[str, Any]]:
        """Memories for a question: those sharing its words first, then the newest."""
        if not self.on:
            return []
        asked = words(question)
        found = self.all()
        found.sort(key=lambda m: (-len(asked & words(m["text"])), -m["changed"]))
        return found[:limit]

    # --- where a conversation left off ---

    def load(self, person: str) -> list[tuple[str, str]]:
        if not self.on:
            return []
        rows = self._db.execute("SELECT role, text, at FROM talk WHERE person = ? ORDER BY n",
                                (person,)).fetchall()
        if rows and self._clock() - rows[-1]["at"] > CHAT_KEEP:
            self.clear_talk(person)
            return []
        return [(r["role"], r["text"]) for r in rows]

    def save(self, person: str, messages: list[tuple[str, str]]) -> None:
        """Where the conversation is now. Nothing if memory is off (E10)."""
        if not self.on:
            return
        now = self._clock()
        with self._db:
            self._db.execute("DELETE FROM talk WHERE person = ?", (person,))
            self._db.executemany("INSERT INTO talk VALUES (?, ?, ?, ?, ?)", [
                (person, n, role, text[:4000], now)
                for n, (role, text) in enumerate(messages[-CHAT_MESSAGES:])])

    def clear_talk(self, person: str | None = None) -> None:
        with self._db:
            if person is None:
                self._db.execute("DELETE FROM talk")
            else:
                self._db.execute("DELETE FROM talk WHERE person = ?", (person,))

    def people(self) -> list[str]:
        """Everyone memory holds something for."""
        rows = self._db.execute("SELECT person FROM memory UNION SELECT person FROM talk")
        return sorted({r[0] for r in rows}, key=str.casefold)

    def forget_person(self, person: str) -> int:
        """Everything kept for one person, when they opt out (E10)."""
        with self._db:
            gone = self._db.execute("DELETE FROM memory WHERE person = ?", (person,)).rowcount
            self._db.execute("DELETE FROM talk WHERE person = ?", (person,))
        return gone

    def forget_everything(self) -> None:
        with self._db:
            self._db.execute("DELETE FROM memory")
            self._db.execute("DELETE FROM talk")

    def close(self) -> None:
        self._db.close()
