"""Deciding what to remove from history. The owner confirms an exact list.

A request in chat only makes a list. Nothing goes until that list is confirmed on the page, and
no model removes anything.
"""
from __future__ import annotations

import datetime
import re
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from .findings import Findings
from .history import HOUR, History

# Measured bytes for each row.
BYTES = {"reading": 38, "hourly": 38, "change": 55, "run": 130}
ACTIONS = ("delete", "shorten", "stop", "keep")
PLAN_LIFE = 600
ASK_AT = 0.8
ASK_AGAIN = 30 * 86400
DAY = 86400

REQUEST = re.compile(
    r"\b(delete|purge|erase|clear out|clean up|remove|shorten|stop (keeping|recording|saving)|"
    r"(start|resume) (keeping|recording|saving))\b", re.I)
ABOUT = re.compile(r"\b(history|readings?|data(base)?|db|records?|older|before|keeping|recording|"
                   r"saving|recorded|trends?)\b", re.I)
KIND_WORDS = {"motion": "motion", "door": "opening", "doors": "opening", "window": "opening",
              "windows": "opening", "lights": "light", "temperatures": "temperature",
              "humidity": "humidity", "people": "person", "locks": "lock", "switches": "switch"}
MONTHS = {m: i + 1 for i, m in enumerate((
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december"))}
UNITS = {"day": 1, "week": 7, "month": 30, "year": 365}
COMMON = {"sensor", "the", "a", "my", "of", "in", "from", "before", "all", "history", "delete",
          "purge", "data", "readings", "older", "than", "stop", "keeping", "and", "room"}


@dataclass
class Plan:
    id: str
    action: str
    devices: list[int]
    before: float
    text: str
    rows: dict[str, int]
    bytes: int
    made: float = field(default=0)


class Cleanup:
    def __init__(self, history: History, findings: Findings | None,
                 clock: Callable[[], float] = time.time) -> None:
        self._h, self._findings, self._clock = history, findings, clock
        self._plans: dict[str, Plan] = {}

    @property
    def _db(self) -> sqlite3.Connection:
        return self._h.db

    # --- what takes space ---

    def usage(self) -> list[dict]:
        """Each device and what it uses, biggest first."""
        found: dict[int, dict] = {}
        for row in self._db.execute("SELECT * FROM device"):
            found[row["id"]] = {"id": row["id"], "home": row["house_id"], "name": _named(row),
                                "kind": row["kind"], "area": row["area"], "keep": row["keep"],
                                "rows": 0, "bytes": 0, "first": None}
        for table, size in BYTES.items():
            at = "start" if table == "run" else "at"
            for row in self._db.execute(
                    f"SELECT device, COUNT(*) AS n, MIN({at}) AS first FROM {table} "  # noqa: S608
                    "GROUP BY device"):
                if (entry := found.get(row["device"])) is not None:
                    entry["rows"] += row["n"]
                    entry["bytes"] += row["n"] * size
                    entry["first"] = min(entry["first"] or row["first"], row["first"])
        return sorted(found.values(), key=lambda e: (-e["bytes"], e["name"]))

    # --- plans ---

    def plan(self, action: str, devices: list[int], before: float | None = None) -> Plan:
        """Exactly what would go. Nothing is changed."""
        if action not in ACTIONS:
            raise ValueError("Unknown action")
        marks = ",".join("?" * len(devices))
        rows = self._db.execute(f"SELECT * FROM device WHERE id IN ({marks})",  # noqa: S608
                                devices).fetchall()
        if not rows or len(rows) != len(set(devices)):
            raise ValueError("Choose at least one device")
        now = self._clock()
        # What arrives after this list was made is never part of it.
        until = now if before is None else min(before, now)
        counts = {}
        for table in ("reading",) if action == "shorten" else BYTES:
            if action in ("stop", "keep"):
                break
            at = "start" if table == "run" else "at"
            counts[table] = self._db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE device IN ({marks}) AND {at} < ?",  # noqa: S608
                (*devices, _until(table, until))).fetchone()[0]
        names = sorted(_named(r) for r in rows)
        about = ", ".join(names[:5]) + (f" and {len(names) - 5} more" if len(names) > 5 else "")
        when = "" if before is None else datetime.datetime.fromtimestamp(
            until, datetime.UTC).strftime(" from before %d %B %Y")
        total = sum(counts.values())
        text = {
            "delete": f"Delete {total:,} entries{when} of {about}. Trends from then are lost",
            "shorten": f"Turn {total:,} 5-minute readings{when} of {about} into hourly ones. "
                       "Hourly trends stay",
            "stop": f"Stop keeping {about}. What is already kept stays",
            "keep": f"Keep {about} again"}[action]
        self._plans = {k: p for k, p in self._plans.items() if now - p.made < PLAN_LIFE}
        plan = Plan(secrets.token_hex(8), action, list(devices), until, text, counts,
                    sum(n * BYTES[t] for t, n in counts.items()), now)
        self._plans[plan.id] = plan
        return plan

    def waiting(self) -> list[Plan]:
        now = self._clock()
        return [p for p in self._plans.values() if now - p.made < PLAN_LIFE]

    def drop(self, plan_id: object) -> None:
        self._plans.pop(plan_id if isinstance(plan_id, str) else "", None)

    def apply(self, plan_id: object) -> Plan:
        """Do one confirmed plan, once."""
        plan = self._plans.pop(plan_id if isinstance(plan_id, str) else "", None)
        if plan is None or self._clock() - plan.made >= PLAN_LIFE:
            raise ValueError("That list has expired. Make it again")
        marks = ",".join("?" * len(plan.devices))
        if plan.action in ("stop", "keep"):
            with self._db:
                self._db.execute(f"UPDATE device SET keep = ? WHERE id IN ({marks})",  # noqa: S608
                                 (int(plan.action == "keep"), *plan.devices))
            self._h.reload()
            return plan
        with self._db:
            if plan.action == "shorten":
                # Any hour not already kept is kept before its detail goes.
                self._db.execute(
                    "INSERT OR IGNORE INTO hourly SELECT device, at / 3600 * 3600, MIN(lo), "  # noqa: S608
                    f"ROUND(AVG(avg), 3), MAX(hi) FROM reading WHERE device IN ({marks}) "
                    "AND at < ? GROUP BY device, at / 3600",
                    (*plan.devices, _until("reading", plan.before)))
            for table in plan.rows:
                at = "start" if table == "run" else "at"
                self._db.execute(
                    f"DELETE FROM {table} WHERE device IN ({marks}) AND {at} < ?",  # noqa: S608
                    (*plan.devices, _until(table, plan.before)))
        self._h.reload()
        return plan

    # --- asking the owner ---

    def should_ask(self) -> str | None:
        """Text to send once when space is running low, or None."""
        share = self._h.size() / max(1, self._h.limit * 1_000_000)
        if share < ASK_AT or self._clock() < (self._h.meta("ask_after") or 0):
            return None
        big = [f"{e['name']} {e['bytes'] / 1e6:.0f} MB" for e in self.usage()[:3]]
        return (f"BRAM's history is {share * 100:.0f}% full. Biggest: {', '.join(big)}. "
                "Choose what to remove under History on BRAM's page.")

    def ask_later(self) -> None:
        self._h.set_meta("ask_after", self._clock() + ASK_AGAIN)

    # --- requests in words ---

    def request(self, text: str, zone: ZoneInfo, house: str | None = None) -> Plan | str | None:
        """A list for what was asked, why it cannot be made, or None if nothing was asked."""
        if not REQUEST.search(text) or not ABOUT.search(text):
            return None
        low = text.lower()
        action = ("keep" if re.search(r"\b(start|resume) (keeping|recording|saving)\b", low)
                  else "stop" if re.search(r"\bstop (keeping|recording|saving)\b", low)
                  else "shorten" if "shorten" in low else "delete")
        try:
            before = _before(low, zone, self._clock())
        except ValueError:
            before = None
        if before is None and re.search(r"\b(before|older|since|after|last|between)\b", low):
            return "I could not tell which dates you meant"
        devices = self._devices(low, house)
        if not devices:
            return "I could not tell which devices you meant"
        return self.plan(action, devices, before)

    def _devices(self, low: str, house: str | None) -> list[int]:
        words = set(re.findall(r"[a-z0-9]+", low)) - COMMON
        rows = [r for r in self._db.execute("SELECT * FROM device")
                if house in (None, r["house_id"])]
        named = [r["id"] for r in rows
                 if (about := set(re.findall(r"[a-z0-9]+", _named(r).lower())) - COMMON)
                 and about <= words]
        if named:
            return named
        kinds = {KIND_WORDS[w] for w in words if w in KIND_WORDS}
        # A kind alone only if nothing else might narrow it, such as a room.
        areas = {r["area"].lower() for r in rows if r["area"] and r["area"].lower() in low}
        return [r["id"] for r in rows if r["kind"] in kinds
                and (not areas or r["area"].lower() in areas)]


def _until(table: str, at: float) -> float:
    """Readings go by whole hours, so no hour is ever worked out from part of itself."""
    return at // HOUR * HOUR if table in ("reading", "hourly") else at


def _named(row: sqlite3.Row) -> str:
    return row["name"] + (" humidity" if row["metric"] == "humidity" else
                          " temperature" if row["metric"] == "now" else "")


def _before(low: str, zone: ZoneInfo, now: float) -> float | None:
    if match := re.search(
            r"\bolder than (\d{1,4}|a|an|one|two|three|six) (day|week|month|year)s?\b", low):
        words = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "six": 6}
        count = words.get(match[1]) or int(match[1])
        return now - count * UNITS[match[2]] * DAY
    today = datetime.datetime.fromtimestamp(now, zone)
    if match := re.search(r"\bbefore (\d{4})-(\d{2})-(\d{2})\b", low):
        return datetime.datetime(int(match[1]), int(match[2]), int(match[3]),
                                 tzinfo=zone).timestamp()
    if match := re.search(
            rf"\bbefore ({'|'.join(MONTHS)})(?: (\d{{1,2}}))?(?:,? (\d{{4}}))?\b", low):
        month, day = MONTHS[match[1]], int(match[2] or 1)
        year = int(match[3] or today.year)
        at = datetime.datetime(year, month, day, tzinfo=zone)
        if match[3] is None and at > today:
            at = at.replace(year=year - 1)
        return at.timestamp()
    return None
