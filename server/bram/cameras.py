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
import re
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
FAILURES = 3  # looks in a row before Frigate is shown as not answering
RECENT = 300  # events still going on are looked at again for this long
KEEP = 20  # events kept per camera
MAX_PICTURE = 2 * 1024 * 1024
LABELS = ("person", "car", "dog", "cat", "package", "bicycle", "motorcycle", "bird")
NAME = 64


class FrigateError(Exception):
    """Something to show the owner."""


def _why(err: BaseException, url: str) -> str:
    """Why Frigate could not be reached, in words the owner can act on."""
    parts = urlsplit(url)
    where = f"{parts.hostname}:{parts.port}"
    if isinstance(err, TimeoutError | asyncio.TimeoutError):
        return f"Frigate could not be reached: no reply from {where} in time"
    if isinstance(err, aiohttp.ClientConnectorCertificateError | ssl.SSLError):
        return f"Frigate could not be reached: a secure connection to {where} failed"
    if isinstance(err, aiohttp.ServerDisconnectedError) and url.startswith("http://"):
        return (f"Frigate could not be reached: {where} closed the connection. If this is "
                "Frigate's login port, use https://")
    if isinstance(err, aiohttp.ClientConnectorError | ConnectionError | OSError):
        return (f"Frigate could not be reached: nothing answered at {where}. Check the address "
                "and port, and that this port is open in Frigate")
    if isinstance(err, ValueError):
        return (f"{where} answered, but not like Frigate. Check the port: 5000, or 8971 "
                "with https://")
    return f"Frigate could not be reached at {where}"


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


def place(camera: str) -> str:
    """A camera's name as said in a sentence: RoofCamera and roof_camera are roof camera."""
    return " ".join(re.sub(r"([a-z])([A-Z])", r"\1 \2", camera).replace("_", " ")
                    .replace("-", " ").split()).lower()


def describe(event: dict[str, Any]) -> str:
    """A few plain words, such as "Alex at front door, in driveway"."""
    camera = place(event["camera"])
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
        self.zones: dict[str, list[str]] = {}  # each camera's zones in Frigate's settings

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
            raise FrigateError(_why(err, self.url)) from err
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

    async def _get(self, path: str, *, as_json: bool = True, limit: int = 16 * 1024 * 1024) -> Any:
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
                    if response.status == 400 and self.url.startswith("http://"):
                        raise FrigateError("Frigate refused plain http on this port. If this is "
                                           "Frigate's login port, use https://")
                    if response.status != 200:
                        raise FrigateError(f"Frigate replied with error {response.status}")
                    body = bytearray()
                    while chunk := await response.content.read(65536):  # every piece
                        body += chunk
                        if len(body) > limit:
                            raise FrigateError("Frigate sent more than expected")
                    body = bytes(body)
                    if not as_json:
                        return body, response.content_type
                    return json.loads(body)
            except aiohttp.ServerFingerprintMismatch as err:
                raise FrigateError("Frigate's certificate changed. If you renewed it, connect "
                                   "Frigate again to trust the new one") from err
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise FrigateError(_why(err, self.url)) from err
        raise FrigateError("Frigate did not accept the login")

    async def cameras(self) -> list[str]:
        config = await self._get("/api/config")
        found = config.get("cameras") if isinstance(config, dict) else None
        if not isinstance(found, dict):
            raise FrigateError("That does not look like Frigate")
        names = sorted(name for name in (_text(n) for n in found) if name)[:64]
        self.zones = {}
        for name in names:
            setup = found.get(name)
            zones = setup.get("zones") if isinstance(setup, dict) else None
            if isinstance(zones, dict):
                self.zones[name] = sorted(z for z in (_text(k) for k in zones) if z)[:20]
        return names

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

    async def picture(self, event: dict[str, Any]) -> bytes | None:
        """The event's snapshot; without snapshots on in Frigate, its thumbnail; without
        that, the camera's latest frame."""
        event_id, camera = quote(event["id"], safe=""), quote(event["camera"], safe="")
        tries = [f"/api/events/{event_id}/snapshot.jpg?bbox=1"] if event["picture"] else []
        tries += [f"/api/events/{event_id}/thumbnail.jpg", f"/api/{camera}/latest.jpg?h=480"]
        for path in tries:
            try:
                found = await self._get(path, as_json=False, limit=MAX_PICTURE)
            except FrigateError:
                continue
            if found and found[1] == "image/jpeg" and found[0][:2] == b"\xff\xd8":
                return found[0]
        return None

    async def close(self) -> None:
        if self._own and self._session is not None:
            await self._session.close()
        self._session = None


async def clean_address(url: object) -> str:
    if not isinstance(url, str) or not url.strip():
        raise FrigateError("Enter Frigate's address")
    text = url.strip() if "://" in url else f"http://{url.strip()}"
    return await _local(text)


async def addresses(url: object) -> list[str]:
    """The addresses to try. Without http:// or https://, the login port is https."""
    if not isinstance(url, str) or not url.strip():
        raise FrigateError("Enter Frigate's address")
    text = url.strip()
    if "://" in text:
        return [await _local(text)]
    try:
        port = urlsplit(f"http://{text}").port
    except ValueError:
        raise FrigateError("That is not a valid address") from None
    if port == 8971:
        return [await _local(f"https://{text}")]
    if port is None:
        return [await _local(f"http://{text}:5000"), await _local(f"https://{text}:8971")]
    return [await _local(f"http://{text}"), await _local(f"https://{text}")]


async def _local(text: str) -> str:
    try:
        port = urlsplit(text).port
    except ValueError:
        raise FrigateError("That is not a valid address") from None
    try:
        return await check_local(text, port or (8971 if text.startswith("https") else 5000))
    except ModelError as err:
        raise FrigateError(str(err).replace("HOST:11434", "HOST:5000")) from None


def for_home(event: dict[str, Any], description: str | None = None) -> dict[str, Any]:
    """What Home Assistant is told about an event. Checked again there. The model's words
    go only to a Home Assistant that knows them (0.42 or later)."""
    told = {"id": event["id"], "label": event["label"], "who": event["who"],
            "zones": event["zones"], "start": event["start"], "end": event["end"],
            "picture": event["picture"], "summary": describe(event)}
    return told if description is None else {**told, "description": description}


class Cameras:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time,
                 connect: Callable[..., Frigate] = Frigate,
                 houses: Callable[[], list[str]] = list) -> None:
        self._settings, self._clock, self._connect = settings, clock, connect
        self._houses = houses
        self._frigate: Frigate | None = None
        self.found: list[str] = []
        self.reason = ""
        self.offline: set[str] = set()
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.pictures: dict[str, tuple[str, bytes]] = {}  # camera -> (event id, jpeg)
        self._checked = 0.0
        self._failures = 0
        self.zones: dict[str, list[str]] = {}
        self._looked = 0.0
        self.on_event: Callable[[dict[str, Any], bool], Any] | None = None
        # The owner's own model describes events, only for cameras chosen for it (E2).
        self.describer: Callable[[bytes, str], Any] | None = None
        self.descriptions: dict[str, str] = {}  # event id: the model's words
        self.told: dict[str, None] = {}  # event ids Home Assistant told the owner about
        self.model_problem = ""
        self._describing: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._model_lock = asyncio.Lock()

    def saved(self) -> dict[str, Any]:
        return self._settings.channel(CHANNEL)

    def chosen(self) -> list[str]:
        return [c for c in self.saved().get("on", []) if c in self.found or not self.found]

    def house(self) -> str | None:
        """The home these cameras belong to: the one chosen, or the only one."""
        houses = self._houses()
        chosen = self.saved().get("house")
        if chosen in houses:
            return chosen
        return houses[0] if len(houses) == 1 else None

    def set_house(self, house_id: object) -> None:
        if house_id not in self._houses():
            raise FrigateError("Choose a connected home")
        self._settings.update_channel(CHANNEL, {"house": house_id})

    def names_for(self, house_id: str) -> list[str]:
        """The cameras whose events go to this home's Home Assistant."""
        return self.chosen() if self.saved().get("url") and house_id == self.house() else []

    def last(self, camera: str) -> dict[str, Any] | None:
        return (self.events.get(camera) or [None])[0]

    def described(self) -> list[str]:
        return [c for c in self.saved().get("describe", []) if c in self.chosen()]

    def set_describe(self, camera: object, on: object) -> None:
        if not isinstance(camera, str) or camera not in self.chosen() or not isinstance(on, bool):
            raise FrigateError("Turn on Watch for that camera first")
        chosen = [c for c in self.saved().get("describe", []) if c != camera]
        self._settings.update_channel(CHANNEL, {"describe": [*chosen, camera] if on else chosen})

    def description(self, event: dict[str, Any] | None) -> str | None:
        return self.descriptions.get(event["id"]) if event else None

    # --- told, and not news ---

    def mark_told(self, camera: object) -> None:
        """Home Assistant told the owner about this camera just now: its latest event."""
        event = self.last(camera) if isinstance(camera, str) else None
        if event is not None and self._clock() - event["start"] < RECENT:
            self.told[event["id"]] = None
            while len(self.told) > 200:
                self.told.pop(next(iter(self.told)))

    def quiet(self) -> list[dict[str, Any]]:
        return self.saved().get("quiet", [])

    def quiet_for(self, event: dict[str, Any] | None) -> dict[str, Any] | None:
        """What the owner said about events like this one: same camera, same kind of thing,
        same Frigate zones (none is a match for none)."""
        if event is None:
            return None
        zones = sorted(event["zones"])
        return next((q for q in self.quiet() if q["camera"] == event["camera"]
                     and q["label"] == event["label"] and q["zones"] == zones), None)

    def keep_quiet(self, camera: object, event_id: object, note: object) -> None:
        if not isinstance(camera, str) or camera not in self.chosen():
            raise FrigateError("Choose a camera BRAM watches")
        event = next((e for e in self.events.get(camera, []) if e["id"] == event_id), None)
        if event is None:
            raise FrigateError("That event is no longer listed")
        note = " ".join(note.split())[:80] if isinstance(note, str) else ""
        found = {"camera": camera, "label": event["label"], "zones": sorted(event["zones"]),
                 "note": note}
        rest = [q for q in self.quiet() if (q["camera"], q["label"], q["zones"]) !=
                (camera, event["label"], found["zones"])]
        self._settings.update_channel(CHANNEL, {"quiet": [*rest, found][-50:]})

    def allow(self, index: object) -> None:
        items = self.quiet()
        if not isinstance(index, int) or not 0 <= index < len(items):
            raise FrigateError("That is no longer listed")
        self._settings.update_channel(CHANNEL, {"quiet": items[:index] + items[index + 1:]})

    # --- teaching: what a camera sees, and does it matter ---

    def scene(self, camera: str) -> str:
        return self.saved().get("scenes", {}).get(camera, "")

    def set_scene(self, camera: object, text: object) -> None:
        if not isinstance(camera, str) or camera not in self.chosen() or not isinstance(text, str):
            raise FrigateError("Choose a camera BRAM watches")
        scenes = dict(self.saved().get("scenes", {}))
        scenes[camera] = " ".join("".join(c if c.isprintable() else " " for c in text)
                                  .split())[:600]
        self._settings.update_channel(CHANNEL, {"scenes": {k: v for k, v in scenes.items() if v}})

    def learned(self) -> list[dict[str, Any]]:
        return self.saved().get("learned", [])

    def learn(self, camera: object, event_id: object, matters: object, note: object = "") -> None:
        """The owner says whether an event matters, and what it was. Kept for the model."""
        if not isinstance(camera, str) or camera not in self.chosen() or not isinstance(
                matters, bool):
            raise FrigateError("Choose a camera BRAM watches")
        event = next((e for e in self.events.get(camera, []) if e["id"] == event_id), None)
        if event is None:
            raise FrigateError("That event is no longer listed")
        note = " ".join(note.split())[:200] if isinstance(note, str) else ""
        item = {"camera": camera, "id": event["id"], "label": event["label"],
                "zones": sorted(event["zones"]), "seen": self.description(event) or "",
                "matters": matters, "note": note, "at": round(self._clock())}
        rest = [x for x in self.learned() if x["id"] != event["id"]]
        self._settings.update_channel(CHANNEL, {"learned": [*rest, item][-200:]})

    def forget(self, index: object) -> None:
        items = self.learned()
        if not isinstance(index, int) or not 0 <= index < len(items):
            raise FrigateError("That is no longer listed")
        self._settings.update_channel(CHANNEL, {"learned": items[:index] + items[index + 1:]})

    def context(self, camera: str) -> dict[str, Any]:
        """What the model is given with a picture: the scene, and what the owner taught it."""
        lines = []
        for x in [x for x in self.learned() if x["camera"] == camera][-25:]:
            where = f" in {', '.join(x['zones'])}" if x["zones"] else ""
            seen = f" (you had said: {x['seen']})" if x["seen"] else ""
            note = f" The owner said it was: {x['note']}." if x["note"] else ""
            lines.append(f"A {x['label']}{where}{seen}: it "
                         f"{'mattered' if x['matters'] else 'did not matter'} to the owner.{note}")
        return {"scene": self.scene(camera), "taught": lines + self.notes(camera)}

    async def live(self, camera: object) -> bytes | None:
        """A camera's picture now, to look at while describing it. No model sees it."""
        frigate = self._client()
        if not isinstance(camera, str) or camera not in self.chosen() or frigate is None:
            return None
        try:
            found = await frigate._get(f"/api/{quote(camera, safe='')}/latest.jpg?h=480",
                                       as_json=False, limit=MAX_PICTURE)
        except FrigateError:
            return None
        if not found or found[1] != "image/jpeg" or found[0][:2] != b"\xff\xd8":
            return None
        return found[0]

    def notes(self, camera: str) -> list[str]:
        """What the owner said about this camera, for the model."""
        found = []
        for q in self.quiet():
            if q["camera"] == camera and q["note"]:
                where = f"in {', '.join(q['zones'])}" if q["zones"] else "outside every zone"
                found.append(f"{q['label']} {where}: {q['note']}")
        return found

    def view(self) -> dict[str, Any]:
        """For the page. Never the password."""
        saved = self.saved()
        on = set(saved.get("on", []))
        return {
            "url": saved.get("url", ""), "user": saved.get("user", ""), "house": self.house(),
            "connected": bool(saved.get("url")) and not self.reason and bool(self.found),
            "reason": self.reason, "pinned": bool(saved.get("pin")),
            "model_problem": self.model_problem,
            "quiet": [{**q, "name": place(q["camera"])} for q in self.quiet()],
            "learned": self.learned(),
            "cameras": [{"name": c, "on": c in on, "offline": c in self.offline,
                         "describe": c in saved.get("describe", []),
                         "scene": saved.get("scenes", {}).get(c, ""),
                         "last": self._with_words(self.last(c)),
                         "shot": c in self.pictures} for c in self.found],
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
        tries = await addresses(url)
        user = _text(user, 64) if isinstance(user, str) else ""
        password = password if isinstance(password, str) and len(password) <= 200 else ""
        if not user and password:
            raise FrigateError("Enter the Frigate username too")
        if user and not password:
            password = self.saved().get("password", "") if self.saved().get("user") == user \
                else ""
            if not password:
                raise FrigateError("Enter the Frigate password")
        first: FrigateError | None = None
        for clean in tries:
            trial = self._connect(clean, user, password, "")
            try:
                pin = await trial.trust()
                found = await trial.cameras()
                zones = trial.zones
                break
            except FrigateError as err:
                first = first or err
                if "could not be reached" not in str(err) and "plain http" not in str(err) \
                        and "not like Frigate" not in str(err):
                    raise  # it was Frigate, and it said no
            finally:
                await trial.close()
        else:
            raise first or FrigateError("Frigate could not be reached")
        await self._drop()
        keep = [c for c in self.saved().get("on", []) if c in found]
        self._settings.update_channel(CHANNEL, {"url": clean, "user": user, "password": password,
                                                "pin": pin, "on": keep})
        self.found, self.reason, self._checked = found, "", self._clock()
        self.zones = zones
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
        if not on:  # a camera turned off keeps nothing (E2), and is not described
            for event in self.events.get(camera, []):
                self.descriptions.pop(event["id"], None)
            self._settings.update_channel(CHANNEL, {"describe": [
                c for c in self.saved().get("describe", []) if c != camera]})
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
                self.zones = frigate.zones
            chosen = self.chosen()
            if chosen:
                self.offline = await frigate.offline(chosen)
                after = max(self._looked - RECENT, now - RECENT) if self._looked else now - RECENT
                for event in sorted(await frigate.events(chosen, after),
                                    key=lambda e: e["start"]):
                    await self._seen(frigate, event)
            self._looked = now
            self.reason, self._failures = "", 0
        except FrigateError as err:
            # A blip is not shown; three looks in a row, about 30 seconds, is.
            self._failures += 1
            if (self._failures >= FAILURES or not self.found
                    or "could not be reached" not in str(err)):
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
        # Again when a snapshot turns up for an event that had none.
        mark = f"{event['id']}:{event['picture']}"
        if newest and self.pictures.get(camera, ("",))[0] != mark:
            found = await frigate.picture(event)
            if found:
                self.pictures[camera] = (mark, found)
                self._describe_later(event, found)
        if self.on_event is not None:
            result = self.on_event(event, old is None)
            if asyncio.iscoroutine(result):
                await result

    def _with_words(self, event: dict[str, Any] | None) -> dict[str, Any] | None:
        if event is None:
            return None
        words, quiet = self.description(event), self.quiet_for(event)
        return {**event, **({"description": words} if words else {}),
                "told": event["id"] in self.told and quiet is None,
                "quiet": quiet["note"] or "not news" if quiet else ""}

    def _describe_later(self, event: dict[str, Any], picture: bytes) -> None:
        """On the side: a slow model never holds anything back (C6). One at a time."""
        if (self.describer is None or event["camera"] not in self.described()
                or event["id"] in self.descriptions or event["id"] in self._describing
                or self._clock() - event["start"] > RECENT or len(self._describing) >= 3):
            return
        self._describing.add(event["id"])
        task = asyncio.create_task(self._describe(event, picture))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _describe(self, event: dict[str, Any], picture: bytes) -> None:
        try:
            async with self._model_lock, asyncio.timeout(90):
                words = await self.describer(picture, place(event["camera"]),
                                             self.context(event["camera"]))
            self.model_problem = ""
        except (ModelError, TimeoutError) as err:
            words = None
            self.model_problem = (f"Your model could not describe a picture: {err}"
                                  if str(err) else "Your model took too long to describe a "
                                  "picture")
        finally:
            self._describing.discard(event["id"])
        if not words or event["camera"] not in self.described():
            return
        self.descriptions[event["id"]] = words
        while len(self.descriptions) > 200:
            self.descriptions.pop(next(iter(self.descriptions)))
        latest = next((e for e in self.events.get(event["camera"], [])
                       if e["id"] == event["id"]), event)
        if self.on_event is not None:
            result = self.on_event(latest, False)
            if asyncio.iscoroutine(result):
                await result

    def asked_about(self, text: str, house: str | None) -> str | None:
        """The camera a question names, by its name or one of its Frigate zones. Only cameras
        chosen for the model, and only for the home they belong to (E2, E4)."""
        if house not in (None, self.house()):
            return None
        words = f" {' '.join(re.sub(r'[^a-z0-9 ]', ' ', text.lower()).split())} "
        ready = self.described()
        for camera in ready:
            names = {place(camera).removesuffix(" camera").removesuffix(" cam"),
                     *(place(z) for z in self.zones.get(camera, []))}
            if any(len(n) > 2 and f" {n} " in words for n in names):
                return camera
        if len(ready) == 1 and re.search(r"\bcam(era)?s?\b", words):
            return ready[0]
        return None

    async def look(self, text: str, house: str | None = None) -> tuple[str, bytes] | None:
        """A camera's picture now, for a question about it. None if none is meant or ready."""
        camera = self.asked_about(text, house)
        frigate = self._client()
        if camera is None or frigate is None:
            return None
        try:
            found = await frigate._get(f"/api/{quote(camera, safe='')}/latest.jpg?h=720",
                                       as_json=False, limit=MAX_PICTURE)
        except FrigateError:
            return None
        if not found or found[1] != "image/jpeg" or found[0][:2] != b"\xff\xd8":
            return None
        return place(camera), found[0]

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
        for task in self._tasks:
            task.cancel()
        await self._drop()
