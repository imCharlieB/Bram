"""Cameras, through Frigate. BRAM only reads from Frigate; it never changes a camera,
a recording, or a Frigate setting.

Frigate is on the owner's own network (E1). With Frigate's login port, its self-made
certificate is trusted the first time and pinned after that, so the password is never sent
to anything else. Nothing is on until the owner turns on a camera (E2, F5).
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
from urllib.parse import quote, urlsplit

import aiohttp

from .local_model import check_local
from .models.base import ModelError
from .settings import Settings

_LOGGER = logging.getLogger(__name__)
CHANNEL = "cameras"
EVERY = 10  # seconds between looks at Frigate's events
CONFIG_EVERY = 600  # cameras added in Frigate show up within ten minutes
RECENT = 300  # events still going on are looked at again for this long
KEEP = 20  # events kept per camera
MAX_PICTURE = 2 * 1024 * 1024
LABELS = ("person", "car", "dog", "cat", "package", "bicycle", "motorcycle", "bird")
NAME = 64


class FrigateError(Exception):
    """Something to show the owner."""


def _text(value: object, limit: int = NAME) -> str:
    text = str(value) if isinstance(value, str | int | float) else ""
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())[:limit]


def _who(sub_label: object) -> str:
    """Frigate's sub label: a name, or [name, score] in newer versions."""
    if isinstance(sub_label, list | tuple) and sub_label:
        sub_label = sub_label[0]
    return _text(sub_label)


def event_from(raw: object) -> dict[str, Any] | None:
    """Only the fields BRAM uses, checked. Frigate's text is data."""
    if not isinstance(raw, dict):
        return None
    event_id, camera = _text(raw.get("id"), 80), _text(raw.get("camera"))
    start = raw.get("start_time")
    if not event_id or not camera or not isinstance(start, int | float):
        return None
    end = raw.get("end_time")
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    score = raw.get("top_score") or data.get("top_score") or data.get("score") or 0
    zones = raw.get("zones") if isinstance(raw.get("zones"), list) else []
    return {
        "id": event_id, "camera": camera, "label": _text(raw.get("label"), 32) or "object",
        "who": _who(raw.get("sub_label")),
        "zones": [z for z in (_text(z) for z in zones[:10]) if z],
        "start": float(start), "end": float(end) if isinstance(end, int | float) else None,
        "score": round(float(score), 2) if isinstance(score, int | float) else 0,
        "picture": bool(raw.get("has_snapshot")),
    }


def describe(event: dict[str, Any]) -> str:
    """A few plain words, such as "Alex at front door, in driveway"."""
    camera = event["camera"].replace("_", " ")
    what = event["who"] or event["label"]
    zones = ", ".join(z.replace("_", " ") for z in event["zones"])
    where = f", in {zones}" if zones else ""
    return f"{what} at {camera}{where}"


class Frigate:
    """One connection to Frigate: plain http, or its login port with a pinned certificate."""

    def __init__(self, url: str, user: str = "", password: str = "", pin: str = "",
                 session: aiohttp.ClientSession | None = None) -> None:
        self.url, self._user, self._password, self.pin = url, user, password, pin
        self._session = session
        self._own = session is None
        self._signed_in = False

    async def _open(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15), trust_env=False,
                cookie_jar=aiohttp.CookieJar(unsafe=True))  # unsafe: allows an IP address
        return self._session

    def _ssl(self) -> aiohttp.Fingerprint | bool | None:
        if not self.url.startswith("https://"):
            return None
        return aiohttp.Fingerprint(bytes.fromhex(self.pin)) if self.pin else False

    async def trust(self) -> str:
        """The first visit to a login port: read its certificate. Sends nothing."""
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
            raise FrigateError("Frigate could not be reached") from err
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
        writer.close()
        if not der:
            raise FrigateError("Frigate's certificate could not be read")
        self.pin = hashlib.sha256(der).hexdigest()
        return self.pin

    async def _sign_in(self) -> None:
        if not self._user or self._signed_in:
            return
        session = await self._open()
        async with session.post(f"{self.url}/api/login", ssl=self._ssl(), allow_redirects=False,
                                json={"user": self._user, "password": self._password}) as r:
            if r.status in (401, 403):
                raise FrigateError("Frigate did not accept that username and password")
            if r.status != 200:
                raise FrigateError(f"Frigate's sign-in replied with error {r.status}")
        self._signed_in = True

    async def _get(self, path: str, *, as_json: bool = True, limit: int = 4 * 1024 * 1024) -> Any:
        session = await self._open()
        for attempt in (1, 2):
            try:
                await self._sign_in()
                async with session.get(f"{self.url}{path}", ssl=self._ssl(),
                                       allow_redirects=False) as response:
                    if response.status == 401 and self._user and attempt == 1:
                        self._signed_in = False  # the sign-in ran out; once more
                        continue
                    if response.status in (401, 403):
                        raise FrigateError("Frigate asks for a login. Enter a Frigate user "
                                           "that can only view")
                    if response.status == 404:
                        return None
                    if response.status != 200:
                        raise FrigateError(f"Frigate replied with error {response.status}")
                    body = await response.content.read(limit + 1)
                    if len(body) > limit:
                        raise FrigateError("Frigate sent more than expected")
                    if not as_json:
                        return body, response.content_type
                    return json.loads(body)
            except aiohttp.ServerFingerprintMismatch as err:
                raise FrigateError("Frigate's certificate changed. If you renewed it, connect "
                                   "Frigate again to trust the new one") from err
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise FrigateError("Frigate could not be reached") from err
        raise FrigateError("Frigate did not accept the login")

    async def cameras(self) -> list[str]:
        config = await self._get("/api/config")
        found = config.get("cameras") if isinstance(config, dict) else None
        if not isinstance(found, dict):
            raise FrigateError("That does not look like Frigate")
        return sorted(name for name in (_text(n) for n in found) if name)[:64]

    async def events(self, cameras: list[str], after: float) -> list[dict[str, Any]]:
        names = ",".join(quote(c, safe="") for c in cameras)
        raw = await self._get(f"/api/events?cameras={names}&after={int(after)}&limit=100"
                              "&include_thumbnails=0")
        return [e for e in (event_from(r) for r in (raw if isinstance(raw, list) else [])) if e]

    async def offline(self, cameras: list[str]) -> set[str]:
        """Cameras Frigate is getting no picture from."""
        stats = await self._get("/api/stats")
        found = stats.get("cameras") if isinstance(stats, dict) else None
        if not isinstance(found, dict):
            return set()
        return {c for c in cameras if isinstance(found.get(c), dict)
                and not found[c].get("camera_fps")}

    async def picture(self, event_id: str) -> tuple[bytes, str] | None:
        found = await self._get(f"/api/events/{quote(event_id, safe='')}/snapshot.jpg?bbox=1",
                                as_json=False, limit=MAX_PICTURE)
        if not found:
            return None
        body, kind = found
        return (body, "image/jpeg") if kind == "image/jpeg" and body[:2] == b"\xff\xd8" else None

    async def close(self) -> None:
        if self._own and self._session is not None:
            await self._session.close()
        self._session = None


async def clean_address(url: object) -> str:
    if not isinstance(url, str) or not url.strip():
        raise FrigateError("Enter Frigate's address")
    text = url.strip() if "://" in url else f"http://{url.strip()}"
    try:
        port = urlsplit(text).port
    except ValueError:
        raise FrigateError("That is not a valid address") from None
    try:
        return await check_local(text, port or (8971 if text.startswith("https") else 5000))
    except ModelError as err:
        raise FrigateError(str(err).replace("HOST:11434", "HOST:5000")) from None


class Cameras:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time,
                 connect: Callable[..., Frigate] = Frigate) -> None:
        self._settings, self._clock, self._connect = settings, clock, connect
        self._frigate: Frigate | None = None
        self.found: list[str] = []
        self.reason = ""
        self.offline: set[str] = set()
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.pictures: dict[str, tuple[str, bytes]] = {}  # camera -> (event id, jpeg)
        self._checked = 0.0
        self._looked = 0.0
        self.on_event: Callable[[dict[str, Any], bool], Any] | None = None

    def saved(self) -> dict[str, Any]:
        return self._settings.channel(CHANNEL)

    def chosen(self) -> list[str]:
        return [c for c in self.saved().get("on", []) if c in self.found or not self.found]

    def view(self) -> dict[str, Any]:
        """For the page. Never the password."""
        saved = self.saved()
        on = set(saved.get("on", []))
        return {
            "url": saved.get("url", ""), "user": saved.get("user", ""),
            "connected": bool(saved.get("url")) and not self.reason and bool(self.found),
            "reason": self.reason, "pinned": bool(saved.get("pin")),
            "cameras": [{"name": c, "on": c in on, "offline": c in self.offline,
                         "last": (self.events.get(c) or [None])[0]} for c in self.found],
        }

    def _client(self) -> Frigate | None:
        saved = self.saved()
        if not saved.get("url"):
            return None
        if self._frigate is None:
            self._frigate = self._connect(saved["url"], saved.get("user", ""),
                                          saved.get("password", ""), saved.get("pin", ""))
        return self._frigate

    async def _drop(self) -> None:
        if self._frigate is not None:
            await self._frigate.close()
        self._frigate = None

    async def connect(self, url: object, user: object = "", password: object = "") -> None:
        clean = await clean_address(url)
        user = _text(user, 64) if isinstance(user, str) else ""
        password = password if isinstance(password, str) and len(password) <= 200 else ""
        if not user and password:
            raise FrigateError("Enter the Frigate username too")
        if user and not password:
            password = self.saved().get("password", "") if self.saved().get("user") == user \
                else ""
            if not password:
                raise FrigateError("Enter the Frigate password")
        trial = self._connect(clean, user, password, "")
        try:
            pin = await trial.trust()
            found = await trial.cameras()
        finally:
            await trial.close()
        await self._drop()
        keep = [c for c in self.saved().get("on", []) if c in found]
        self._settings.update_channel(CHANNEL, {"url": clean, "user": user, "password": password,
                                                "pin": pin, "on": keep})
        self.found, self.reason, self._checked = found, "", self._clock()
        self.offline = set()

    async def disconnect(self) -> None:
        await self._drop()
        self._settings.update_channel(CHANNEL, {"url": "", "user": "", "password": "", "pin": "",
                                                "on": []})
        self.found, self.reason, self.offline = [], "", set()
        self.events, self.pictures = {}, {}

    def choose(self, camera: object, on: object) -> None:
        if not isinstance(camera, str) or camera not in self.found or not isinstance(on, bool):
            raise FrigateError("Choose a camera Frigate has")
        chosen = [c for c in self.saved().get("on", []) if c != camera]
        self._settings.update_channel(CHANNEL, {"on": [*chosen, camera] if on else chosen})
        if not on:  # a camera turned off keeps nothing (E2)
            self.events.pop(camera, None)
            self.pictures.pop(camera, None)
            self.offline.discard(camera)

    async def tick(self) -> None:
        frigate = self._client()
        if frigate is None:
            return
        now = self._clock()
        try:
            if not self.found or now - self._checked >= CONFIG_EVERY:
                self.found, self._checked = await frigate.cameras(), now
            chosen = self.chosen()
            if chosen:
                self.offline = await frigate.offline(chosen)
                after = max(self._looked - RECENT, now - RECENT) if self._looked else now - RECENT
                for event in sorted(await frigate.events(chosen, after),
                                    key=lambda e: e["start"]):
                    await self._seen(frigate, event)
            self._looked = now
            self.reason = ""
        except FrigateError as err:
            self.reason = str(err)

    async def _seen(self, frigate: Frigate, event: dict[str, Any]) -> None:
        camera = event["camera"]
        if camera not in self.chosen():
            return
        kept = self.events.setdefault(camera, [])
        old = next((e for e in kept if e["id"] == event["id"]), None)
        if old == event:
            return
        kept[:] = sorted([event, *(e for e in kept if e["id"] != event["id"])],
                         key=lambda e: -e["start"])[:KEEP]
        newest = kept[0]["id"] == event["id"]
        if newest and event["picture"] and self.pictures.get(camera, ("",))[0] != event["id"]:
            try:
                found = await frigate.picture(event["id"])
            except FrigateError:
                found = None
            if found:
                self.pictures[camera] = (event["id"], found[0])
        if self.on_event is not None:
            result = self.on_event(event, old is None)
            if asyncio.iscoroutine(result):
                await result

    def picture(self, camera: object) -> bytes | None:
        if not isinstance(camera, str) or camera not in self.chosen():
            return None
        return self.pictures.get(camera, ("", None))[1]

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # Frigate must not stop BRAM
                _LOGGER.exception("Camera error")
            await asyncio.sleep(EVERY)

    async def close(self) -> None:
        await self._drop()
