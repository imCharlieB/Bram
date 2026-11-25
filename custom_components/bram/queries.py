"""The only questions the server may ask. Both read, both are off by default.

Problems are cleaned here, before anything leaves Home Assistant. Log text is data.
"""
from __future__ import annotations

import datetime
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from .const import CONF_ENTITIES, CONF_HISTORY, CONF_PROBLEMS, MEANING

DAYS = 10
MAX_CHANGES = 20
MAX_ERRORS = 12
MAX_NAMES = 10
LOW_BATTERY = 15

_REMOVE = [
    (re.compile(r"[a-z][a-z0-9+.-]*://\S+", re.I), "[address]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    # name value
    (re.compile(r"(?i)\b(bearer|basic|token|password|passwd|pwd|secret|user|username|pin|account)\b"
                r"\s+(?![:=])['\"]?[^\s,'\"}]+"), r"\1 [removed]"),
    # name=value, name: value, "name": "value", whatever surrounds the telling word
    (re.compile(r"(?i)([\w-]*(?:pass|pwd|token|secret|key|auth|cred|cookie|session|pin|code|user|"
                r"login|account|email|signature)[\w-]*)(['\"]?\s*[:=]\s*)(?:['\"][^'\"]*['\"]?|"
                r"[^\s,}\])]+(?:\s+(?=\S{12,})\S+)?)"), r"\1 [removed]"),
    (re.compile(r"\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", re.I), "[device]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "[address]"),
    (re.compile(r"(?<![\w:])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])", re.I), "[address]"),
    (re.compile(r"-?\b\d{1,3}\.\d{3,}\b"), "[number]"),
    (re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:local|lan|home|com|net|org|io|internal)\b", re.I),
     "[address]"),
    (re.compile(r"(?:/[\w.-]+){2,}|[A-Z]:\\\S+"), "[path]"),
    (re.compile(r"\b(?=\w*\d)[\w-]{16,}\b"), "[removed]"),
    (re.compile(r"\+?\d[\d ()-]{8,}\d"), "[number]"),
]


def clean(text: object) -> str:
    """One short line with addresses, names of accounts, and secrets taken out."""
    line = str(text).strip().splitlines()[0] if str(text).strip() else ""
    for pattern, put in _REMOVE:
        line = pattern.sub(put, line)
    return " ".join("".join(c if c.isprintable() else " " for c in line).split())[:160]


async def answer(hass: HomeAssistant, entry: ConfigEntry, kinds: dict[str, str],
                 what: object, entity_id: object) -> dict[str, Any]:
    if what == "problems":
        return problems(hass) if entry.options.get(CONF_PROBLEMS) else {"error": "off"}
    if what == "history":
        if not entry.options.get(CONF_HISTORY):
            return {"error": "off"}
        if entity_id not in entry.options.get(CONF_ENTITIES, []):
            return {"error": "refused"}
        return await history(hass, entity_id, kinds.get(entity_id, ""))
    return {"error": "refused"}


def problems(hass: HomeAssistant) -> dict[str, Any]:
    errors = []
    log = hass.data.get("system_log")
    for item in (log.records.to_list() if log is not None else []):
        if item.get("level") not in ("ERROR", "CRITICAL", "WARNING"):
            continue
        messages = item.get("message") or [""]
        errors.append({
            "from": clean(str(item.get("name", "")).removeprefix("homeassistant.").removeprefix(
                "components.").removeprefix("custom_components.").split(":")[0]),
            "level": item["level"].lower(), "times": int(item.get("count", 1)),
            "first": _when(item.get("first_occurred")), "last": _when(item.get("timestamp")),
            "text": clean(messages[-1])})
    errors.sort(key=lambda e: (e["level"] == "warning", -e["times"]))
    failed = sorted({e.domain for e in hass.config_entries.async_entries() if e.state in (
        ConfigEntryState.SETUP_ERROR, ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR, ConfigEntryState.FAILED_UNLOAD)})
    repairs = sorted({f"{i.domain}: {i.translation_key}" for i in
                      ir.async_get(hass).issues.values()
                      if i.active and i.dismissed_version is None and i.translation_key})
    states = hass.states.async_all()
    low = [f"{clean(s.name)} {s.state}%" for s in states if _low(s)]
    updates = [clean(s.name) for s in states
               if s.entity_id.startswith("update.") and s.state == "on"]
    return {"errors": errors[:MAX_ERRORS], "more_errors": max(0, len(errors) - MAX_ERRORS),
            "failed": failed[:MAX_NAMES], "repairs": [clean(r) for r in repairs[:MAX_NAMES]],
            "low_batteries": sorted(low)[:MAX_NAMES], "updates": sorted(updates)[:MAX_NAMES],
            "unavailable": sum(1 for s in states if s.state == "unavailable")}


def _low(state: State) -> bool:
    if state.attributes.get("device_class") != "battery":
        return False
    try:
        return state.entity_id.startswith("sensor.") and float(state.state) < LOW_BATTERY
    except ValueError:
        return False


def _when(stamp: object) -> str:
    if not isinstance(stamp, (int, float)):
        return ""
    return dt_util.as_local(dt_util.utc_from_timestamp(stamp)).strftime("%a %d %b %H:%M")


async def history(hass: HomeAssistant, entity_id: str, kind: str) -> dict[str, Any]:
    """What changed, in BRAM's own words, newest first."""
    if "recorder" not in hass.config.components:
        return {"error": "off"}
    from homeassistant.components.recorder import history as recorded

    start = dt_util.utcnow() - datetime.timedelta(days=DAYS)
    found = await get_instance(hass).async_add_executor_job(
        lambda: recorded.state_changes_during_period(
            hass, start, entity_id=entity_id, no_attributes=True,
            include_start_time_state=False))
    yes, no = MEANING.get(kind, ("", ""))
    words = {"on": yes, "open": yes, "unlocked": yes, "home": yes,
             "off": no, "closed": no, "locked": no, "not_home": no}
    runs: list[tuple[float, str]] = []
    for state in found.get(entity_id, []):
        word = words.get(state.state, "unknown" if kind != "person" else "away")
        if state.state in ("unavailable", "unknown"):
            word = "unknown"
        if not runs or runs[-1][1] != word:
            runs.append((state.last_changed.timestamp(), word))
    # Models are bad at arithmetic, so every length is worked out here.
    ends = [at for at, _ in runs[1:]] + [dt_util.utcnow().timestamp()]
    changes, counts, totals = [], {}, {}
    for (at, word), end in zip(runs, ends, strict=True):
        counts[word] = counts.get(word, 0) + 1
        totals[word] = totals.get(word, 0.0) + end - at
        now = " so far" if at == runs[-1][0] else ""
        changes.append([_when(at), word, f"for {length(end - at)}{now}"])
    return {"changes": changes[::-1][:MAX_CHANGES], "counts": counts, "days": DAYS,
            "totals": {w: length(t) for w, t in totals.items()}}


def length(seconds: float) -> str:
    seconds = max(0, round(seconds))
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' * (minutes != 1)}"
    if minutes < 2880:
        hours, rest = divmod(minutes, 60)
        return f"{hours} hour{'s' * (hours != 1)}" + (f" {rest} min" if rest else "")
    return f"{round(minutes / 1440)} days"
