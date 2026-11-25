"""Owner settings and the config page login."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any

MIN_PASSWORD, MAX_PASSWORD = 12, 200
DEFAULTS: dict[str, Any] = {
    "model_url": "", "model": "", "context": 8192, "personality": "professional",
    "custom_style": "", "timezone": "",
}


class Settings:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(path, timeout=10)
        with self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def _get(self, key: str) -> Any:
        row = self._db.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _set(self, values: dict[str, Any]) -> None:
        with self._db:
            self._db.executemany("INSERT OR REPLACE INTO setting VALUES (?, ?)",
                                 [(k, json.dumps(v)) for k, v in values.items()])

    def all(self) -> dict[str, Any]:
        return {k: default if (v := self._get(k)) is None else v
                for k, default in DEFAULTS.items()}

    def update(self, values: dict[str, Any]) -> None:
        if not values.keys() <= DEFAULTS.keys():
            raise ValueError("unknown setting")
        self._set(values)

    def channel(self, name: str) -> dict[str, Any]:
        """Private channel settings. Never returned whole by the config page."""
        return self._get(f"_channel_{name}") or {}

    def update_channel(self, name: str, values: dict[str, Any]) -> None:
        self._set({f"_channel_{name}": {**self.channel(name), **values}})

    def login_record(self) -> str | None:
        return self._get("_login")

    def create_login(self, user: str, password: str) -> bool:
        """Create the owner's login. False if one already exists."""
        record = self._make(user, password)
        with self._db:
            return self._db.execute("INSERT OR IGNORE INTO setting VALUES ('_login', ?)",
                                    (record,)).rowcount == 1

    def change_login(self, user: str, password: str) -> None:
        record = self._make(user, password)
        with self._db:
            self._db.execute("UPDATE setting SET value = ? WHERE key = '_login'", (record,))

    @staticmethod
    def _make(user: str, password: str) -> str:
        user = user.strip()
        if not 1 <= len(user) <= 64:
            raise ValueError("Enter a username of up to 64 characters")
        if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise ValueError(f"Use a password of at least {MIN_PASSWORD} characters")
        salt = secrets.token_bytes(16)
        record = json.dumps([user, salt.hex(), _scrypt(password, salt)])
        return json.dumps(record)

    def reset_login(self) -> None:
        with self._db:
            self._db.execute("DELETE FROM setting WHERE key IN ('_login', '_factor')")

    def factor(self) -> dict[str, Any] | None:
        """The second factor. Never returned by the config page."""
        return self._get("_factor")

    def set_factor(self, record: dict[str, Any] | None) -> None:
        self._set({"_factor": record})

    def close(self) -> None:
        self._db.close()


def owner_name(record: str) -> str:
    return json.loads(record)[0]


def _scrypt(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1,
                          maxmem=64 * 1024 * 1024).hex()


def login_matches(record: str | None, user: str, password: str) -> bool:
    if record is None or len(password) > MAX_PASSWORD:
        return False
    owner, salt, expected = json.loads(record)
    # Check the password even when the username is wrong, so both take the same time.
    right = hmac.compare_digest(_scrypt(password, bytes.fromhex(salt)), expected)
    return right and user.strip().casefold() == owner.casefold()
