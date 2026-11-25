"""Config page. Cannot control the home, lower a tier, or approve an action."""
from __future__ import annotations

import asyncio
import hashlib
import io
import ipaddress
import secrets
import time
from collections.abc import Awaitable, Callable
from importlib.metadata import version
from pathlib import Path
from zoneinfo import available_timezones

import segno
from aiohttp import web

from .alerts import Alerts, Outgoing
from .audit import KINDS, Audit
from .channels import TOKEN, ChannelError, Ntfy, Telegram, new_topic
from .chat import MAX_TEXT, Busy, Chat
from .local_model import check_local, local_models, open_model
from .models.base import ModelError
from .monitors import Monitors
from .pairing import CODE_LIFETIME, Pairing
from .personality import CUSTOM_LIMIT, MODES, messages
from .settings import Settings, login_matches, owner_name
from .speech import MAX_AUDIO, MAX_SPEAK, Speech, SpeechError
from .world import World

STATIC = Path(__file__).parent / "static"
COOKIE = "__Host-bram"
SESSION_LIFE, IDLE_LIFE = 12 * 3600, 1800
MAX_FAILURES, MAX_FAILURES_ALL, LOCKOUT = 5, 20, 900
# The first visitor may create the login, but only this long after the server starts.
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
FILES = {"": "index.html", "app.js": "app.js", "style.css": "style.css", "icon.png": "icon.png",
         "recorder.js": "recorder.js"}


class ConfigPage:
    def __init__(self, settings: Settings, pairing: Pairing, audit: Audit,
                 fingerprint: str, connected: Callable[[], set[str]],
                 disconnect: Callable[[str], Awaitable[None]], alerts: Alerts | None = None,
                 worlds: Callable[[], dict[str, World]] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._settings, self._pairing, self._audit = settings, pairing, audit
        self._fingerprint, self._connected = fingerprint, connected
        self._disconnect, self._clock = disconnect, clock
        self._started = clock()
        self._alerts = alerts
        self.monitors = Monitors(settings, alerts) if alerts is not None else None
        self.ntfy = Ntfy(settings, self._answer)
        self.speech = Speech(settings)
        self._worlds = worlds or dict
        self.chat = Chat(settings, pairing, audit, self._worlds, self.monitors)
        self.telegram = Telegram(settings, self._answer, talk=self._telegram_talk,
                                 hear=self.speech.hear)
        self._sessions: dict[str, tuple[float, float, str]] = {}
        self._failures: dict[str, tuple[int, float]] = {}
        self._login_lock = asyncio.Lock()
        self._sample_lock = asyncio.Lock()

    def routes(self) -> list[web.RouteDef]:
        return [
            web.get("/", self._home), web.get("/ui/{file:[a-z.]*}", self._file),
            web.get("/api/state", self._state), web.post("/api/login", self._login),
            web.post("/api/setup", self._setup),
            web.get("/api/profile", self._private(self._profile)),
            web.post("/api/username", self._private(self._change_username)),
            web.post("/api/logout-others", self._private(self._logout_others)),
            web.post("/api/password", self._private(self._change_password)),
            web.get("/api/speech", self._private(self._get_speech)),
            web.post("/api/speech", self._confirmed(self._save_speech)),
            web.post("/api/hear", self._private(self._hear)),
            web.post("/api/speak", self._private(self._speak)),
            web.get("/api/chat", self._private(self._chat_history)),
            web.post("/api/chat", self._private(self._chat_ask)),
            web.post("/api/chat-clear", self._private(self._chat_clear)),
            web.get("/api/monitors", self._private(self._list_monitors)),
            web.post("/api/monitors", self._private(self._add_monitor)),
            web.post("/api/monitor-remove", self._private(self._remove_monitor)),
            web.get("/api/messages", self._private(self._messages)),
            web.get("/api/ntfy-qr", self._private(self._ntfy_qr)),
            web.post("/api/ntfy", self._confirmed(self._save_ntfy)),
            web.post("/api/telegram", self._confirmed(self._save_telegram)),
            web.post("/api/telegram-link", self._confirmed(self._telegram_link)),
            web.post("/api/quiet", self._private(self._save_quiet)),
            web.post("/api/test-message", self._private(self._test_message)),
            web.post("/api/unmute", self._private(self._unmute)),
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

    def _answer(self, action: str, by: str) -> str:
        return self._alerts.answer(action, by) if self._alerts else "That is no longer active."

    async def _telegram_talk(self, text: str) -> str:
        return (await self.chat.ask("telegram", text)).text

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

    def _setup_open(self, request: web.Request) -> bool:
        try:
            local = ipaddress.ip_address(request.remote or "").is_private
        except ValueError:
            local = False
        return (local and self._settings.login_record() is None
                and self._clock() - self._started <= SETUP_WINDOW)

    async def _setup(self, request: web.Request) -> web.Response:
        body = await _body(request)
        if not _same_origin(request) or not self._setup_open(request):
            return _json({"error": "Setup is closed. Restart the BRAM Server and reload."}, 403)
        user, password = body.get("user"), body.get("password")
        if not isinstance(user, str) or not isinstance(password, str):
            return _json({"error": "Enter a username and password"}, 400)
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
        self.chat.clear(self._chat_key(request))
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
        houses = [{"id": house_id, "name": name, "connected": house_id in online,
                   "version": self._house_version(house_id)}
                  for house_id, name in self._pairing.houses()]
        return _json({"version": version("bram-core"), "houses": houses})

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
        if self._alerts is not None:
            self._alerts.forget_house(house_id)
        self._audit.record(house_id, "config page", "unpaired", "removed by owner", "ok",
                           approver="owner")
        return _json({"ok": True})

    def _house_version(self, house_id: str) -> str:
        world = self._worlds().get(house_id)
        return world.version if world is not None else ""

    async def _log(self, request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get("limit", "50"))
            before = int(request.query["before"]) if "before" in request.query else None
        except ValueError:
            return _json({"error": "Invalid number"}, 400)
        kind = request.query.get("kind", "")
        if not 1 <= limit <= 200 or not 0 <= (before or 0) < 2**62 or kind not in ("", *KINDS):
            return _json({"error": "Invalid filter"}, 400)
        names = dict(self._pairing.houses())
        return _json({"entries": [{
            "id": r["id"], "at": r["at"], "house": names.get(r["house_id"], r["house_id"]),
            "decision": r["decision"], "trigger": r["trigger"], "reason": r["reason"],
            "result": r["result"]} for r in self._audit.recent(limit, before, kind)]})

    async def _profile(self, request: web.Request) -> web.Response:
        now, record = self._clock(), self._settings.login_record() or '[""]'
        count = sum(1 for v in self._sessions.values() if min(v[:2]) > now and v[2] == record)
        return _json({"user": owner_name(record), "sessions": count})

    async def _logout_others(self, request: web.Request) -> web.Response:
        key = _key(request.cookies.get(COOKIE, ""))
        self._sessions = {k: v for k, v in self._sessions.items() if k == key}
        self.chat.clear_others(f"web:{key}", "web:")
        self._audit.record("server", "config page", "signed out others", "by owner", "ok",
                           approver="owner")
        return _json({"ok": True})

    async def _change_username(self, request: web.Request) -> web.Response:
        body = await _body(request)
        record, new, confirm = self._settings.login_record(), body.get("new"), body.get("confirm")
        if record is None:
            return _json({"error": "Sign in first"}, 401)
        refused = await self._check(request, owner_name(record), confirm)
        if refused is not None:
            return refused
        try:
            if not isinstance(new, str) or not isinstance(confirm, str):
                raise ValueError("Enter a new username")
            self._settings.change_login(new, confirm)
        except ValueError as err:
            return _json({"error": str(err)}, 400)
        self._sessions.clear()
        self._audit.record("server", "config page", "username changed", "by owner", "ok",
                           approver="owner")
        return self._start_session(self._settings.login_record() or "")

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

    async def _messages(self, request: web.Request) -> web.Response:
        n, t = self._settings.channel("ntfy"), self._settings.channel("telegram")
        names = dict(self._pairing.houses())
        muted = self._alerts.muted() if self._alerts else []
        return _json({
            "ntfy": {"on": bool(n.get("on")), "url": n.get("url", "http://ntfy:80"),
                     "phone_url": n.get("phone_url", ""), "topic": n.get("topic", ""),
                     "link": self._ntfy_link(),
                     "quiet": n.get("quiet", {})},
            # The token itself is never sent back.
            "telegram": {"on": bool(t.get("on")), "token_saved": bool(t.get("token")),
                         "bot": t.get("bot", ""), "linked": bool(t.get("user_id")),
                         "chat": bool(t.get("chat")),
                         "quiet": t.get("quiet", {})},
            "muted": [{**m, "house": names.get(m["house_id"], m["house_id"])} for m in muted]})

    def _ntfy_link(self) -> str:
        """Opens the ntfy app on the right server and topic."""
        c = self._settings.channel("ntfy")
        if not c.get("phone_url") or not c.get("topic"):
            return ""
        scheme, _, host = c["phone_url"].partition("://")
        return f"ntfy://{host}/{c['topic']}" + ("" if scheme == "https" else "?secure=false")

    async def _ntfy_qr(self, request: web.Request) -> web.Response:
        link = self._ntfy_link()
        if not link:
            raise web.HTTPNotFound
        out = io.BytesIO()
        segno.make(link, error="m").save(out, kind="svg", scale=5, border=3, light="#ffffff",
                                         dark="#000000")
        return web.Response(body=out.getvalue(), content_type="image/svg+xml", headers=HEADERS)

    async def _save_ntfy(self, body: dict) -> web.Response:
        try:
            url = await check_local(str(body.get("url", "")), default_port=80)
            phone = await check_local(str(body.get("phone_url", "")), default_port=80)
        except ModelError as err:
            return _json({"error": str(err)}, 400)
        values = {"on": body.get("on") is True, "url": url, "phone_url": phone}
        if body.get("new_topic") is True or not self._settings.channel("ntfy").get("topic"):
            values |= {"topic": new_topic(), "reply": new_topic()}
        self._settings.update_channel("ntfy", values)
        self._audit.record("server", "config page", "ntfy saved",
                           "on" if values["on"] else "off", "ok", approver="owner")
        return _json({"ok": True})

    async def _save_telegram(self, body: dict) -> web.Response:
        token, values = body.get("token"), {
            "on": body.get("on") is True, "chat": body.get("chat") is True}
        if token:
            if not isinstance(token, str) or not TOKEN.fullmatch(token.strip()):
                return _json({"error": "That does not look like a bot token"}, 400)
            token = token.strip()
            if token != self._settings.channel("telegram").get("token"):
                try:
                    bot = await self.telegram.bot_name(token)
                except ChannelError as err:
                    return _json({"error": str(err)}, 400)
                # A different bot must be linked again.
                values |= {"token": token, "bot": bot, "user_id": None}
        if body.get("remove") is True:
            values = {"on": False, "chat": False, "token": "", "bot": "", "user_id": None}
            self.chat.clear("telegram")
        self._settings.update_channel("telegram", values)
        self._audit.record("server", "config page", "telegram saved",
                           "on" if values["on"] else "off", "ok", approver="owner")
        return _json({"ok": True})

    async def _telegram_link(self, body: dict) -> web.Response:
        t = self._settings.channel("telegram")
        if not t.get("on") or not t.get("bot"):
            return _json({"error": "Save a bot token and turn Telegram on first"}, 400)
        return _json({"url": f"https://t.me/{t['bot']}?start={self.telegram.new_link()}"})

    async def _save_quiet(self, request: web.Request) -> web.Response:
        body = await _body(request)
        name, start, end = body.get("channel"), body.get("from"), body.get("to")
        zone = body.get("timezone")
        hours = (None, *range(24))
        if (name not in ("ntfy", "telegram") or isinstance(start, bool) or isinstance(end, bool)
                or start not in hours or end not in hours or (start is None) != (end is None)
                or not isinstance(zone, str) or zone not in available_timezones()):
            return _json({"error": "Invalid quiet hours"}, 400)
        self._settings.update_channel(name, {
            "quiet": {"from": start, "to": end, "timezone": zone}})
        return _json({"ok": True})

    async def _test_message(self, request: web.Request) -> web.Response:
        name = (await _body(request)).get("channel")
        channel = {"ntfy": self.ntfy, "telegram": self.telegram}.get(str(name))
        if channel is None or not channel.ready():
            return _json({"error": "Finish setting this up first"}, 400)
        try:
            await channel.send(Outgoing("0" * 16, "BRAM", "This is a test message.", False))
        except ChannelError as err:
            return _json({"error": str(err)}, 400)
        return _json({"ok": True})

    async def _get_speech(self, request: web.Request) -> web.Response:
        return _json(self.speech.config())

    async def _save_speech(self, body: dict) -> web.Response:
        try:
            await self.speech.save(body)
        except SpeechError as err:
            return _json({"error": str(err)}, 400)
        self._audit.record("server", "config page", "voice saved", "by owner", "ok",
                           approver="owner")
        return _json({"ok": True})

    async def _hear(self, request: web.Request) -> web.Response:
        # Only this request may be this large.
        pcm = await request.clone(client_max_size=MAX_AUDIO + 1024).read()
        try:
            return _json({"text": await self.speech.hear(pcm)})
        except SpeechError as err:
            return _json({"error": str(err)}, 400)

    async def _speak(self, request: web.Request) -> web.Response:
        text = (await _body(request)).get("text")
        if not isinstance(text, str):
            return _json({"error": "There is nothing to say"}, 400)
        try:
            wav = await self.speech.speak(text[:MAX_SPEAK])
        except SpeechError as err:
            return _json({"error": str(err)}, 400)
        return web.Response(body=wav, content_type="audio/wav", headers=HEADERS)

    @staticmethod
    def _chat_key(request: web.Request) -> str:
        return f"web:{_key(request.cookies.get(COOKIE, ''))}"

    async def _chat_history(self, request: web.Request) -> web.Response:
        return _json({"messages": self.chat.history(self._chat_key(request))})

    async def _chat_ask(self, request: web.Request) -> web.Response:
        body = await _body(request)
        text, zone = body.get("text"), body.get("timezone")
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            return _json({"error": f"Use up to {MAX_TEXT} characters"}, 400)
        if isinstance(zone, str) and zone in available_timezones():
            if zone != self._settings.all()["timezone"]:
                self._settings.update({"timezone": zone})
        key = self._chat_key(request)
        try:
            reply = await self.chat.ask(key, text)
        except Busy:
            return _json({"error": "I'm still thinking about something else."}, 409)
        except ModelError as err:
            return _json({"error": str(err)}, 400)
        # Signed out while it was thinking: keep nothing.
        if not self._signed_in(request):
            self.chat.clear(key)
            return _json({"error": "Sign in first"}, 401)
        return _json({"text": reply.text, "facts": reply.facts})

    async def _chat_clear(self, request: web.Request) -> web.Response:
        self.chat.clear(self._chat_key(request))
        return _json({"ok": True})

    async def _list_monitors(self, request: web.Request) -> web.Response:
        if self.monitors is None:
            return _json({"monitors": []})
        return _json({"monitors": [{**m, "up": self.monitors.status.get(m["id"]),
                                    "reason": self.monitors.reasons.get(m["id"], "")}
                                   for m in self.monitors.all()]})

    async def _add_monitor(self, request: web.Request) -> web.Response:
        body = await _body(request)
        if self.monitors is None:
            return _json({"error": "Not available"}, 400)
        try:
            await self.monitors.add(body.get("kind"), body.get("name"), body.get("url"))
        except (ValueError, ModelError) as err:
            return _json({"error": str(err)}, 400)
        self._audit.record("server", "config page", "monitor added", str(body["kind"]), "ok",
                           approver="owner")
        return _json({"ok": True})

    async def _remove_monitor(self, request: web.Request) -> web.Response:
        if self.monitors is not None:
            self.monitors.remove((await _body(request)).get("id"))
            self._audit.record("server", "config page", "monitor removed", "by owner", "ok",
                               approver="owner")
        return _json({"ok": True})

    async def _unmute(self, request: web.Request) -> web.Response:
        body = await _body(request)
        if self._alerts is not None:
            self._alerts.unmute(str(body.get("house_id")), str(body.get("key")))
        return _json({"ok": True})

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
