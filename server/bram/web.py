"""Config page. Cannot control the home, lower a tier, or approve an action."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import secrets
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from aiohttp import web

from .audit import Audit
from .local_model import check_local, local_models, open_model
from .models.base import ModelError
from .pairing import CODE_LIFETIME, Pairing
from .personality import CUSTOM_LIMIT, MODES, messages
from .settings import Settings, login_matches, owner_name

STATIC = Path(__file__).parent / "static"
COOKIE = "__Host-bram"
SESSION_LIFE, IDLE_LIFE = 12 * 3600, 1800
MAX_FAILURES, MAX_FAILURES_ALL, LOCKOUT = 5, 20, 900
# Creating the first login needs the code from the server's log, and this long to use it.
SETUP_WINDOW = 900
# Invented, so a sample never contains anything about the house.
SAMPLE = "The garage door has been open for 40 minutes."

HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self'; "
                                "img-src 'self'; connect-src 'self'; form-action 'none'; "
                                "base-uri 'none'; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
FILES = {"": "index.html", "app.js": "app.js", "style.css": "style.css", "icon.png": "icon.png"}


class ConfigPage:
    def __init__(self, settings: Settings, pairing: Pairing, audit: Audit,
                 fingerprint: str, connected: Callable[[], set[str]],
                 disconnect: Callable[[str], Awaitable[None]],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._settings, self._pairing, self._audit = settings, pairing, audit
        self._fingerprint, self._connected = fingerprint, connected
        self._disconnect, self._clock = disconnect, clock
        self._started = clock()
        self._setup_failures = 0
        # 40 bits, at most 5 guesses.
        self.setup_code = "".join(secrets.choice(CODE_LETTERS) for _ in range(8))
        self._sessions: dict[str, tuple[float, float, str]] = {}
        self._failures: dict[str, tuple[int, float]] = {}
        self._login_lock = asyncio.Lock()
        self._sample_lock = asyncio.Lock()

    def routes(self) -> list[web.RouteDef]:
        return [
            web.get("/", self._home), web.get("/ui/{file:[a-z.]*}", self._file),
            web.get("/api/state", self._state), web.post("/api/login", self._login),
            web.post("/api/setup", self._setup),
            web.post("/api/password", self._private(self._change_password)),
            web.post("/api/pair", self._confirmed(self._pair)),
            web.post("/api/unpair", self._confirmed(self._unpair)),
            web.post("/api/logout", self._private(self._logout)),
            web.get("/api/status", self._private(self._status)),
            web.get("/api/log", self._private(self._log)),
            web.get("/api/settings", self._private(self._get_settings)),
            web.post("/api/settings", self._private(self._save_settings)),
            web.post("/api/models", self._private(self._models)),
            web.post("/api/sample", self._private(self._sample)),
        ]

    # --- access ---

    def _signed_in(self, request: web.Request) -> bool:
        key = _key(request.cookies.get(COOKIE, ""))
        session = self._sessions.get(key)
        if session is None:
            return False
        expires, idle, record = session
        # A reset login ends every session.
        if self._clock() > min(expires, idle) or record != self._settings.login_record():
            del self._sessions[key]
            return False
        self._sessions[key] = (expires, self._clock() + IDLE_LIFE, record)
        return True

    def _private(self, handler: Callable) -> Callable:
        async def wrapped(request: web.Request) -> web.Response:
            if not self._signed_in(request):
                return _json({"error": "Sign in first"}, 401)
            if request.method == "POST" and not _same_origin(request):
                return _json({"error": "Request refused"}, 403)
            return await handler(request)
        return wrapped

    async def _login(self, request: web.Request) -> web.Response:
        if not _same_origin(request):
            return _json({"error": "Request refused"}, 403)
        body = await _body(request)
        refused = await self._check(request, body.get("user"), body.get("password"))
        if refused is not None:
            return refused
        self._audit.record("server", "config page", "signed in", "correct login", "ok")
        return self._start_session(self._settings.login_record() or "")

    async def _check(self, request: web.Request, user: object,
                     password: object) -> web.Response | None:
        """Check a login. Returns the refusal, or None when it is right."""
        who = request.remote or ""
        # One at a time, so guesses cannot run in parallel.
        async with self._login_lock:
            now = self._clock()
            self._failures = {k: v for k, v in self._failures.items() if now - v[1] < LOCKOUT}
            count = self._failures.get(who, (0, 0.0))[0]
            total = sum(v[0] for v in self._failures.values())
            if count >= MAX_FAILURES or total >= MAX_FAILURES_ALL:
                return _json({"error": "Too many attempts. Try again in 15 minutes."}, 429)
            ok = (isinstance(user, str) and isinstance(password, str) and await asyncio.to_thread(
                login_matches, self._settings.login_record(), user, password))
            if not ok:
                self._failures[who] = (count + 1, now)
                self._audit.record("server", "config page", "login refused", "wrong login",
                                   "refused")
                return _json({"error": "Wrong username or password"}, 403)
            self._failures.pop(who, None)
        return None

    def _confirmed(self, handler: Callable) -> Callable:
        """Signed in is not enough: the password must be entered again."""
        async def wrapped(request: web.Request) -> web.Response:
            body = await _body(request)
            owner = owner_name(self._settings.login_record() or '[""]')
            refused = await self._check(request, owner,
                                        body.pop("confirm", None))
            return refused if refused is not None else await handler(body)
        return self._private(wrapped)

    async def _change_password(self, request: web.Request) -> web.Response:
        body = await _body(request)
        record = self._settings.login_record()
        if record is None:
            return _json({"error": "Sign in first"}, 401)
        user, new = owner_name(record), body.get("new")
        refused = await self._check(request, user, body.get("confirm"))
        if refused is not None:
            return refused
        try:
            if not isinstance(new, str):
                raise ValueError("Enter a new password")
            self._settings.change_login(user, new)
        except ValueError as err:
            return _json({"error": str(err)}, 400)
        # Every other session ends; this one starts again.
        self._sessions.clear()
        self._audit.record("server", "config page", "password changed", "by owner", "ok",
                           approver="owner")
        return self._start_session(self._settings.login_record() or "")

    @property
    def needs_setup(self) -> bool:
        return self._settings.login_record() is None

    def _setup_open(self, request: web.Request) -> bool:
        try:
            local = ipaddress.ip_address(request.remote or "").is_private
        except ValueError:
            local = False
        return (local and self._settings.login_record() is None
                and self._setup_failures < MAX_FAILURES
                and self._clock() - self._started <= SETUP_WINDOW)

    async def _setup(self, request: web.Request) -> web.Response:
        body = await _body(request)
        # Checked after the body arrives: nothing below waits before a wrong code is counted,
        # so guesses sent together cannot slip past the limit.
        if not _same_origin(request) or not self._setup_open(request):
            return _json({"error": "Setup is closed. Restart the BRAM Server and reload."}, 403)
        user, password = body.get("user"), body.get("password")
        if not isinstance(user, str) or not isinstance(password, str):
            return _json({"error": "Enter a username and password"}, 400)
        code = str(body.get("code", "")).strip().upper().replace("-", "")
        if not secrets.compare_digest(code.encode(), self.setup_code.encode()):
            self._setup_failures += 1
            self._audit.record("server", "config page", "setup refused", "wrong code", "refused")
            return _json({"error": "That is not the setup code in the server's log"}, 403)
        async with self._login_lock:
            try:
                created = self._settings.create_login(user, password)
            except ValueError as err:
                return _json({"error": str(err)}, 400)
        if not created:
            return _json({"error": "A login already exists"}, 403)
        self._audit.record("server", "config page", "login created", "first-run setup", "ok")
        return self._start_session(self._settings.login_record() or "")

    def _start_session(self, record: str) -> web.Response:
        now = self._clock()
        token = secrets.token_urlsafe(32)
        self._sessions = {k: v for k, v in self._sessions.items() if min(v[:2]) > now}
        self._sessions[_key(token)] = (now + SESSION_LIFE, now + IDLE_LIFE, record)
        response = _json({"ok": True})
        response.set_cookie(COOKIE, token, max_age=SESSION_LIFE, secure=True, httponly=True,
                            samesite="Strict", path="/")
        return response

    async def _logout(self, request: web.Request) -> web.Response:
        self._sessions.pop(_key(request.cookies.get(COOKIE, "")), None)
        response = _json({"ok": True})
        response.del_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Strict")
        return response

    # --- pages ---

    async def _home(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/ui/")

    async def _file(self, request: web.Request) -> web.StreamResponse:
        name = FILES.get(request.match_info["file"])
        if name is None:
            raise web.HTTPNotFound
        return web.FileResponse(STATIC / name, headers=HEADERS)

    async def _state(self, request: web.Request) -> web.Response:
        return _json({"login_exists": self._settings.login_record() is not None,
                      "setup_open": self._setup_open(request),
                      "signed_in": self._signed_in(request)})

    async def _status(self, request: web.Request) -> web.Response:
        online = self._connected()
        return _json({"houses": [{"id": house_id, "name": name, "connected": house_id in online}
                                 for house_id, name in self._pairing.houses()]})

    async def _pair(self, body: dict) -> web.Response:
        name = body.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
            return _json({"error": "Enter a name for this home"}, 400)
        code = self._pairing.new_code(name.strip(), self._fingerprint)
        self._audit.record("server", "config page", "code created", "pairing", "ok",
                           approver="owner")
        return _json({"code": code, "minutes": CODE_LIFETIME // 60})

    async def _unpair(self, body: dict) -> web.Response:
        house_id = body.get("house_id")
        if not isinstance(house_id, str) or not self._pairing.remove(house_id):
            return _json({"error": "No such home"}, 400)
        await self._disconnect(house_id)
        self._audit.record(house_id, "config page", "unpaired", "removed by owner", "ok",
                           approver="owner")
        return _json({"ok": True})

    async def _log(self, request: web.Request) -> web.Response:
        names = dict(self._pairing.houses())
        return _json({"entries": [{
            "at": r["at"], "house": names.get(r["house_id"], r["house_id"]),
            "decision": r["decision"], "trigger": r["trigger"], "reason": r["reason"],
            "result": r["result"]} for r in self._audit.recent(200)]})

    async def _get_settings(self, request: web.Request) -> web.Response:
        modes = [{"id": k, "name": v[0], "about": v[1]} for k, v in MODES.items()]
        return _json({"settings": self._settings.all(), "modes": modes,
                      "custom_limit": CUSTOM_LIMIT})

    async def _save_settings(self, request: web.Request) -> web.Response:
        try:
            body = await _body(request)
            confirm = body.pop("confirm", None)
            values = await _valid(body)
            # The model sees household text, so changing it needs the password.
            if values.keys() & {"model_url", "model", "context"}:
                owner = owner_name(self._settings.login_record() or '[""]')
                refused = await self._check(request, owner, confirm)
                if refused is not None:
                    return refused
            self._settings.update(values)
        except (ValueError, ModelError) as err:
            return _json({"error": str(err)}, 400)
        # Names only: a custom style is personal text (E10).
        self._audit.record("server", "config page", "settings saved",
                           ", ".join(sorted(values)), "ok", approver="owner")
        return _json({"ok": True, "settings": self._settings.all()})

    async def _models(self, request: web.Request) -> web.Response:
        try:
            return _json({"models": await local_models(str((await _body(request)).get("url")))})
        except ModelError as err:
            return _json({"error": str(err)}, 400)

    async def _sample(self, request: web.Request) -> web.Response:
        try:
            values = await _valid(await _body(request))
            mode = values.get("personality", "professional")
            saved = self._settings.all()
            if not saved["model"]:
                raise ModelError("Choose and save a model first")
            if self._sample_lock.locked():
                raise ModelError("A sample is already running")
            async with self._sample_lock:
                model = await open_model(saved["model_url"], saved["model"], saved["context"])
                try:
                    reply = await model.chat(
                        messages(mode, values.get("custom_style", ""), SAMPLE))
                finally:
                    await model.close()
        except (ValueError, ModelError) as err:
            return _json({"error": str(err)}, 400)
        return _json({"facts": SAMPLE, "text": reply.text.strip()[:2000]})


async def _valid(body: dict) -> dict:
    values: dict = {}
    for key, value in body.items():
        if key == "model_url":
            values[key] = await check_local(str(value)) if value else ""
        elif key == "model" and isinstance(value, str) and len(value) <= 200:
            values[key] = value
        elif key == "context" and type(value) is int and 2048 <= value <= 262144:
            values[key] = value
        elif key == "personality" and isinstance(value, str) and value in MODES:
            values[key] = value
        elif key == "custom_style" and isinstance(value, str) and len(value) <= CUSTOM_LIMIT:
            values[key] = value
        else:
            raise ValueError(f"Invalid setting: {str(key)[:40]}")
    return values


def _key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _same_origin(request: web.Request) -> bool:
    return request.headers.get("Origin") == f"https://{request.host}"


async def _body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest
    return data


def _json(data: dict, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, headers=HEADERS)
