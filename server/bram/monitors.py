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


async def probe(kind: str, url: str, transport: httpx.AsyncBaseTransport | None = None) -> bool:
    """Is it answering? Sends nothing about the home."""
    try:
        url = await check_local(url, KINDS[kind])
        if kind == "device":
            host, _, port = url.removeprefix("http://").removeprefix("https://").rpartition(":")
            return await _reachable(host.strip("[]"), int(port))
        # Frigate's login port has a self-made certificate. Nothing is sent to it, and
        # being asked to sign in means Frigate itself answered.
        frigate = kind == "frigate"
        async with httpx.AsyncClient(timeout=10, transport=transport, trust_env=False,
                                     verify=not frigate, follow_redirects=False) as client:
            response = await client.get(f"{url}/api/version")
            return response.status_code in ((200, 401, 403) if frigate else (200,))
    except (ModelError, httpx.HTTPError):
        return False


async def _reachable(host: str, port: int) -> bool:
    try:
        async with asyncio.timeout(5):
            _, writer = await asyncio.open_connection(host, port)
    except ConnectionRefusedError:
        return True  # something answered, so the device is up
    except (OSError, TimeoutError):
        return False
    writer.close()
    return True


class Monitors:
    def __init__(self, settings: Settings, alerts: Alerts,
                 check: Callable = probe) -> None:
        self._settings, self._alerts, self._check = settings, alerts, check
        self._failures: dict[str, int] = {}
        self.status: dict[str, bool] = {}

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
        self._alerts.forget(HOUSE, f"monitor {monitor_id}")

    async def tick(self) -> None:
        await asyncio.gather(*(self._one(m) for m in self.all()))

    async def _one(self, monitor: dict) -> None:
        monitor_id, key = monitor["id"], f"monitor {monitor['id']}"
        up = await self._check(monitor["kind"], monitor["url"])
        if monitor_id not in {m["id"] for m in self.all()}:
            return  # removed while it was being checked
        if up:
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
