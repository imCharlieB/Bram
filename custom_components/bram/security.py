"""Read-only checks of Home Assistant itself. Counts and fixed words only: no names of people.

Says what it could not check, and never that a home is secure.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Any

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

OLD_TOKEN_DAYS = 90
OFFLINE = datetime.timedelta(minutes=30)
ASSISTANTS = {"conversation": "Assist", "cloud.alexa": "Alexa", "cloud.google_assistant": "Google"}
NOT_CHECKED = ["Your router and network", "Remote access through Home Assistant Cloud",
               "Z-Wave security levels", "App ports", "Passwords and two-factor sign-in"]


def _sensitive(state: State) -> bool:
    domain = state.entity_id.split(".", 1)[0]
    return domain in ("lock", "alarm_control_panel") or (
        domain == "cover" and state.attributes.get("device_class") in ("garage", "door", "gate"))


def _finding(key: str, level: str, text: str) -> dict[str, str]:
    return {"key": key, "level": level, "text": text}


async def check(hass: HomeAssistant, known: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Findings, most serious first. Each check that fails is listed as not run."""
    found: list[dict[str, str]] = []
    missed = list(NOT_CHECKED)
    ids: dict[str, list[str]] = {"admins": [], "tokens": []}

    async def accounts() -> None:
        now = dt_util.utcnow()
        old = 0
        for user in await hass.auth.async_get_users():
            if user.system_generated or not user.is_active:
                continue
            if user.is_admin:
                ids["admins"].append(user.id)
            for token in user.refresh_tokens.values():
                if token.token_type == TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
                    ids["tokens"].append(token.id)
                    used = token.last_used_at or token.created_at
                    old += (now - used).days >= OLD_TOKEN_DAYS
        if known is not None:
            for kind, words in (("admins", "administrator account"), ("tokens", "access token")):
                for item in set(ids[kind]) - set(known.get(kind, [])):
                    found.append(_finding(f"new:{kind}:{item}", "high",
                                          f"A new {words} was created"))
        if len(ids["admins"]) > 2:
            found.append(_finding("many_admins", "low", f"{len(ids['admins'])} people are "
                                  "administrators; fewer is safer"))
        if old:
            found.append(_finding("old_tokens", "low", f"{old} access token{'s' * (old != 1)} not "
                                  f"used in {OLD_TOKEN_DAYS} days; delete any you do not need"))

    def logins() -> None:
        from homeassistant.components.persistent_notification import (
            _async_get_or_create_notifications,
        )

        if "http-login" in _async_get_or_create_notifications(hass):
            found.append(_finding("failed_login", "medium", "Someone failed to sign in to Home "
                                  "Assistant; see its notifications"))

    def bypass() -> None:
        for provider in hass.auth.auth_providers:
            if provider.type == "trusted_networks" and provider.config.get("allow_bypass_login"):
                found.append(_finding("bypass", "medium", "Trusted networks can sign in without "
                                      "a password"))

    def exposed() -> None:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_get_entity_settings,
        )

        for assistant, label in ASSISTANTS.items():
            names = []
            for state in hass.states.async_all():
                if not _sensitive(state):
                    continue
                try:
                    settings = async_get_entity_settings(hass, state.entity_id)
                except Exception:  # noqa: BLE001, S112 - no settings means not exposed by choice
                    continue
                if settings.get(assistant, {}).get("should_expose"):
                    names.append(state.name)
            if names:
                found.append(_finding(f"exposed:{assistant}", "medium", (
                    f"{label} can see or use {', '.join(sorted(names)[:5])}")))

    def webhooks() -> None:
        component = hass.data.get("automation")
        count = 0
        for entity in getattr(component, "entities", []):
            config = getattr(entity, "raw_config", None) or {}
            triggers = config.get("triggers", config.get("trigger")) or []
            for trigger in triggers if isinstance(triggers, list) else [triggers]:
                if (isinstance(trigger, dict)
                        and "webhook" in (trigger.get("trigger"), trigger.get("platform"))
                        and trigger.get("local_only") is False):
                    count += 1
        if count:
            found.append(_finding("webhooks", "medium", f"{count} automation{'s' * (count != 1)} "
                                  "can be started from the internet by webhook"))

    def offline() -> None:
        cutoff = dt_util.utcnow() - OFFLINE
        names = sorted(s.name for s in hass.states.async_all()
                       if (_sensitive(s) or s.entity_id.startswith("camera."))
                       and s.state == "unavailable" and s.last_changed <= cutoff)
        if names:
            more = f" and {len(names) - 5} more" if len(names) > 5 else ""
            found.append(_finding("offline:" + ",".join(names), "medium",
                                  f"Offline: {', '.join(names[:5])}{more}"))

    def joining() -> None:
        names = sorted(s.name for s in hass.states.async_all("switch")
                       if s.state == "on" and "permit_join" in s.entity_id)
        if names:
            found.append(_finding("joining", "medium", "Zigbee joining is open: new devices can "
                                  "be added"))

    def address() -> None:
        url = hass.config.external_url or ""
        if url.startswith("http://"):
            found.append(_finding("plain_http", "high", "The outside address is not encrypted"))

    def upnp() -> None:
        if any(e.domain == "upnp" for e in hass.config_entries.async_entries()):
            found.append(_finding("upnp", "low", "The router offers UPnP, which lets devices open "
                                  "ports"))

    def updates() -> None:
        names = [s.name for s in hass.states.async_all("update") if s.state == "on"
                 and s.entity_id.startswith("update.home_assistant_")]
        if names:
            found.append(_finding("updates", "low", f"Updates waiting: {', '.join(names[:4])}"))

    for label, step in (("Accounts and tokens", accounts), ("Failed sign-ins", logins),
                        ("Sign-in bypass", bypass), ("Voice assistant exposure", exposed),
                        ("Webhooks", webhooks), ("Offline security devices", offline),
                        ("Zigbee joining", joining), ("Outside address", address),
                        ("UPnP", upnp), ("Updates", updates)):
        try:
            result = step()
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # noqa: BLE001 - a check that breaks is one that did not run
            missed.append(label)
    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda f: order[f["level"]])
    return {"findings": found, "not_checked": missed, "ids": ids}
