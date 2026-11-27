"""Your router, read directly: every device on every network and VLAN, and its firmware.

OPNsense first. BRAM only reads, with an API key the owner makes for a user that may only
read the ARP table, DHCP leases, and firmware status. It never changes the router. The
router is on the owner's own network (E1); its certificate is trusted the first time and
pinned after that, so the key is never sent to anything else.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import ssl
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from .local_model import check_local
from .models.base import ModelError
from .settings import Settings

_LOGGER = logging.getLogger(__name__)
CHANNEL = "router"
EVERY = 300  # seconds between looks
FAILURES = 3
MAX_DEVICES = 2000
LEASES = ("/api/dnsmasq/leases/search", "/api/kea/leases4/search",
          "/api/dhcpv4/leases/searchLease")


class RouterError(Exception):
    """Something to show the owner."""


def _text(value: object, limit: int = 64) -> str:
    text = str(value) if isinstance(value, str | int | float) else ""
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())[:limit]


def _mac(value: object) -> str:
    mac = _text(value, 17).lower()
    parts = mac.split(":")
    if len(parts) != 6 or not all(len(p) == 2 and all(c in "0123456789abcdef" for c in p)
                                  for p in parts):
        return ""
    return mac


def _rows(raw: object) -> list[dict]:
    if isinstance(raw, dict):
        raw = raw.get("rows", raw.get("arp", []))
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


class OPNsense:
    def __init__(self, url: str, key: str, secret: str, pin: str = "") -> None:
        self.url, self._auth, self.pin = url, aiohttp.BasicAuth(key, secret), pin
        self._session: aiohttp.ClientSession | None = None

    def _ssl(self) -> aiohttp.Fingerprint | bool | None:
        if not self.url.startswith("https://"):
            return None
        return aiohttp.Fingerprint(bytes.fromhex(self.pin)) if self.pin else False

    async def trust(self) -> str:
        """The first visit: read the router's certificate. Sends nothing."""
        if not self.url.startswith("https://") or self.pin:
            return self.pin
        parts = urlsplit(self.url)
        context = ssl.create_default_context()
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE  # read, then pin
        try:
            async with asyncio.timeout(10):
                _, writer = await asyncio.open_connection(parts.hostname, parts.port or 443,
                                                          ssl=context)
        except (OSError, TimeoutError) as err:
            raise RouterError(f"The router could not be reached at {parts.hostname}") from err
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
        writer.close()
        if not der:
            raise RouterError("The router's certificate could not be read")
        self.pin = hashlib.sha256(der).hexdigest()
        return self.pin

    async def _get(self, path: str, optional: bool = False) -> Any:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                                  trust_env=False)
        try:
            async with self._session.get(f"{self.url}{path}", ssl=self._ssl(), auth=self._auth,
                                         allow_redirects=False) as response:
                if response.status in (401, 403):
                    if optional:
                        return None
                    raise RouterError("The router did not accept that key, or the key's user "
                                      "may not read this. See the setup steps")
                if response.status == 404 and optional:
                    return None
                if response.status != 200:
                    raise RouterError(f"The router replied with error {response.status}")
                body = bytearray()
                while chunk := await response.content.read(65536):
                    body += chunk
                    if len(body) > 8 * 1024 * 1024:
                        raise RouterError("The router sent more than expected")
                return json.loads(body)
        except aiohttp.ServerFingerprintMismatch as err:
            raise RouterError("The router's certificate changed. If you renewed it, connect "
                              "again to trust the new one") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RouterError("The router could not be reached. Check the address; OPNsense "
                              "usually uses https://") from err
        except ValueError as err:
            raise RouterError("That address answered, but not like OPNsense") from err

    async def devices(self) -> dict[str, dict[str, str]]:
        """Every device the router knows: its ARP table, named from DHCP leases if allowed."""
        found: dict[str, dict[str, str]] = {}
        for row in _rows(await self._get("/api/diagnostics/interface/getArp")):
            mac = _mac(row.get("mac"))
            if mac and not row.get("expired"):
                found[mac] = {"ip": _text(row.get("ip"), 45),
                              "name": _text(row.get("hostname")) or _text(row.get("manufacturer")),
                              "where": _text(row.get("intf_description") or row.get("intf"))}
        for path in LEASES:
            for row in _rows(await self._get(path, optional=True)):
                mac = _mac(row.get("hwaddr") or row.get("mac"))
                name = _text(row.get("hostname"))
                if mac and name:
                    found.setdefault(mac, {"ip": _text(row.get("address"), 45), "name": "",
                                           "where": _text(row.get("if_descr"))})["name"] = name
        return dict(list(found.items())[:MAX_DEVICES])

    async def firmware(self) -> dict[str, Any]:
        raw = await self._get("/api/core/firmware/status", optional=True)
        if not isinstance(raw, dict):
            return {"update": None, "version": ""}
        product = raw.get("product") if isinstance(raw.get("product"), dict) else {}
        version = _text(product.get("product_version") or raw.get("product_version"), 32)
        return {"update": raw.get("status") in ("update", "upgrade"), "version": version}

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
        self._session = None


async def _address(url: object) -> str:
    if not isinstance(url, str) or not url.strip():
        raise RouterError("Enter the router's address")
    text = url.strip() if "://" in url else f"https://{url.strip()}"
    try:
        port = urlsplit(text).port
    except ValueError:
        raise RouterError("That is not a valid address") from None
    try:
        return await check_local(text, port or (443 if text.startswith("https") else 80))
    except ModelError as err:
        raise RouterError(str(err).replace("HOST:11434", "HOST")) from None


class Router:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time,
                 connect: Callable[..., OPNsense] = OPNsense,
                 houses: Callable[[], list[str]] = list) -> None:
        self._settings, self._clock, self._connect, self._houses = (
            settings, clock, connect, houses)
        self._router: OPNsense | None = None
        self.devices: dict[str, dict[str, str]] = {}
        self.firmware: dict[str, Any] = {"update": None, "version": ""}
        self.reason = ""
        self.looked = 0.0
        self._failures = 0
        self.on_change: Callable[[], Any] | None = None

    def saved(self) -> dict[str, Any]:
        return self._settings.channel(CHANNEL)

    def house(self) -> str | None:
        """The home this router belongs to: the one chosen, or the only one."""
        houses, chosen = self._houses(), self.saved().get("house")
        if chosen in houses:
            return chosen
        return houses[0] if len(houses) == 1 else None

    def view(self) -> dict[str, Any]:
        """For the page. Never the key or secret."""
        saved = self.saved()
        return {"url": saved.get("url", ""), "connected": bool(saved.get("url")) and not
                self.reason and bool(self.looked), "reason": self.reason,
                "devices": len(self.devices), "update": self.firmware["update"],
                "version": self.firmware["version"], "looked": self.looked,
                "list": sorted(({"mac": m, **d} for m, d in self.devices.items()),
                               key=lambda d: (d["where"], d["name"] or "~", d["ip"]))}

    def for_home(self) -> dict[str, Any]:
        """What Home Assistant's security check is told: names, addresses, and the network."""
        return {"type": "network", "devices": [
            {"key": f"router:{mac}", "name": d["name"] or f"a device at {d['ip']}",
             "where": d["where"]} for mac, d in self.devices.items()],
                "update": bool(self.firmware["update"]), "version": self.firmware["version"]}

    def _client(self) -> OPNsense | None:
        saved = self.saved()
        if not saved.get("url"):
            return None
        if self._router is None:
            self._router = self._connect(saved["url"], saved.get("key", ""),
                                         saved.get("secret", ""), saved.get("pin", ""))
        return self._router

    async def connect(self, url: object, key: object, secret: object) -> None:
        clean = await _address(url)
        saved = self.saved()
        key = key.strip() if isinstance(key, str) and len(key) <= 200 else ""
        secret = secret.strip() if isinstance(secret, str) and len(secret) <= 200 else ""
        if not secret and key == saved.get("key"):
            secret = saved.get("secret", "")  # left empty: keep the saved one
        if not key or not secret:
            raise RouterError("Enter the API key and secret from OPNsense")
        trial = self._connect(clean, key, secret, "")
        try:
            pin = await trial.trust()
            devices = await trial.devices()
            firmware = await trial.firmware()
        finally:
            await trial.close()
        await self.close()
        self._settings.update_channel(CHANNEL, {"url": clean, "key": key, "secret": secret,
                                                "pin": pin})
        self.devices, self.firmware, self.reason = devices, firmware, ""
        self.looked, self._failures = self._clock(), 0

    async def disconnect(self) -> None:
        await self.close()
        self._settings.update_channel(CHANNEL, {"url": "", "key": "", "secret": "", "pin": ""})
        self.devices, self.firmware = {}, {"update": None, "version": ""}
        self.reason, self.looked = "", 0.0

    async def tick(self) -> None:
        router = self._client()
        if router is None:
            return
        try:
            self.devices = await router.devices()
            self.firmware = await router.firmware()
            self.looked, self.reason, self._failures = self._clock(), "", 0
        except RouterError as err:
            self._failures += 1
            if self._failures >= FAILURES or "could not be reached" not in str(err):
                self.reason = str(err)
            return
        if self.on_change is not None:
            result = self.on_change()
            if asyncio.iscoroutine(result):
                await result

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # the router must not stop BRAM
                _LOGGER.exception("Router error")
            await asyncio.sleep(EVERY)

    async def close(self) -> None:
        if self._router is not None:
            await self._router.close()
        self._router = None
