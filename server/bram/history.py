"""What shared devices did, if the owner turns it on (E10). Code measures; no model writes here.

Unknown is never recorded as a value (B2). Everything belongs to one house (E4).
"""
from __future__ import annotations

import datetime
import math
import sqlite3
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from zoneinfo import ZoneInfo

from .world import MEANING, UNUSABLE, Event, World

SLOT, HOUR = 300, 3600
GAP = 180  # a longer silence means we cannot say what happened in between
RUNNING = ("heating", "cooling", "drying", "fan", "preheating", "defrosting")
SETTINGS = ("action", "mode", "preset", "fan", "target", "low", "high")
DEFAULT_LIMIT = 2048

_SCHEMA = """
CREATE TABLE IF NOT EXISTS device (
    id INTEGER PRIMARY KEY, house_id TEXT NOT NULL, entity_id TEXT NOT NULL,
    metric TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, area TEXT NOT NULL,
    unit TEXT NOT NULL, imported INTEGER NOT NULL DEFAULT 0,
    UNIQUE (house_id, entity_id, metric));
CREATE TABLE IF NOT EXISTS reading (
    device INTEGER NOT NULL, at INTEGER NOT NULL, lo REAL, avg REAL, hi REAL,
    PRIMARY KEY (device, at)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS hourly (
    device INTEGER NOT NULL, at INTEGER NOT NULL, lo REAL, avg REAL, hi REAL,
    PRIMARY KEY (device, at)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS change (
    device INTEGER NOT NULL, at REAL NOT NULL, state TEXT NOT NULL,
    PRIMARY KEY (device, at)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY, device INTEGER NOT NULL, start REAL NOT NULL, end REAL,
    seen REAL NOT NULL, cut INTEGER NOT NULL DEFAULT 0,
    action TEXT, mode TEXT, preset TEXT, fan TEXT, target REAL, low REAL, high REAL,
    inside0 REAL, inside1 REAL, outside0 REAL, outside1 REAL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value REAL);
CREATE INDEX IF NOT EXISTS run_device ON run (device, start);
"""
TABLES = ("reading", "hourly", "change", "run")


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and abs(value) < 1e12 else None


class History:
    def __init__(self, path: Path | str, on: Callable[[], bool],
                 limit_mb: Callable[[], int] = lambda: DEFAULT_LIMIT,
                 clock: Callable[[], float] = time.time) -> None:
        self._db = sqlite3.connect(path, timeout=10)
        self._db.row_factory = sqlite3.Row
        # A snapshot of the volume taken while this is running can be recovered.
        self._db.execute("PRAGMA journal_mode=WAL")
        self.healthy = self._db.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"
        self._db.executescript(_SCHEMA)
        if "keep" not in [r[1] for r in self._db.execute("PRAGMA table_info(device)")]:
            with self._db:
                self._db.execute("ALTER TABLE device ADD COLUMN keep INTEGER NOT NULL DEFAULT 1")
        self._on, self._limit_mb, self._clock = on, limit_mb, clock
        self._dropped: set[tuple[str, str, str]] = set()
        self.reload()
        self._ids: dict[tuple[str, str, str], tuple[int, tuple]] = {}
        self._slots: dict[tuple[int, int], list[float]] = {}
        self._last: dict[int, str] = {}
        self._rolled = 0
        alive = self._db.execute("SELECT value FROM meta WHERE key = 'alive'").fetchone()
        if alive is not None:
            # While the server was down, nothing is known (B2).
            self._unknown(alive[0])
        self.shortened = False

    @property
    def on(self) -> bool:
        return self._on()

    @property
    def db(self) -> sqlite3.Connection:
        return self._db

    @property
    def limit(self) -> int:
        return self._limit_mb()

    def meta(self, key: str) -> float | None:
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: float) -> None:
        with self._db:
            self._db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def reload(self) -> None:
        """After something was removed, or what to keep was changed."""
        self._dropped = {tuple(r) for r in self._db.execute(
            "SELECT house_id, entity_id, metric FROM device WHERE keep = 0")}
        self._last = {}

    # --- writing ---

    def _device(self, event: Event, metric: str = "", unit: str = "") -> int:
        key = (event.house_id, event.entity_id, metric)
        about = (event.name or event.entity_id, event.kind, event.detail.get("area", ""), unit)
        known = self._ids.get(key)
        if known is None or known[1] != about:
            with self._db:
                self._db.execute(
                    "INSERT INTO device (house_id, entity_id, metric, name, kind, area, unit) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (house_id, entity_id, metric) "
                    "DO UPDATE SET name = excluded.name, kind = excluded.kind, "
                    "area = excluded.area, unit = excluded.unit", (*key, *about))
            row = self._db.execute(
                "SELECT id FROM device WHERE house_id = ? AND entity_id = ? AND metric = ?",
                key).fetchone()
            known = self._ids[key] = (row[0], about)
        return known[0]

    def record(self, event: Event, world: World) -> None:
        """Something changed, or was seen again after a reconnect."""
        if not self.on or (event.house_id, event.entity_id, "") in self._dropped:
            return
        if event.kind == "climate":
            self._climate(event, world)
        elif event.kind in MEANING:
            device = self._device(event)
            state = str(world.check(event.entity_id))
            if device not in self._last:
                row = self._db.execute("SELECT state FROM change WHERE device = ? "
                                       "ORDER BY at DESC LIMIT 1", (device,)).fetchone()
                self._last[device] = row[0] if row else ""
            if self._last[device] != state:
                self._last[device] = state
                with self._db:
                    self._db.execute("INSERT OR REPLACE INTO change VALUES (?, ?, ?)",
                                     (device, self._clock(), state))

    def _unknown(self, at: float, house_id: str | None = None) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO change SELECT device, ?, 'unknown' FROM change JOIN device "
                "ON device.id = change.device WHERE (? IS NULL OR house_id = ?) "
                "GROUP BY change.device HAVING MAX(at) < ? AND state != 'unknown'",
                (at, house_id, house_id, at))

    def lost(self, house_id: str) -> None:
        """The connection dropped, so nothing is known from here on (B2)."""
        if self.on:
            self._unknown(self._clock(), house_id)
            self._last.clear()

    def _climate(self, event: Event, world: World) -> None:
        now, values = self._clock(), event.detail.get("values", {})
        device = self._device(event)
        unknown = event.state.lower() in UNUSABLE
        settings = tuple(values.get(k) for k in SETTINGS)
        running = not unknown and values.get("action") in RUNNING
        inside, outside = number(values.get("now")), self._outside(world)
        for row in self._db.execute("SELECT * FROM run WHERE device = ? AND end IS NULL",
                                    (device,)).fetchall():
            silent = now - row["seen"] > GAP
            if running and not silent and tuple(row[k] for k in SETTINGS) == settings:
                with self._db:
                    self._db.execute("UPDATE run SET seen = ?, inside1 = ?, outside1 = ?, "
                                     "outside0 = COALESCE(outside0, ?) WHERE id = ?",
                                     (now, inside, outside, outside, row["id"]))
                return
            with self._db:
                self._db.execute(
                    "UPDATE run SET end = ?, cut = ?, inside1 = COALESCE(?, inside1), "
                    "outside1 = COALESCE(?, outside1) WHERE id = ?",
                    (row["seen"] if silent else now, int(silent or unknown),
                     None if silent else inside, None if silent else outside, row["id"]))
        if running:
            with self._db:
                self._db.execute(
                    f"INSERT INTO run (device, start, seen, {', '.join(SETTINGS)}, inside0, "  # noqa: S608
                    f"inside1, outside0, outside1) VALUES ({', '.join('?' * 14)})",
                    (device, now, now, *settings, inside, inside, outside, outside))

    @staticmethod
    def _outside(world: World) -> float | None:
        for event in world.all():
            if (event.entity_id.startswith("weather.") and world.live
                    and event.state.lower() not in UNUSABLE):
                return number(event.detail.get("values", {}).get("now"))
        return None

    def sample(self, worlds: Iterable[World]) -> None:
        """Once a minute: every live reading, so quiet sensors count as much as busy ones."""
        if not self.on:
            return
        now = self._clock()
        slot = int(now // SLOT) * SLOT
        with self._db:
            self._db.execute("INSERT OR REPLACE INTO meta VALUES ('alive', ?)", (now,))
        for world in worlds:
            if not world.live:
                continue
            for event in world.all():
                values = event.detail.get("values")
                if not values or event.state.lower() in UNUSABLE:
                    continue
                for key, metric, unit in (("now", "", values.get("unit", "")),
                                          ("humidity", "humidity", "%")):
                    if (value := number(values.get(key))) is None:
                        continue
                    # A climate device's own row is for its runs.
                    name = metric or ("now" if event.kind == "climate" else "")
                    if (event.house_id, event.entity_id, name) in self._dropped:
                        continue
                    kept = self._slots.setdefault(
                        (self._device(event, name, unit), slot), [value, 0.0, value, 0])
                    kept[0], kept[2] = min(kept[0], value), max(kept[2], value)
                    kept[1] += value
                    kept[3] += 1
                if (event.kind == "climate"
                        and (event.house_id, event.entity_id, "") not in self._dropped):
                    self._climate(event, world)
        self.flush(slot)

    def flush(self, before: float = math.inf) -> None:
        done = [k for k in self._slots if k[1] < before]
        with self._db:
            for key in done:
                lo, total, hi, count = self._slots.pop(key)
                self._db.execute("INSERT OR REPLACE INTO reading VALUES (?, ?, ?, ?, ?)",
                                 (*key, round(lo, 3), round(total / count, 3), round(hi, 3)))
        hour = int(self._clock() // HOUR) * HOUR
        if done and hour != self._rolled:
            since = hour - (3 if self._rolled else 168) * HOUR
            self._rolled = hour
            with self._db:
                self._db.execute(
                    "INSERT OR REPLACE INTO hourly SELECT device, at / 3600 * 3600, MIN(lo), "
                    "ROUND(AVG(avg), 3), MAX(hi) FROM reading WHERE at >= ? AND at < ? "
                    "GROUP BY device, at / 3600", (since, hour))
            self._fit()

    def _fit(self) -> None:
        """At the limit, the oldest 5-minute readings give way. Their hours are already kept."""
        while self.size() > self._limit_mb() * 1_000_000:
            row = self._db.execute("SELECT MIN(at) FROM reading").fetchone()
            hour = int(self._clock() // HOUR) * HOUR
            if row[0] is None or row[0] >= hour - 24 * HOUR:
                return
            with self._db:
                self._db.execute("DELETE FROM reading WHERE at < ?",
                                 (min(row[0] // HOUR * HOUR + 86400, hour - 24 * HOUR),))
            self.shortened = True

    # --- past readings from Home Assistant ---

    def to_import(self, house_id: str) -> list[tuple[int, str]]:
        if not self.on:
            return []
        return [(r["id"], r["entity_id"]) for r in self._db.execute(
            "SELECT id, entity_id FROM device WHERE house_id = ? AND metric = '' "
            "AND imported = 0 AND entity_id LIKE 'sensor.%' AND unit != ''", (house_id,))]

    def add_past(self, device: int, rows: object) -> int:
        kept = []
        for row in rows if isinstance(rows, list) else []:
            values = [number(v) for v in row] if isinstance(row, list) and len(row) == 4 else [None]
            if None not in values and 0 < values[0] <= self._clock():
                kept.append((device, int(values[0] // HOUR) * HOUR, *values[1:]))
        with self._db:
            # What BRAM measured itself is never replaced.
            self._db.executemany("INSERT OR IGNORE INTO hourly VALUES (?, ?, ?, ?, ?)", kept)
        return len(kept)

    def imported(self, device: int) -> None:
        with self._db:
            self._db.execute("UPDATE device SET imported = 1 WHERE id = ?", (device,))

    # --- reading ---

    def size(self) -> int:
        pages, free, each = (self._db.execute(f"PRAGMA {p}").fetchone()[0]
                             for p in ("page_count", "freelist_count", "page_size"))
        return (pages - free) * each

    def summary(self) -> dict:
        counts = {t: self._db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
                  for t in TABLES}
        return {"on": self.on, "size": self.size(), "limit_mb": self._limit_mb(),
                "healthy": self.healthy, "shortened": self.shortened, "counts": counts}

    def climate_days(self, house_id: str, days: int, zone: ZoneInfo) -> list[dict]:
        """Run time and settings for each device and day, newest first."""
        now = self._clock()
        today = datetime.datetime.fromtimestamp(now, zone).date()
        first = today - datetime.timedelta(days=days - 1)
        begin = datetime.datetime.combine(first, datetime.time(), zone).timestamp()
        found: dict[tuple, dict] = {}
        for row in self._db.execute(
                "SELECT run.*, device.name, device.area FROM run JOIN device ON device.id = device "
                "WHERE house_id = ? AND COALESCE(end, seen) > ? ORDER BY start",
                (house_id, begin)):
            at, stop = max(row["start"], begin), row["end"] or row["seen"]
            while at < stop:
                day = datetime.datetime.fromtimestamp(at, zone).date()
                midnight = datetime.datetime.combine(
                    day + datetime.timedelta(days=1), datetime.time(), zone).timestamp()
                part = min(stop, midnight) - at
                entry = found.setdefault((day, row["device"]), {
                    "day": day.isoformat(), "name": row["name"], "area": row["area"],
                    "seconds": {}, "targets": {}, "starts": 0, "cut": False, "outside": []})
                action = row["action"]
                entry["seconds"][action] = entry["seconds"].get(action, 0) + part
                target = _setting(row)
                entry["targets"][target] = entry["targets"].get(target, 0) + part
                entry["starts"] += at == row["start"]
                entry["cut"] |= bool(row["cut"])
                entry["outside"] += [v for v in (row["outside0"], row["outside1"])
                                     if v is not None]
                at = midnight
        for entry in found.values():
            degrees = entry.pop("outside")
            entry["outside"] = round(sum(degrees) / len(degrees), 1) if degrees else None
        return [found[k] for k in sorted(found, key=lambda k: (-k[0].toordinal(), k[1]))]

    def series(self, house_id: str, hours: int = 24) -> list[dict]:
        """Each hour: outside, and the average of the temperature sensors inside."""
        start = (int(self._clock() // HOUR) - hours + 1) * HOUR
        rows = self._db.execute(
            "SELECT r.at / 3600 * 3600 AS hour, d.entity_id, d.kind, AVG(r.avg) AS value "
            "FROM reading r JOIN device d ON d.id = r.device WHERE d.house_id = ? AND r.at >= ? "
            "AND d.metric = '' AND (d.kind = 'temperature' OR d.entity_id LIKE 'weather.%') "
            "GROUP BY hour, d.id", (house_id, start)).fetchall()
        found: dict[int, dict] = {start + i * HOUR: {"at": start + i * HOUR, "outside": None,
                                                     "inside": []} for i in range(hours)}
        for row in rows:
            if (slot := found.get(row["hour"])) is None:
                continue
            if row["entity_id"].startswith("weather."):
                slot["outside"] = round(row["value"], 1)
            else:
                slot["inside"].append(row["value"])
        return [{"at": s["at"], "outside": s["outside"],
                 "inside": round(sum(s["inside"]) / len(s["inside"]), 1) if s["inside"] else None}
                for s in found.values()]

    def compare(self, house_id: str, days: int = 7) -> list[dict]:
        """Each thermostat against the other temperature sensors in its room."""
        since = self._clock() - days * 86400
        return [dict(r) for r in self._db.execute(
            "SELECT a.area, a.name AS climate, b.name AS sensor, b.unit, COUNT(*) AS samples, "
            "ROUND(AVG(x.avg), 1) AS climate_avg, ROUND(AVG(y.avg), 1) AS sensor_avg, "
            "ROUND(AVG(y.avg - x.avg), 1) AS apart, "
            "ROUND(MAX(ABS(y.avg - x.avg)), 1) AS most "
            "FROM device a JOIN device b ON b.house_id = a.house_id AND b.area = a.area "
            "AND b.kind = 'temperature' AND b.metric = '' AND b.unit = a.unit "
            "JOIN reading x ON x.device = a.id JOIN reading y ON y.device = b.id AND y.at = x.at "
            "WHERE a.house_id = ? AND a.kind = 'climate' AND a.metric = 'now' AND a.area != '' "
            "AND x.at >= ? GROUP BY a.id, b.id ORDER BY a.area", (house_id, since))]

    # --- forgetting ---

    def forget(self, house_id: str | None = None) -> None:
        where, values = ("WHERE house_id = ?", (house_id,)) if house_id else ("", ())
        self._slots.clear()
        with self._db:
            for table in TABLES:
                self._db.execute(f"DELETE FROM {table} WHERE device IN "  # noqa: S608
                                 f"(SELECT id FROM device {where})", values)
            self._db.execute(f"DELETE FROM device {where}", values)  # noqa: S608
        self._ids.clear()
        self.reload()
        self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self) -> None:
        if self.on:
            self.flush()
        self._db.close()


def _setting(row: sqlite3.Row) -> str:
    if row["target"] is not None:
        return f"{row['target']:g}"
    if row["low"] is not None and row["high"] is not None:
        return f"{row['low']:g} to {row['high']:g}"
    return "not reported"
