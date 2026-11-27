"""Finds what is wrong with Home Assistant itself. Reads only. Plain rules, no model, no server."""
from __future__ import annotations

import datetime
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import CONF_ENTITIES, DOMAIN, SAFETY
from .feed import kind_of
from .names import entity_name
from .queries import clean
from .security import PRINTERS

OFFLINE = datetime.timedelta(minutes=30)
STUCK = datetime.timedelta(hours=48)
BACKUP_OLD = datetime.timedelta(days=8)
LOW, LOW_OVER, PHONE_LOW = 15, 20, 20
ERRORS, WINDOW = 10, 3600
WHOLE = 3  # this many devices gone at once is one problem with their integration
DISK_FREE, DISK_FREE_BYTES = 0.05, 1_000_000_000
DATABASE = 10_000_000_000
HEALTH = 50
# Devices that are away or off in ordinary use, or that other rules watch.
ORDINARY = {"mobile_app", "hassio", "bram", *PRINTERS}
NOT_READINGS = ("target", "setpoint", "set_point", "_set", "limit", "threshold", "max", "min",
                "high", "low", "calibration", "offset")


@dataclass(frozen=True)
class Problem:
    key: str
    level: str
    text: str
    tell: bool = True  # otherwise only listed


def _name(text: object) -> str:
    return clean(text)[:60] or "Something"


def _short(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


class Finder:
    """Remembers only what it needs to tell a moment from a pattern."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass, self._options = hass, entry.options
        self._failing: dict[str, float] = {}
        self._errors: dict[str, tuple[float, int]] = {}
        self._repeating: dict[str, tuple[float, Problem]] = {}
        self._low: set[str] = set()
        self.not_run: list[str] = []

    async def find(self, night: bool) -> list[Problem]:
        found: list[Problem] = []
        self.not_run = []
        for label, check in (("Integrations", self._integrations), ("Errors", self._log),
                             ("Repairs", self._repairs), ("Offline devices", self._devices),
                             ("Stuck sensors", self._stuck), ("Automations", self._automations),
                             ("Backups", self._backups), ("Updates", self._updates),
                             ("Devices reporting trouble", self._trouble)):
            try:
                found += check()
            except Exception:  # noqa: BLE001 - one broken check must not stop the rest
                self.not_run.append(label)
        try:
            found += self._batteries(night)
        except Exception:  # noqa: BLE001
            self.not_run.append("Batteries")
        try:
            found += await self._hass.async_add_executor_job(self._disk)
        except Exception:  # noqa: BLE001
            self.not_run.append("Disk")
        return found

    def _now(self) -> float:
        return dt_util.utcnow().timestamp()

    def _integrations(self) -> list[Problem]:
        now, found, failing = self._now(), [], {}
        for entry in self._hass.config_entries.async_entries():
            if entry.domain in (DOMAIN, *PRINTERS) or entry.disabled_by is not None:
                continue
            retrying = entry.state is ConfigEntryState.SETUP_RETRY
            if not retrying and entry.state not in (
                    ConfigEntryState.SETUP_ERROR, ConfigEntryState.MIGRATION_ERROR,
                    ConfigEntryState.FAILED_UNLOAD):
                continue
            since = failing[entry.entry_id] = self._failing.get(entry.entry_id, now)
            if now - since < OFFLINE.total_seconds():
                continue
            what = "cannot connect and keeps retrying" if retrying else "failed to start"
            title = _name(entry.title)
            label = title if entry.domain in title.lower() else f"{title} ({entry.domain})"
            found.append(Problem(f"integration:{entry.entry_id}", "low" if retrying else "medium",
                                 f"{label} {what}. Look in Settings > Devices & services"))
        self._failing = failing
        return found

    def _log(self) -> list[Problem]:
        now = self._now()
        log = self._hass.data.get("system_log")
        seen = {}
        for item in (log.records.to_list() if log is not None else []):
            if item.get("level") not in ("ERROR", "CRITICAL"):
                continue
            key = _short(f"{item.get('name')}{item.get('source')}")
            seen[key] = item
            count = int(item.get("count", 1))
            at, base = self._errors.get(key, (now, 0 if self._errors else count))
            if count < base:  # Home Assistant restarted or the log was cleared
                at, base = now, 0
            if count - base >= ERRORS:
                name = clean(str(item.get("name", "")).removeprefix("homeassistant.").removeprefix(
                    "components.").removeprefix("custom_components."))
                text = clean((item.get("message") or [""])[-1])
                # The count is left out, so the same problem keeps the same words.
                self._repeating[key] = (now, Problem(
                    f"error:{key}", "medium", f"{name} keeps logging the same error: {text}"))
                at, base = now, count
            elif now - at >= WINDOW:
                at, base = now, count
            self._errors[key] = (at, base)
        self._errors = {k: v for k, v in self._errors.items() if k in seen}
        self._repeating = {k: v for k, v in self._repeating.items() if now - v[0] < 2 * WINDOW}
        return [p for _, p in self._repeating.values()]

    def _repairs(self) -> list[Problem]:
        found = []
        for issue in ir.async_get(self._hass).issues.values():
            if (not issue.active or issue.dismissed_version is not None
                    or issue.domain == DOMAIN or not issue.translation_key):
                continue
            serious = issue.severity in (ir.IssueSeverity.CRITICAL, ir.IssueSeverity.ERROR)
            words = clean(issue.translation_key).replace("_", " ")
            found.append(Problem(f"repair:{_short(issue.domain + issue.issue_id)}",
                                 "medium" if serious else "low",
                                 f"Home Assistant suggests a repair for {issue.domain}: {words}. "
                                 "Look in Settings > System > Repairs"))
        return found

    def _shown(self, state: State) -> str:
        """The name people use, never a serial number (see names.py)."""
        return _name(entity_name(self._hass, state))

    def _platform(self, entity_id: str) -> tuple[str, str | None]:
        entry = er.async_get(self._hass).async_get(entity_id)
        return (entry.platform, entry.device_id) if entry is not None else ("", None)

    def _batteries(self, night: bool) -> list[Problem]:
        found, low = [], set()
        for state in self._hass.states.async_all(("sensor", "binary_sensor")):
            if state.attributes.get("device_class") != "battery":
                continue
            platform, device = self._platform(state.entity_id)
            if platform in PRINTERS:
                continue
            if state.entity_id.startswith("binary_sensor."):
                if state.state == "on":
                    found.append(Problem(f"battery:{state.entity_id}", "low",
                                         f"{self._shown(state)} is low"))
                continue
            try:
                level = float(state.state)
            except ValueError:
                # Not known, so a battery that was low still counts as low (B2).
                if state.entity_id in self._low:
                    low.add(state.entity_id)
                    found.append(Problem(f"battery:{state.entity_id}", "low",
                                         f"{self._shown(state)} is low"))
                continue
            if platform == "mobile_app":
                if night and level < PHONE_LOW and not self._charging(device):
                    found.append(Problem(f"battery:{state.entity_id}", "low",
                                         f"{self._shown(state)} is low and not charging"))
                continue
            if level < (LOW_OVER if state.entity_id in self._low else LOW):
                low.add(state.entity_id)
                found.append(Problem(f"battery:{state.entity_id}", "low",
                                     f"{self._shown(state)} is low"))
        self._low = low
        return found

    def _charging(self, device: str | None) -> bool:
        if device is None:
            return False
        states = [self._hass.states.get(e.entity_id) for e in
                  er.async_entries_for_device(er.async_get(self._hass), device)]
        return any(s is not None and s.entity_id.endswith(("battery_state", "is_charging"))
                   and s.state.lower() in ("charging", "full", "on") for s in states)

    def _devices(self) -> list[Problem]:
        cutoff = dt_util.utcnow() - OFFLINE
        entities = er.async_get(self._hass)
        gone: dict[str, list[dr.DeviceEntry]] = {}
        total: dict[str, int] = {}
        devices = dr.async_get(self._hass)
        # Older versions of Home Assistant give ids here, newer ones the devices themselves.
        for item in list(devices.devices):
            device = devices.async_get(item) if isinstance(item, str) else item
            if device is None or device.disabled_by is not None:
                continue
            mine = er.async_entries_for_device(entities, device.id)
            states = [s for e in mine if (s := self._hass.states.get(e.entity_id)) is not None]
            if (not states or any(e.platform in ORDINARY for e in mine)
                    or any(s.entity_id.startswith("media_player.") for s in states)
                    or any(self._watched(s) for s in states)):
                continue
            home = mine[0].config_entry_id or ""
            total[home] = total.get(home, 0) + 1
            if all(s.state == "unavailable" and s.last_changed <= cutoff for s in states):
                gone.setdefault(home, []).append(device)
        found = []
        for home, missing in gone.items():
            entry = self._hass.config_entries.async_get_entry(home) if home else None
            if entry is not None and entry.state is not ConfigEntryState.LOADED:
                continue  # already said by the integration itself
            if entry is not None and len(missing) >= WHOLE and len(missing) == total[home]:
                found.append(Problem(f"gone:{home}", "medium",
                                     f"Everything from {_name(entry.title)} is offline"))
                continue
            for device in missing:
                name = _name(device.name_by_user or device.name)
                found.append(Problem(f"device:{device.id}", "low", f"{name} is offline"))
        return found

    def _watched(self, state: State) -> bool:
        """Safety sensors, locks, and doors have their own rules."""
        if state.entity_id not in self._options.get(CONF_ENTITIES, []):
            return False
        kind = kind_of(state.entity_id, state.attributes.get("device_class"))
        return kind in SAFETY or (kind in ("lock", "opening") and bool(
            self._options.get("offline")))

    def _stuck(self) -> list[Problem]:
        cutoff, found = dt_util.utcnow() - STUCK, []
        entities = er.async_get(self._hass)
        for state in self._hass.states.async_all("sensor"):
            if (state.attributes.get("device_class") not in ("temperature", "humidity")
                    or state.last_changed > cutoff
                    or any(w in state.entity_id for w in NOT_READINGS)):
                continue
            entry = entities.async_get(state.entity_id)
            if (entry is None or entry.device_id is None or entry.entity_category is not None
                    or entry.platform in ORDINARY):
                continue
            try:
                float(state.state)
            except ValueError:
                continue
            found.append(Problem(f"stuck:{state.entity_id}", "low",
                                 f"{self._shown(state)} has said {state.state} for more than 2 days"
                                 ". The sensor may be stuck"))
        return found

    def _automations(self) -> list[Problem]:
        found = []
        entities = er.async_get(self._hass)
        component = self._hass.data.get("automation")
        for item in getattr(component, "entities", []):
            state = self._hass.states.get(item.entity_id)
            if state is None:
                continue
            if state.state == "unavailable":
                found.append(Problem(f"automation:{item.entity_id}", "medium",
                                     f"Automation {self._shown(state)} could not be loaded"))
                continue
            if state.state != "on":
                continue
            missing = sorted(e for e in getattr(item, "referenced_entities", ())
                             if self._hass.states.get(e) is None and entities.async_get(e) is None
                             and "." in e and not e.startswith(("scene.", "input_")))
            if missing:
                found.append(Problem(f"missing:{item.entity_id}", "low",
                                     f"Automation {self._shown(state)} uses {missing[0]}"
                                     + (f" and {len(missing) - 1} more" if missing[1:] else "")
                                     + ", which does not exist"))
        return found

    def _trouble(self) -> list[Problem]:
        """A device's own count of alerts or errors, or its own health reading."""
        found = []
        for state in self._hass.states.async_all("sensor"):
            low = state.entity_id.lower()
            try:
                value = float(state.state)
            except ValueError:
                continue
            name = _name(state.name.replace("_", " "))
            if low.endswith(("alert_count", "error_count", "alarm_count", "fault_count")):
                if value > 0:
                    found.append(Problem(f"trouble:{state.entity_id}", "medium",
                                         f"{name} is {value:g}"))
            elif (low.endswith("_health") and state.attributes.get("unit_of_measurement") == "%"
                  and value < HEALTH):
                found.append(Problem(f"trouble:{state.entity_id}", "medium",
                                     f"{name} is down to {value:g}%"))
        return found

    def _backups(self) -> list[Problem]:
        for entry in er.async_get(self._hass).entities.values():
            if (entry.platform != "backup"
                    or "last_successful_automatic_backup" not in entry.unique_id):
                continue
            state = self._hass.states.get(entry.entity_id)
            last = dt_util.parse_datetime(state.state) if state is not None else None
            # Never made one may mean it is done another way, such as by the host.
            if last is not None and dt_util.utcnow() - last > BACKUP_OLD:
                return [Problem("backup", "medium",
                                "Home Assistant's last automatic backup is more than a week old")]
        return []

    def _updates(self) -> list[Problem]:
        return [Problem(f"update:{s.entity_id}", "low", f"Update waiting: {_name(s.name)}", False)
                for s in self._hass.states.async_all("update") if s.state == "on"]

    def _disk(self) -> list[Problem]:
        found = []
        use = shutil.disk_usage(self._hass.config.config_dir)
        if use.free < max(use.total * DISK_FREE, DISK_FREE_BYTES):
            found.append(Problem("disk", "medium", "Home Assistant's disk is almost full"))
        file = Path(self._hass.config.path("home-assistant_v2.db"))
        if file.exists() and file.stat().st_size > DATABASE:
            found.append(Problem("database", "low",
                                 "Home Assistant's database is larger than 10 GB"))
        return found


def summary(problems: list[Problem]) -> dict[str, Any]:
    return {"medium": sum(p.level == "medium" for p in problems), "all": len(problems)}
