"""3D printers, read from whichever integration each one uses. Reads only."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .names import device_name
from .security import PRINTERS

# What each integration calls things: the end of a unique id, or its start if it ends with "-".
ROLES = {
    "status": ("_print_status", "_print_state", "current state-", "_printer.state",
               "_current_status"),
    "progress": ("_print_progress", "_progress", "job percentage-", "_job.progress",
                 "_percent_complete"),
    "left": ("_remaining_time", "_print_time_left", "_ticks_remaining"),
    "ends": ("estimated finish time-", "_job.finish"),
    "file": ("_subtask_name", "_filename", "current file-", "_job.filename"),
    "nozzle": ("_nozzle_temp", "_extruder_temp", "actual tool0 temp-",
               "_printer.telemetry.temp-nozzle"),
    "nozzle2": ("_left_nozzle_temp",),
    "nozzle_target": ("_target_nozzle_temp", "_extruder_target", "target tool0 temp-",
                      "_printer.telemetry.temp-nozzle.target"),
    "nozzle2_target": ("_left_target_nozzle_temp",),
    "bed": ("_bed_temp", "_heater_bed_temp", "actual bed temp-", "_printer.telemetry.temp-bed"),
    "bed_target": ("_target_bed_temp", "_heater_bed_target", "target bed temp-",
                   "_printer.telemetry.temp-bed.target"),
    "chamber": ("_chamber_temp", "_temp_of_box"),
    "problem": ("_hms", "_print_error", "printing error-"),
    "weight": ("_print_weight",),
}
STATES = {
    "printing": {"running", "prepare", "slicing", "printing", "starting", "starting_sd",
                 "starting_streaming", "printing_sd", "printing_streaming", "resuming",
                 "finishing", "busy", "preheating"},
    "paused": {"pause", "paused", "pausing"},
    "finished": {"finish", "complete", "completed", "finished"},
    "failed": {"failed", "error", "offline_after_error", "attention"},
    "stopped": {"cancelled", "cancelling", "stopped", "stopping"},
    "idle": {"idle", "init", "standby", "operational", "ready", "transferring_file"},
    "off": {"offline", "open_serial", "detect_serial", "connecting"},
}
MEANS = {word: name for name, words in STATES.items() for word in words}


@dataclass(frozen=True)
class Printer:
    id: str
    name: str
    area: str
    roles: dict[str, list[str]] = field(default_factory=dict)


def _role(unique_id: str, platform: str) -> str | None:
    uid = unique_id.lower()
    best: tuple[int, str] | None = None
    for role, names in ROLES.items():
        for name in names:
            hit = uid.startswith(name) if name.endswith("-") else uid.endswith(name)
            # The longest match wins: a target is not the temperature itself.
            if hit and (best is None or len(name) > best[0]):
                best = (len(name), role)
    return best[1] if best else None


def find(hass: HomeAssistant) -> list[Printer]:
    entities, devices, areas = er.async_get(hass), dr.async_get(hass), ar.async_get(hass)
    found: dict[str, dict[str, list[str]]] = {}
    for entry in entities.entities.values():
        if entry.platform not in PRINTERS or entry.device_id is None or entry.disabled_by:
            continue
        if role := _role(str(entry.unique_id), entry.platform):
            found.setdefault(entry.device_id, {}).setdefault(role, []).append(entry.entity_id)
    printers = []
    for device_id, roles in found.items():
        device = devices.async_get(device_id)
        # Only a device that says what it is printing is a printer.
        if device is None or "status" not in roles:
            continue
        area = areas.async_get_area(device.area_id) if device.area_id else None
        name = device_name(hass, device)[:40]
        printers.append(Printer(device_id, name, area.name[:40] if area else "", roles))
    return sorted(printers, key=lambda p: p.name)


def read(hass: HomeAssistant, printer: Printer) -> dict[str, Any]:
    """What the printer says now. What it does not say is left out (B2)."""
    def state(role: str) -> State | None:
        for entity_id in printer.roles.get(role, []):
            found = hass.states.get(entity_id)
            if found is not None and found.state not in ("unavailable", "unknown", ""):
                return found
        return None

    def number(role: str) -> float | None:
        found = state(role)
        try:
            return float(found.state) if found is not None else None
        except ValueError:
            return None

    status = state("status")
    result: dict[str, Any] = {
        "id": printer.id, "name": printer.name, "area": printer.area,
        "state": MEANS.get(status.state.lower(), "unknown") if status is not None else "unknown"}
    # Reachable means the integration answers, even if the printer itself is off.
    if status is None and all(
            (s := hass.states.get(e)) is None or s.state == "unavailable"
            for e in printer.roles["status"]):
        result["state"] = "off"
    if result["state"] in ("off", "unknown"):
        return result
    for role in ("nozzle", "nozzle2", "nozzle_target", "nozzle2_target", "bed", "bed_target",
                 "chamber"):
        if (value := number(role)) is not None:
            result[role] = round(value)
    if (heat := state("nozzle") or state("bed")) is not None:
        result["unit"] = str(heat.attributes.get("unit_of_measurement") or "")[:5]
    problems = [s for e in printer.roles.get("problem", [])
                if (s := hass.states.get(e)) is not None and s.state == "on"]
    result["problem"] = bool(problems)
    # What the printer says is wrong, such as a Bambu HMS message. It is data, kept short.
    for found in problems:
        words = [v for k, v in sorted(found.attributes.items())
                 if str(k).lower().endswith(("error", "message")) and isinstance(v, str) and v]
        if words:
            result["problem_text"] = " ".join(
                "".join(c if c.isprintable() else " " for c in words[0]).split())[:160]
            break
    if result["state"] in ("printing", "paused", "finished", "failed", "stopped"):
        if (file := state("file")) is not None:
            result["file"] = " ".join(
                "".join(c if c.isprintable() else " " for c in file.state).split())[:80]
        if (progress := number("progress")) is not None and 0 <= progress <= 100:
            result["progress"] = round(progress)
        if (weight := number("weight")) is not None:
            result["weight"] = round(weight)
    if result["state"] in ("printing", "paused") and (left := _left(state)) is not None:
        result["left"] = left
    return result


def _left(state: Any) -> int | None:
    """Seconds left."""
    if (found := state("left")) is not None:
        try:
            value = float(found.state)
        except ValueError:
            return None
        unit = found.attributes.get("unit_of_measurement")
        size = {"s": 1, "min": 60, "h": 3600, "d": 86400, "ms": 0.001}.get(unit)
        return round(value * size) if size and 0 <= value * size < 30 * 86400 else None
    if (found := state("ends")) is not None:
        ends = dt_util.parse_datetime(found.state)
        if ends is not None and ends.tzinfo is not None:
            left = (ends - dt_util.utcnow()) / datetime.timedelta(seconds=1)
            return round(left) if 0 <= left < 30 * 86400 else None
    return None
