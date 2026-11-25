"""Watches things outside Home Assistant, on the owner's own network only."""
from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable

import httpx

from .alerts import Alerts
from .local_model import check_local
from .models.base import ModelError
from .settings import Settings

_LOGGER = logging.getLogger(__name__)
HOUSE = "server"  # monitors belong to the server, not to a house
EVERY = 60
FAILURES = 3
LIMIT = 20
KINDS = {"ollama": 11434, "frigate": 5000, "device": 80}


async def diagnose(kind: str, url: str, transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Empty if it is answering, or why not. Sends nothing about the home."""
    try:
        url = await check_local(url, KINDS[kind])
    except ModelError as err:
        return str(err)
    if kind == "device":
        host, _, port = url.partition("://")[2].rpartition(":")
        return await _reach(host.strip("[]"), int(port))
    # Frigate's login port has a self-made certificate. Nothing is sent to it, and
    # being asked to sign in means Frigate itself answered.
    frigate, reason = kind == "frigate", ""
    good = (200, 401, 403) if frigate else (200,)
    # People leave off https, so Frigate is tried both ways.
    host = url.partition("://")[2]
    async with httpx.AsyncClient(timeout=10, transport=transport, trust_env=False,
                                 verify=not frigate, follow_redirects=False) as client:
        for address in [f"https://{host}", f"http://{host}"] if frigate else [url]:
            try:
                response = await client.get(f"{address}/api/version")
            except httpx.TimeoutException:
                reason = reason or "no reply in time"
            except httpx.HTTPError as err:
                untrusted = "CERTIFICATE_VERIFY" in str(err).upper()
                reason = reason or ("its certificate is not trusted" if untrusted
                                    else "could not connect")
            else:
                if response.status_code in good:
                    return ""
                reason = f"it replied with error {response.status_code}"
    return reason


async def probe(kind: str, url: str, transport: httpx.AsyncBaseTransport | None = None) -> bool:
    return not await diagnose(kind, url, transport)


async def _reach(host: str, port: int) -> str:
    try:
        async with asyncio.timeout(5):
            _, writer = await asyncio.open_connection(host, port)
    except ConnectionRefusedError:
        return ""  # something answered, so the device is up
    except TimeoutError:
        return "no reply in time"
    except OSError:
        return "could not connect"
    writer.close()
    return ""


class Monitors:
    def __init__(self, settings: Settings, alerts: Alerts,
                 check: Callable = diagnose) -> None:
        self._settings, self._alerts, self._check = settings, alerts, check
        self._failures: dict[str, int] = {}
        self.status: dict[str, bool] = {}
        self.reasons: dict[str, str] = {}

    def all(self) -> list[dict]:
        return self._settings.channel("monitors").get("list", [])

    def _save(self, items: list[dict]) -> None:
        self._settings.update_channel("monitors", {"list": items})

    async def add(self, kind: object, name: object, url: object) -> None:
        if kind not in KINDS or not isinstance(name, str) or not isinstance(url, str):
            raise ValueError("Choose what to watch")
        name = " ".join("".join(c if c.isprintable() else " " for c in name).split())
        if not 1 <= len(name) <= 60:
            raise ValueError("Enter a name of up to 60 characters")
        if len(self.all()) >= LIMIT:
            raise ValueError(f"At most {LIMIT} monitors")
        text = url.strip() if "://" in url else f"http://{url.strip()}"
        clean = await check_local(text, KINDS[kind])
        monitor = {"id": secrets.token_hex(6), "kind": kind, "name": name, "url": clean}
        self._save([*self.all(), monitor])
        await self._one(monitor)  # show a result now, not at the next pass

    def remove(self, monitor_id: object) -> None:
        self._save([m for m in self.all() if m["id"] != monitor_id])
        self._failures.pop(str(monitor_id), None)
        self.status.pop(str(monitor_id), None)
        self.reasons.pop(str(monitor_id), None)
        self._alerts.forget(HOUSE, f"monitor {monitor_id}")

    async def tick(self) -> None:
        await asyncio.gather(*(self._one(m) for m in self.all()))

    async def _one(self, monitor: dict) -> None:
        monitor_id, key = monitor["id"], f"monitor {monitor['id']}"
        reason = await self._check(monitor["kind"], monitor["url"])
        if monitor_id not in {m["id"] for m in self.all()}:
            return  # removed while it was being checked
        self.reasons[monitor_id] = reason
        if not reason:
            self._failures[monitor_id] = 0
            self.status[monitor_id] = True
            self._alerts.clear(HOUSE, key, f"{monitor['name']} is back.", safety=False)
            return
        self._failures[monitor_id] = self._failures.get(monitor_id, 0) + 1
        if self._failures[monitor_id] >= FAILURES:
            self.status[monitor_id] = False
            self._alerts.raise_alert(HOUSE, key, f"{monitor['name']} is not answering.",
                                     safety=False)

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # one bad monitor must not stop the rest
                _LOGGER.exception("Monitor error")
            await asyncio.sleep(EVERY)
