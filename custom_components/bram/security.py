"""Read-only checks of Home Assistant itself. Counts and fixed words only: no names of people.

Says what it could not check, and never that a home is secure.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Any

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

OLD_TOKEN_DAYS = 90
# Cameras on 3D printers are off whenever the printer is.
PRINTERS = {"bambu_lab", "moonraker", "octoprint", "prusalink", "elegoo_printer",
            "creality", "ha_creality_ws", "anycubic_cloud"}
OFFLINE = datetime.timedelta(minutes=30)
ASSISTANTS = {"conversation": "Assist", "cloud.alexa": "Alexa", "cloud.google_assistant": "Google"}
NOT_CHECKED = ["Remote access through Home Assistant Cloud",
               "Passwords and two-factor sign-in"]
# Router integrations: their device list, firmware, and guest Wi-Fi.
ROUTERS = {"opnsense", "pfsense", "unifi", "fritz", "eero", "netgear", "asuswrt", "tplink_omada",
           "openwrt", "luci", "ubus", "keenetic_ndms2", "mikrotik", "ruckus_unleashed",
           "tplink_router", "huawei_lte", "synology_srm", "vodafone_station", "nmap_tracker",
           "ping"}
RADIOS = {"zha": "Zigbee", "deconz": "Zigbee", "zwave_js": "Z-Wave", "matter": "Matter",
          "thread": "Thread", "homekit_controller": "HomeKit"}


def _sensitive(state: State) -> bool:
    domain = state.entity_id.split(".", 1)[0]
    return domain in ("lock", "alarm_control_panel") or (
        domain == "cover" and state.attributes.get("device_class") in ("garage", "door", "gate"))


def _finding(key: str, level: str, text: str) -> dict[str, str]:
    return {"key": key, "level": level, "text": text}


def _zwave_security(hass: HomeAssistant, device_id: str) -> str | None:
    """A Z-Wave device's best security class, such as S2_ACCESS_CONTROL, or None."""
    from homeassistant.components.zwave_js.helpers import async_get_node_from_device_id
    node = async_get_node_from_device_id(hass, device_id)
    found = getattr(node, "highest_security_class", None)
    return getattr(found, "name", None) if found is not None else None


async def check(hass: HomeAssistant, known: dict[str, list[str]] | None = None,
                away: bool = False, own: tuple[dict[str, str] | None, dict] | None = None,
                ) -> dict[str, Any]:
    """Findings, most serious first. Each check that fails is listed as not run."""
    found: list[dict[str, str]] = []
    missed = list(NOT_CHECKED)
    ids: dict[str, list[str]] = {"admins": [], "tokens": [], "network": [], "radio": [],
                                 "network_sources": []}
    registry, devices = er.async_get(hass), dr.async_get(hass)
    domains = {e.entry_id: e.domain for e in hass.config_entries.async_entries()}

    def owner(entity_id: str) -> str | None:
        entry = registry.async_get(entity_id)
        return domains.get(entry.config_entry_id) if entry and entry.config_entry_id else None

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
                    # Home Assistant does not record when these are used, only when made.
                    old += (now - token.created_at).days >= OLD_TOKEN_DAYS
        if known is not None:
            for kind, words in (("admins", "administrator account"), ("tokens", "access token")):
                for item in set(ids[kind]) - set(known.get(kind, [])):
                    found.append(_finding(f"new:{kind}:{item}", "high",
                                          f"A new {words} was created"))
        if len(ids["admins"]) > 2:
            found.append(_finding("many_admins", "low", f"{len(ids['admins'])} people are "
                                  "administrators; fewer is safer"))
        if old:
            found.append(_finding("old_tokens", "low", f"{old} access token{'s' * (old != 1)} "
                                  f"more than {OLD_TOKEN_DAYS} days old. Home Assistant cannot say "
                                  "if they are in use, so check before deleting"))

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
        registry = er.async_get(hass)

        def watched(state: State) -> bool:
            if not state.entity_id.startswith("camera."):
                return _sensitive(state)
            entry = registry.async_get(state.entity_id)
            return entry is None or entry.platform not in PRINTERS

        names = sorted({s.name for s in hass.states.async_all() if watched(s)
                        and s.state == "unavailable" and s.last_changed <= cutoff})
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
            found.append(_finding("upnp", "low", "The UPnP integration is set up; check whether "
                                  "your router lets devices open ports"))

    def updates() -> None:
        names = [s.name for s in hass.states.async_all("update") if s.state == "on"
                 and s.entity_id.startswith("update.home_assistant_")]
        if names:
            found.append(_finding("updates", "low", f"Updates waiting: {', '.join(names[:4])}"))

    def network() -> None:
        """Devices on the network: from the router connected on BRAM's page, Home Assistant's
        own DHCP discovery, and any router integration's device list. A device is known by its
        hardware address whichever source reports it. Each source's first look learns what is
        already there, so only devices that join after it are told, once."""
        seen: dict[str, tuple[str, str]] = {}  # key: (source, name)
        for state in hass.states.async_all("device_tracker"):
            if state.attributes.get("source_type") == "router" or owner(state.entity_id) in ROUTERS:
                mac = str(state.attributes.get("mac") or "").lower()
                seen[f"mac:{mac}" if mac else state.entity_id] = ("trackers", state.name)
        # Home Assistant's DHCP discovery keeps what it has seen under its own name.
        addresses = getattr(hass.data.get("dhcp"), "address_data", None) or {}
        for mac, data in list(addresses.items()):
            name = str(data.get("hostname") or "").strip()
            where = data.get("ip") or "an unknown address"
            seen.setdefault(f"mac:{mac.lower()}", ("discovery", name or f"a device at {where}"))
        # The router itself: every network and VLAN, with the best names.
        if own is not None and own[0]:
            for key, name in own[0].items():
                seen[f"mac:{key.removeprefix('router:').lower()}"] = ("router", name)
        if not seen:
            missed.append("Devices on your network: none seen yet. Connect your router on "
                          "BRAM's page to see every network")
            return
        sources = sorted({source for source, _ in seen.values()})
        ids["network"], ids["network_sources"] = sorted(seen), sources
        if known is None or "network" not in known:
            return  # the first look learns what is already there
        # Learned before 0.52.3: keys were dhcp:<mac>; trackers and discovery had been seen.
        before = {k.replace("dhcp:", "mac:", 1) for k in known["network"]}
        learned = set(known.get("network_sources") or ["trackers", "discovery"])
        for key, (source, name) in seen.items():
            if key in before or source not in learned:
                continue  # known, or a source seen for the first time: learned, not told
            where = " while everyone is away" if away else ""
            found.append(_finding(f"new:network:{key}", "high" if away else "medium",
                                  f"A new device joined your network{where}: {name}"))

    def radio() -> None:
        """New Zigbee, Z-Wave, Matter, and other paired devices, told once."""
        here: dict[str, tuple[str, str]] = {}
        for entry in hass.config_entries.async_entries():
            kind = RADIOS.get(entry.domain) or ("Zigbee" if entry.domain == "mqtt" else None)
            if kind is None:
                continue
            for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
                # Zigbee2MQTT's devices; not everything else that speaks MQTT.
                if entry.domain == "mqtt" and not any(
                        "zigbee2mqtt" in str(part) for part in device.identifiers):
                    continue
                if device.entry_type is None:
                    here[device.id] = (kind, device.name_by_user or device.name or "A device")
        ids["radio"] = sorted(here)
        if known is None or "radio" not in known:
            return
        for device_id, (kind, name) in here.items():
            if device_id not in known["radio"]:
                found.append(_finding(f"new:radio:{device_id}", "medium",
                                      f"A new {kind} device was paired: {name}"))

    def zwave_locks() -> None:
        """Z-Wave locks joined without S2, the strong kind of Z-Wave security."""
        weak = []
        for entry in hass.config_entries.async_entries("zwave_js"):
            for item in er.async_entries_for_config_entry(registry, entry.entry_id):
                if item.domain != "lock" or not item.device_id:
                    continue
                level = _zwave_security(hass, item.device_id)
                if level is None or not level.startswith("S2"):
                    state = hass.states.get(item.entity_id)
                    weak.append(state.name if state else item.entity_id)
        if weak:
            found.append(_finding("zwave_weak", "medium", "Z-Wave lock without S2 security, so "
                                  f"its radio is easier to fool: {', '.join(sorted(weak)[:4])}. "
                                  "Pair it again with S2"))

    def router() -> None:
        """The router's own firmware, and guest Wi-Fi left on."""
        waiting = [s.name for s in hass.states.async_all("update")
                   if s.state == "on" and owner(s.entity_id) in ROUTERS]
        if own is not None and own[1].get("update"):
            waiting.append(f"OPNsense {own[1].get('version', '')}".strip())
        if waiting:
            found.append(_finding("router_update", "medium",
                                  f"Router update waiting: {', '.join(waiting[:3])}"))
        guests = [s.name for s in hass.states.async_all("switch")
                  if s.state == "on" and "guest" in s.entity_id and owner(s.entity_id) in ROUTERS]
        if guests:
            found.append(_finding("guest_wifi", "low",
                                  f"Guest Wi-Fi is on: {', '.join(guests[:3])}"))

    def apps() -> None:
        """Home Assistant apps with protection off, or with ports open on the host."""
        if "hassio" not in hass.config.components:
            return
        from homeassistant.components.hassio import get_addons_info
        unprotected, ports = [], []
        for slug, info in (get_addons_info(hass) or {}).items():
            if not isinstance(info, dict) or info.get("state") not in ("started", None):
                continue
            name = str(info.get("name") or slug)
            if info.get("protected") is False:
                unprotected.append(name)
            network = info.get("network")
            if isinstance(network, dict) and any(v for v in network.values()):
                ports.append(name)
        if unprotected:
            found.append(_finding("apps_unprotected", "medium", "Apps running with protection "
                                  f"mode off: {', '.join(sorted(unprotected)[:4])}"))
        if ports:
            found.append(_finding("apps_ports", "low", "Apps with ports open on the host: "
                                  f"{', '.join(sorted(ports)[:6])}. Close any you do not use"))

    for label, step in (("Accounts and tokens", accounts), ("Failed sign-ins", logins),
                        ("Sign-in bypass", bypass), ("Voice assistant exposure", exposed),
                        ("Webhooks", webhooks), ("Offline security devices", offline),
                        ("Zigbee joining", joining), ("Outside address", address),
                        ("UPnP", upnp), ("Updates", updates),
                        ("Devices on your network", network), ("New paired devices", radio),
                        ("Z-Wave lock security", zwave_locks), ("Router", router),
                        ("App protection and ports", apps)):
        try:
            result = step()
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # noqa: BLE001 - a check that breaks is one that did not run
            missed.append(label)
    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda f: order[f["level"]])
    return {"findings": found, "not_checked": missed, "ids": ids}
