import asyncio
import base64
import json
import re

import aiohttp
import pytest
from aiohttp import web

from bram import local_model
from bram.alerts import Alerts
from bram.audit import Audit
from bram.findings import Findings
from bram.local_model import _is_remote, _keep_alive, check_local
from bram.models.base import ModelError, Reply
from bram.pairing import Pairing, ensure_certificate
from bram.personality import MODES, messages
from bram.server import CHAT, CONFIG, make_app
from bram.settings import Settings
from bram.web import COOKIE, HEADERS, SAMPLE, STATIC
from bram.world import Event, World
from fakes import FakeModel

PASSWORD = "correct horse battery"  # noqa: S105


class Page:
    async def post(self, path, body, origin=True, **kw):
        headers = {"Origin": self.url} if origin is True else {"Origin": origin} if origin else {}
        return await self.http.post(self.url + "/api/" + path, json=body, ssl=self.pin,
                                    headers=headers, **kw)

    async def get(self, path):
        return await self.http.get(self.url + path, ssl=self.pin, allow_redirects=False)

    async def login(self, password=PASSWORD):
        return await self.post("login", {"user": "owner", "password": password})


@pytest.fixture
async def page(tmp_path):
    p = Page()
    context, fingerprint = ensure_certificate(tmp_path)
    db = tmp_path / "bram.db"
    p.settings, p.audit, p.pairing = Settings(db), Audit(db), Pairing(db)
    p.now = 0.0
    p.alerts, p.findings = Alerts(db, p.audit), Findings(db)
    p.app = make_app(p.pairing, p.audit, p.settings, fingerprint, p.alerts, clock=lambda: p.now,
                     findings=p.findings)
    runner = web.AppRunner(p.app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context).start()
    p.url = f"https://127.0.0.1:{runner.addresses[0][1]}"
    p.pin = aiohttp.Fingerprint(bytes.fromhex(fingerprint))
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as p.http:
        yield p
    await runner.cleanup()
    for item in (p.alerts, p.settings, p.audit, p.pairing, p.findings):
        item.close()


PRIVATE = [("GET", "status"), ("GET", "log"), ("GET", "settings"), ("POST", "settings"),
           ("POST", "models"), ("POST", "sample"), ("POST", "logout"),
           ("GET", "speech"), ("POST", "speech"), ("POST", "speech-find"),
           ("POST", "speech-voices"), ("POST", "speech-preview"),
           ("POST", "hear"), ("POST", "speak"),
           ("GET", "house"), ("GET", "history"), ("POST", "history"),
           ("GET", "findings"), ("GET", "brain"), ("GET", "finding"), ("POST", "finding-ignore"),
           ("POST", "press"),
           ("GET", "cleanup"), ("POST", "cleanup-plan"), ("POST", "cleanup-drop"),
           ("POST", "cleanup-apply"), ("POST", "cleanup-later"),
           ("POST", "history-delete"),
           ("GET", "picture"), ("GET", "chat"), ("POST", "chat"), ("POST", "chat-clear"),
           ("GET", "monitors"), ("POST", "monitors"), ("POST", "monitor-remove"),
           ("GET", "cameras"), ("POST", "cameras"), ("POST", "cameras-off"), ("POST", "camera"),
           ("GET", "camera-picture"),
           ("GET", "messages"), ("GET", "ntfy-qr"), ("POST", "ntfy"), ("POST", "telegram"),
           ("POST", "telegram-link"), ("POST", "quiet"), ("POST", "test-message"),
           ("POST", "unmute"), ("GET", "profile"), ("POST", "factor-start"),
           ("GET", "factor-qr"), ("POST", "factor-on"), ("POST", "factor-off"),
           ("POST", "username"), ("POST", "logout-others"),
           ("POST", "pair"), ("POST", "password"),
           ("POST", "unpair")]


@pytest.mark.parametrize(("method", "path"), PRIVATE)
async def test_everything_needs_sign_in(page, method, path):
    page.settings.create_login("Owner", PASSWORD)
    response = await (page.get("/api/" + path) if method == "GET" else page.post(path, {}))
    assert response.status == 401


SETUP = {"user": "Owner", "password": PASSWORD}


async def state(page):
    return await (await page.get("/api/state")).json()


async def test_first_run_setup_signs_in_and_works_once(page):
    assert await state(page) == {"login_exists": False, "setup_open": True, "signed_in": False}
    assert (await page.login()).status == 403
    for bad in ({}, {"user": "", "password": PASSWORD}, {"user": "x", "password": "short"},
                {"user": 1, "password": PASSWORD}, {"user": "x", "password": "y" * 201}):
        assert (await page.post("setup", bad)).status == 400
    assert (await page.post("setup", SETUP)).status == 200
    assert await state(page) == {"login_exists": True, "setup_open": False, "signed_in": True}
    again = await page.post("setup", {"user": "x", "password": PASSWORD})
    assert again.status == 403
    assert page.settings.create_login("thief", "thief password!!") is False
    assert (await page.post("login", {"user": "thief", "password": PASSWORD})).status == 403
    assert (await page.login()).status == 200


async def test_setup_race_has_one_winner(page):
    tries = [{"user": f"u{i}", "password": PASSWORD} for i in range(5)]
    results = await asyncio.gather(*(page.post("setup", t) for t in tries))
    assert sorted(r.status for r in results) == [200, 403, 403, 403, 403]


async def test_setup_closes_after_window_and_to_other_sites(page):
    for origin in (None, "https://evil.example"):
        assert (await page.post("setup", SETUP, origin=origin)).status == 403
    page.now = 901
    assert (await state(page))["setup_open"] is False
    assert (await page.post("setup", SETUP)).status == 403
    assert page.settings.login_record() is None


async def test_signed_in_is_not_enough_for_sensitive_changes(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    house = page.pairing.redeem(page.pairing.new_code("H", "0" * 64).split("-")[2])[0]
    for path, body in (("pair", {"name": "x"}), ("unpair", {"house_id": house}),
                       ("settings", {"model": "m"}),
                       ("password", {"new": "brand new password"})):
        assert (await page.post(path, {**body, "confirm": "wrong"})).status == 403
        page.now += 901  # past the lockout
        await page.login()
    assert [h[0] for h in page.pairing.houses()] == [house]
    assert page.settings.all()["model"] == ""
    assert (await page.post("pair", {"name": "x"})).status == 403
    # Personality is wording only, so it needs no password.
    assert (await page.post("settings", {"personality": "dry"})).status == 200


async def test_confirm_guesses_count_toward_lockout(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    for _ in range(5):
        assert (await page.post("pair", {"name": "x", "confirm": "guess"})).status == 403
    assert (await page.post("pair", {"name": "x", "confirm": PASSWORD})).status == 429


async def test_change_password_ends_other_sessions(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    old = {c.key: c.value for c in page.http.cookie_jar}
    new = "a brand new password"
    assert (await page.post("password", {"new": "short", "confirm": PASSWORD})).status == 400
    assert (await page.post("password", {"new": new, "confirm": PASSWORD})).status == 200
    assert (await page.get("/api/status")).status == 200
    async with aiohttp.ClientSession(cookies=old,
                                     cookie_jar=aiohttp.CookieJar(unsafe=True)) as other:
        assert (await other.get(page.url + "/api/status", ssl=page.pin)).status == 401
    assert (await page.login()).status == 403
    assert (await page.login(new)).status == 200


async def test_profile_username_and_other_devices(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as other:
        async def other_signed_in():
            await other.post(page.url + "/api/login", ssl=page.pin, headers={"Origin": page.url},
                             json={"user": "owner", "password": PASSWORD})

        async def other_status():
            return (await other.get(page.url + "/api/status", ssl=page.pin)).status

        await other_signed_in()
        profile = await (await page.get("/api/profile")).json()
        assert profile == {"user": "Owner", "sessions": 2, "factor": False}
        assert (await page.post("logout-others", {})).status == 200
        assert await other_status() == 401 and (await page.get("/api/status")).status == 200
        await other_signed_in()
        for bad in ("", " ", "x" * 65, None):
            response = await page.post("username", {"new": bad, "confirm": PASSWORD})
            assert response.status == 400
        assert (await page.post("username", {"new": "Boss", "confirm": "wrong"})).status == 403
        assert (await page.post("username", {"new": "Boss", "confirm": PASSWORD})).status == 200
        assert await other_status() == 401
    assert (await (await page.get("/api/profile")).json())["user"] == "Boss"
    assert (await page.login()).status == 403
    assert (await page.post("login", {"user": "boss", "password": PASSWORD})).status == 200


async def test_log_pages_and_filters(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    for i in range(5):
        page.audit.record("h", "feed", "connected", str(i), "ok")
    page.audit.record("h", "sensor", "would_say", "leak", "log_only")

    async def log(query):
        return (await (await page.get("/api/log?" + query)).json())["entries"]

    first = await log("limit=2&kind=connection")
    assert [e["reason"] for e in first] == ["4", "3"]
    rest = await log(f"limit=50&kind=connection&before={first[-1]['id']}")
    assert [e["reason"] for e in rest] == ["2", "1", "0"]
    assert [e["reason"] for e in await log("kind=say")] == ["leak"]
    assert {e["trigger"] for e in await log("kind=security")} == {"config page"}
    for bad in ("limit=0", "limit=201", "limit=x", "before=x", "before=-1", "kind=x",
                f"before={10**30}", "kind=say%27%20OR%201=1"):
        assert (await page.get("/api/log?" + bad)).status == 400


async def test_messages_settings(page, monkeypatch):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    token = "123456789:" + "A" * 35
    ntfy = {"on": True, "url": "http://127.0.0.1", "phone_url": "http://127.0.0.1:2586"}
    assert (await page.get("/api/ntfy-qr")).status == 404
    for path, body in (("ntfy", ntfy), ("telegram", {"on": True, "token": token}),
                       ("telegram-link", {})):
        assert (await page.post(path, body)).status == 403  # needs the password again
    page.now += 901
    await page.login()

    async def bot_name(self, token):
        return "example_bot"

    monkeypatch.setattr("bram.channels.Telegram.bot_name", bot_name)
    ok = {"confirm": PASSWORD}
    assert (await page.post("ntfy", {**ntfy, **ok, "url": "http://8.8.8.8"})).status == 400
    assert (await page.post("ntfy", {**ntfy, **ok})).status == 200
    assert (await page.post("telegram-link", ok)).status == 400
    assert (await page.post("telegram", {"token": "junk", **ok})).status == 400
    assert (await page.post("telegram", {"on": True, "token": token, **ok})).status == 200
    link = (await (await page.post("telegram-link", ok)).json())["url"]
    assert link.startswith("https://t.me/example_bot?start=")
    response = await page.get("/api/messages")
    text = await response.text()
    data = json.loads(text)
    assert token not in text and page.settings.channel("ntfy")["reply"] not in text
    assert data["telegram"] == {"on": True, "token_saved": True, "bot": "example_bot",
                                "linked": False, "chat": False, "quiet": {}}
    topic = data["ntfy"]["topic"]
    assert data["ntfy"]["link"] == f"ntfy://127.0.0.1:2586/{topic}?secure=false"
    qr = await page.get("/api/ntfy-qr")
    assert qr.content_type == "image/svg+xml" and b"<svg" in await qr.read()
    await page.post("ntfy", {**ntfy, **ok})
    assert page.settings.channel("ntfy")["topic"] == topic
    await page.post("ntfy", {**ntfy, **ok, "new_topic": True})
    assert page.settings.channel("ntfy")["topic"] != topic
    assert token not in json.dumps(page.audit.recent(50))
    # A different bot drops the old link.
    page.settings.update_channel("telegram", {"user_id": 5})
    await page.post("telegram", {"on": True, "token": "987654321:" + "B" * 35, **ok})
    assert page.settings.channel("telegram")["user_id"] is None
    await page.post("telegram", {"remove": True, **ok})
    assert page.settings.channel("telegram")["token"] == ""


async def test_chat_on_the_page(page, monkeypatch):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    assert (await page.post("chat", {"text": "hi"})).status == 400  # no model yet
    page.settings.update({"model_url": "http://127.0.0.1:11434", "model": "m:1"})

    class Closing(FakeModel):
        async def close(self):
            pass

    async def opened(*args, **kw):
        return Closing(Reply("Good evening."))

    monkeypatch.setattr(page.app[CHAT], "_open", opened)
    for bad in ({}, {"text": 5}, {"text": "x" * 2001}):
        assert (await page.post("chat", bad)).status == 400
    reply = await page.post("chat", {"text": "hi", "timezone": "America/New_York"})
    assert (await reply.json()) == {"text": "Good evening.", "facts": []}
    assert page.settings.all()["timezone"] == "America/New_York"
    await page.post("chat", {"text": "hi", "timezone": "../../etc"})
    assert page.settings.all()["timezone"] == "America/New_York"
    messages = (await (await page.get("/api/chat")).json())["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"] * 2
    await page.post("logout", {})
    await page.login()
    assert (await (await page.get("/api/chat")).json())["messages"] == []
    await page.post("chat", {"text": "hi"})
    await page.post("chat-clear", {})
    assert (await (await page.get("/api/chat")).json())["messages"] == []


async def test_voice_on_the_page(page, monkeypatch):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    good = {"hear": "127.0.0.1", "speak": "127.0.0.1:10200", "voice": "", "confirm": PASSWORD}
    assert (await page.post("speech", {**good, "confirm": ""})).status == 403
    assert (await page.post("speech", {**good, "hear": "8.8.8.8"})).status == 400
    assert (await page.post("speech", good)).status == 200
    saved = await (await page.get("/api/speech")).json()
    assert saved == {"hear": "127.0.0.1:10300", "speak": "127.0.0.1:10200", "voice": ""}
    heard = []

    async def transcribe(address, pcm):
        heard.append(len(pcm))
        return "hello"

    async def synthesize(address, text, voice):
        return b"RIFF" + text.encode()

    monkeypatch.setattr("bram.speech.transcribe", transcribe)
    monkeypatch.setattr("bram.speech.synthesize", synthesize)

    async def hear(size, origin=None):
        return await page.http.post(page.url + "/api/hear", data=b"\x00" * size, ssl=page.pin,
                                    headers={"Origin": origin or page.url})

    assert await (await hear(900_000)).json() == {"text": "hello"}
    assert (await hear(2_000_000)).status == 413
    assert (await hear(10, "https://evil.example")).status == 403
    assert heard == [900_000]
    async def describe(kind, address):
        return {"name": "x", "voices": [{"name": "v1", "ready": True, "language": "en"}]}

    monkeypatch.setattr("bram.web.describe", describe)
    found = await page.post("speech-voices", {"address": "127.0.0.1:10200"})
    assert (await found.json())["voices"][0]["name"] == "v1"
    preview = await page.post("speech-preview", {"address": "127.0.0.1:10200", "voice": "v1"})
    assert (await preview.read()).startswith(b"RIFF")
    for bad in ({"address": 5}, {"address": "127.0.0.1", "voice": "../x"}):
        assert (await page.post("speech-preview", bad)).status == 400
    assert (await page.post("speech-find", {"host": 5})).status == 400
    reply = await page.post("speak", {"text": "hi"})
    assert reply.content_type == "audio/wav" and await reply.read() == b"RIFFhi"
    assert (await page.post("speak", {"text": 5})).status == 400
    # Everything else keeps the small limit.
    assert (await page.post("speak", {"text": "x" * 5000})).status == 413


async def test_pictures(page, monkeypatch):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    png, asked = b"\x89PNG\r\n\x1a\n" + b"0" * 20, []
    result = [{"data": base64.b64encode(png).decode(), "kind": "text/html"}]
    world = World("h", clock=lambda: 0)
    world.update(Event("h", "person.a", "person", "home", "A", {"picture": "tag1"}))
    world.update(Event("h", "light.a", "light", "on", "L"))

    async def look_up(*args):
        asked.append(args)
        return result[0]

    monkeypatch.setattr(page.app[CONFIG], "_look_up", look_up)
    monkeypatch.setattr(page.app[CONFIG], "_worlds", lambda: {"h": world})
    for _ in range(2):
        response = await page.get("/api/picture?home=h&id=person.a")
        assert response.content_type == "image/png" and await response.read() == png
        assert "sandbox" in response.headers["Content-Security-Policy"]
    assert asked == [("h", "picture", "person.a")]  # kept, in memory only
    for query in ("home=h&id=light.a", "home=h&id=person.b", "home=x&id=person.a", ""):
        assert (await page.get("/api/picture?" + query)).status == 404
    for bad in ({"data": base64.b64encode(b"<svg onload=1>").decode()}, {"data": "!!"}, None,
                {"error": "none"}, {"data": 5}):
        result[0] = bad
        page.app[CONFIG]._pictures.clear()
        assert (await page.get("/api/picture?home=h&id=person.a")).status == 404


async def test_monitors_page(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    bad = {"kind": "website", "name": "x", "url": "http://127.0.0.1"}
    assert (await page.post("monitors", bad)).status == 400
    for url in ("http://8.8.8.8", "file:///etc/passwd"):
        assert (await page.post("monitors", {**bad, "kind": "device", "url": url})).status == 400
    good = {"kind": "device", "name": "Router", "url": "127.0.0.1"}
    assert (await page.post("monitors", good)).status == 200
    items = (await (await page.get("/api/monitors")).json())["monitors"]
    assert items[0]["url"] == "http://127.0.0.1:80" and items[0]["up"] in (True, None)
    await page.post("monitor-remove", {"id": items[0]["id"]})
    assert (await (await page.get("/api/monitors")).json())["monitors"] == []


async def test_quiet_hours_setting(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    good = {"channel": "ntfy", "from": 22, "to": 7, "timezone": "America/New_York"}
    assert (await page.post("quiet", good)).status == 200
    assert page.settings.channel("ntfy")["quiet"]["from"] == 22
    for bad in ({"from": 24}, {"from": True}, {"to": None}, {"timezone": "../etc/passwd"},
                {"channel": "ha"}, {"from": "22"}):
        assert (await page.post("quiet", {**good, **bad})).status == 400
    assert (await page.post("quiet", {**good, "from": None, "to": None})).status == 200


async def test_idle_session_ends(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    page.now = 1700
    assert (await page.get("/api/status")).status == 200
    page.now = 3400
    assert (await page.get("/api/status")).status == 200
    page.now = 5300
    assert (await page.get("/api/status")).status == 401


async def test_pair_and_unpair_from_the_page(page):
    await page.post("setup", SETUP)
    assert (await page.post("pair", {"name": " ", "confirm": PASSWORD})).status == 400
    code = (await (await page.post("pair", {"name": "Home", "confirm": PASSWORD})).json())["code"]
    paired = await (await page.http.post(
        page.url + "/pair", json={"secret": code.split("-")[2]}, ssl=page.pin)).json()
    assert code.split("-")[1] == page.pin.fingerprint.hex()
    assert code not in json.dumps(page.audit.recent(20))
    headers = {"Authorization": f"Bearer {paired['token']}"}
    async with page.http.ws_connect(page.url + "/feed", ssl=page.pin, headers=headers) as ws:
        await ws.receive(timeout=3)  # hello
        await ws.receive(timeout=3)  # mood
        await ws.send_json({"type": "snapshot", "states": [], "version": "0.1.0"})
        await asyncio.sleep(0.2)
        houses = (await (await page.get("/api/status")).json())["houses"]
        assert houses == [{"id": paired["house_id"], "name": "Home", "connected": True,
                           "version": "0.1.0"}]
        done, closed = await asyncio.gather(
            page.post("unpair", {"house_id": paired["house_id"], "confirm": PASSWORD}),
            ws.receive(timeout=5))
        assert done.status == 200 and closed.type is aiohttp.WSMsgType.CLOSE
    with pytest.raises(aiohttp.WSServerHandshakeError):
        await page.http.ws_connect(page.url + "/feed", ssl=page.pin, headers=headers)
    assert (await page.post("unpair", {"house_id": "nope", "confirm": PASSWORD})).status == 400


async def test_login_cookie_and_logout(page):
    page.settings.create_login("Owner", PASSWORD)
    response = await page.login()
    cookie = response.headers["Set-Cookie"]
    assert response.status == 200 and cookie.startswith(COOKIE + "=")
    assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/"))
    assert (await page.get("/api/status")).status == 200
    assert (await page.post("logout", {})).status == 200
    assert (await page.get("/api/status")).status == 401


async def test_sessions_end_on_expiry_and_login_reset(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    page.now = 12 * 3600 + 1
    assert (await page.get("/api/status")).status == 401
    await page.login()
    page.settings.reset_login()
    page.settings.create_login("Owner", "another long password")
    assert (await page.get("/api/status")).status == 401


async def test_lockout(page):
    page.settings.create_login("Owner", PASSWORD)
    results = await asyncio.gather(*(page.login("wrong") for _ in range(8)))
    assert sorted(r.status for r in results) == [403] * 5 + [429] * 3
    assert (await page.login()).status == 429
    page.now = 901
    assert (await page.login()).status == 200


@pytest.mark.parametrize("origin", [None, "https://evil.example", "null"])
async def test_other_sites_cannot_post(page, origin):
    page.settings.create_login("Owner", PASSWORD)
    login = {"user": "owner", "password": PASSWORD}
    assert (await page.post("login", login, origin=origin)).status == 403
    await page.login()
    response = await page.post("settings", {"personality": "dry"}, origin=origin)
    assert response.status == 403 and page.settings.all()["personality"] == "professional"


async def test_settings(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    good = {"model_url": "http://127.0.0.1:11434/", "model": "m:1", "context": 4096,
            "personality": "custom", "custom_style": "private pirate words"}
    assert (await page.post("settings", {**good, "confirm": PASSWORD})).status == 200
    assert page.settings.all() == {
        **good, "model_url": "http://127.0.0.1:11434", "timezone": "", "keep_history": False,
        "history_limit_mb": 2048}
    log = json.dumps(page.audit.recent(10))
    assert "settings saved" in log and "pirate" not in log
    for bad in ({"_password": "x"}, {"tier": 1}, {"personality": "evil"}, {"personality": []},
                {"context": 1}, {"context": True}, {"custom_style": "x" * 501},
                {"model_url": "http://8.8.8.8:11434"}, {"model": 5}, {"keep_history": True}):
        assert (await page.post("settings", {**bad, "confirm": PASSWORD})).status == 400
    assert page.settings.all()["personality"] == "custom"


async def test_password_not_stored_or_returned(page, tmp_path):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    text = await (await page.get("/api/settings")).text()
    assert "password" not in text
    assert PASSWORD.encode() not in b"".join(f.read_bytes() for f in tmp_path.glob("bram.db*"))


async def test_static_files_and_headers(page):
    for path in ("/ui/", "/ui/app.js", "/ui/style.css", "/ui/recorder.js", "/ui/deck.js",
                 "/ui/deck.css",
                 "/ui/icon.png"):
        response = await page.get(path)
        assert response.status == 200
        for key, value in HEADERS.items():
            assert response.headers[key] == value
    assert (await page.get("/ui/server.key")).status == 404
    assert (await page.get("/ui/..%2fserver.py")).status == 404
    assert (await page.get("/")).headers["Location"] == "/ui/"


async def test_sample_uses_only_the_invented_fact(page, monkeypatch):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    assert (await page.post("sample", {"personality": "dry"})).status == 400  # no model yet
    page.settings.update({"model_url": "http://127.0.0.1:11434", "model": "m:1"})

    class Closing(FakeModel):
        async def close(self):
            pass

    fake = Closing(Reply("Bold strategy."), ModelError("down"))

    async def opened(*args, **kw):
        return fake

    monkeypatch.setattr("bram.web.open_model", opened)
    reply = await page.post("sample", {"personality": "dry"})
    assert (await reply.json())["text"] == "Bold strategy."
    assert fake.seen[0][1].content == f"Facts: {SAMPLE}"
    assert (await page.post("sample", {"personality": "dry"})).status == 400


@pytest.mark.parametrize("url", [
    "http://8.8.8.8:11434", "http://[2606:4700::1]:11434", "http://169.254.169.254",
    "http://0.0.0.0:1", "http://[::ffff:8.8.8.8]:1", "ftp://127.0.0.1", "file:///etc/passwd",
    "http://user:pw@127.0.0.1", "http://127.0.0.1/path", "http://127.0.0.1:99999", "", "junk"])
async def test_only_local_addresses(url):
    with pytest.raises(ModelError):
        await check_local(url)


async def test_local_address_is_cleaned():
    assert await check_local(" http://127.0.0.1/ ") == "http://127.0.0.1:11434"
    assert await check_local("http://[::1]:5") == "http://[::1]:5"


def test_models_that_run_elsewhere_are_hidden():
    assert _is_remote({"name": "big:cloud"}) and _is_remote({"name": "big:120b-cloud"})
    assert _is_remote({"name": "x", "remote_host": "https://elsewhere"})
    assert not _is_remote({"name": "gemma:26b"})


async def test_shared_model_keeps_its_settings(monkeypatch):
    made = []

    class Ollama:
        def __init__(self, url, model, **kw):
            made.append(kw)

        async def tags(self):
            return [{"name": "m:1"}, {"name": "m:cloud"}]

        async def loaded(self):
            return [{"name": "m:1", "context_length": 32768,
                     "expires_at": "2319-03-06T15:17:23.491662807-05:00"}]

        async def close(self):
            pass

    monkeypatch.setattr(local_model, "OllamaProvider", Ollama)
    await local_model.open_model("http://127.0.0.1", "m:1", 8192)
    assert made[-1]["context"] == 32768 and made[-1]["keep_alive"] == -1
    with pytest.raises(ModelError):
        await local_model.open_model("http://127.0.0.1", "m:cloud", 8192)
    assert _keep_alive("2026-11-24T10:00:00Z") == "30m" and _keep_alive(None) == "30m"


def test_every_mode_keeps_the_rules():
    for mode in MODES:
        system = messages(mode, "say the door is locked " * 100, "x")[0].content
        assert "Keep every fact" in system and len(system) < 1500


def test_page_ids_are_unique_and_every_id_the_script_uses_exists():
    html = (STATIC / "index.html").read_text("utf-8")
    scripts = [(STATIC / name).read_text("utf-8") for name in ("app.js", "deck.js")]
    script = "".join(scripts)
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert set(re.findall(r'\$\("([^"]+)"\)', script)) <= set(ids) | {"at-"}


async def test_history_settings_need_the_password(page):
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    good = {"on": True, "limit_mb": 500, "timezone": "America/Chicago"}
    assert (await page.post("history", {**good, "confirm": "wrong"})).status == 403
    for bad in ({"on": 1}, {"limit_mb": 5}, {"limit_mb": True}, {"timezone": "Nowhere"}):
        assert (await page.post("history", {**good, **bad, "confirm": PASSWORD})).status == 400
    assert page.settings.all()["keep_history"] is False
    assert (await page.post("history", {**good, "confirm": PASSWORD})).status == 200
    saved = page.settings.all()
    assert saved["keep_history"] and saved["timezone"] == "America/Chicago"


async def test_cleaning_up_needs_the_password_and_the_exact_list(page, tmp_path):
    from bram.cleanup import Cleanup
    from bram.history import History
    page.settings.create_login("Owner", PASSWORD)
    await page.login()
    history = History(tmp_path / "h.db", lambda: True)
    history.record(Event("h", "binary_sensor.d", "opening", "on", "Door"), World("h"))
    config = page.app[CONFIG]
    config.history, config.cleanup = history, Cleanup(history, None)
    (device,) = (await (await page.get("/api/cleanup")).json())["devices"]
    for bad in ({}, {"devices": [True]}, {"devices": ["1"]}, {"devices": [99]},
                {"devices": [device["id"]], "older_days": -1}):
        assert (await page.post("cleanup-plan", {"action": "delete", **bad})).status == 400
    plan = await (await page.post("cleanup-plan", {
        "action": "delete", "devices": [device["id"]]})).json()
    assert (await page.post("cleanup-apply", {"id": plan["id"], "confirm": "no"})).status == 403
    assert (await page.post("cleanup-apply", {"id": "x", "confirm": PASSWORD})).status == 400
    assert history.summary()["counts"]["change"] == 1
    assert (await page.post("cleanup-apply", {
        "id": plan["id"], "confirm": PASSWORD})).status == 200
    assert history.summary()["counts"]["change"] == 0
    assert "history cleaned" in json.dumps(page.audit.recent(5))
    history.close()


async def test_page_buttons_go_to_home_assistant_only_as_offered(page):
    await page.post("setup", SETUP)
    code = (await (await page.post("pair", {"name": "Home", "confirm": PASSWORD})).json())["code"]
    paired = await (await page.http.post(
        page.url + "/pair", json={"secret": code.split("-")[2]}, ssl=page.pin)).json()
    headers = {"Authorization": f"Bearer {paired['token']}"}
    stop = {"action": "BRAM_QUIET_night:lock.a", "title": "Stop these"}
    async with page.http.ws_connect(page.url + "/feed", ssl=page.pin, headers=headers) as ws:
        await ws.receive(timeout=3)  # hello
        await ws.receive(timeout=3)  # mood
        await ws.send_json({"type": "snapshot", "states": [], "version": "0.32.0"})
        for n, (what, extra) in enumerate([("open", {}), ("buttons", {"buttons": [stop]})]):
            await ws.send_json({"type": "note", "id": f"{n:016x}", "key": "rules:k",
                                "what": what, "text": "Front lock", "source": "rules",
                                "severity": "medium", **extra})
            assert (await ws.receive_json(timeout=3))["type"] == "noted"
        (need,) = (await (await page.get("/api/brain")).json())["needs"]
        assert need["buttons"] == [stop]
        press = {"id": need["id"], "action": stop["action"]}
        assert (await page.post("press", {**press, "action": "BRAM_ACK_k"})).status == 400
        assert (await page.post("press", press)).status == 409  # Home Assistant too old
        await ws.send_json({"type": "snapshot", "states": [], "version": "0.33.0"})
        await asyncio.sleep(0.2)
        assert (await page.post("press", press)).status == 200
        assert await ws.receive_json(timeout=3) == {"type": "press", "key": "rules:k",
                                                     "action": stop["action"]}
        assert (await page.post("press", press)).status == 400  # once
