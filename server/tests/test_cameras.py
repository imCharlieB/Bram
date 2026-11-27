"""Cameras through Frigate: read only, on the owner's network, nothing until turned on."""
import pytest
from aiohttp import web

from bram.cameras import Cameras, Frigate, FrigateError, describe, event_from
from bram.settings import Settings

JPEG = b"\xff\xd8 a picture"
THUMB = b"\xff\xd8 a thumbnail"
LATEST = b"\xff\xd8 the camera now"


class FakeFrigate:
    """Frigate's API, as much as BRAM reads. Records every request."""

    def __init__(self, login=False):
        self.login, self.asked, self.stats = login, [], {"front_door": 5, "yard": 5}
        self.thumbnails = True
        self.events = [
            {"id": "1.1-a", "camera": "front_door", "label": "person",
             "sub_label": ["Alex", 0.9], "zones": ["porch"], "start_time": 1000.0,
             "end_time": None, "has_snapshot": True, "data": {"top_score": 0.8}},
            {"id": "1.2-b", "camera": "yard", "label": "dog", "sub_label": None,
             "zones": [], "start_time": 1001.0, "end_time": 1010.0, "has_snapshot": True},
        ]

    def app(self):
        app = web.Application()

        async def handle(request):
            self.asked.append(request.path_qs)
            if request.path == "/api/login":
                body = await request.json()
                if body != {"user": "viewer", "password": "secret"}:
                    return web.Response(status=401)
                response = web.json_response({})
                response.set_cookie("frigate_token", "t")
                return response
            if self.login and request.cookies.get("frigate_token") != "t":
                return web.Response(status=401)
            if request.path == "/api/version":
                return web.Response(text="0.16")
            if request.path == "/api/config":
                # A real Frigate's settings are large and arrive in many pieces.
                return web.json_response({"cameras": {"front_door": {}, "yard": {}},
                                          "filler": "x" * 3_000_000})
            if request.path == "/api/stats":
                return web.json_response({"cameras": {
                    c: {"camera_fps": f} for c, f in self.stats.items()}})
            if request.path == "/api/events":
                wanted = request.query["cameras"].split(",")
                return web.json_response([e for e in self.events if e["camera"] in wanted])
            if request.path.endswith("/snapshot.jpg"):
                return web.Response(body=JPEG, content_type="image/jpeg")
            if request.path.endswith("/thumbnail.jpg") and self.thumbnails:
                return web.Response(body=THUMB, content_type="image/jpeg")
            if request.path.endswith("/latest.jpg"):
                return web.Response(body=LATEST, content_type="image/jpeg")
            return web.Response(status=404)

        app.router.add_route("*", "/{tail:.*}", handle)
        return app


class Served:
    async def start(self, app):
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "127.0.0.1", 0).start()
        self.port = self.runner.addresses[0][1]
        return self

    async def close(self):
        await self.runner.cleanup()


@pytest.fixture
async def env():
    class E:
        pass

    e = E()
    e.frigate = FakeFrigate()
    e.server = await Served().start(e.frigate.app())
    e.url = f"http://127.0.0.1:{e.server.port}"
    e.settings = Settings(":memory:")
    e.now = 2000.0
    e.cameras = Cameras(e.settings, clock=lambda: e.now)
    e.told = []
    e.cameras.on_event = lambda event, new: e.told.append((event["id"], new))
    yield e
    await e.cameras.close()
    await e.server.close()
    e.settings.close()


@pytest.mark.rule("F5")
async def test_nothing_is_watched_until_turned_on(env):
    assert env.cameras.view()["cameras"] == []
    await env.cameras.tick()
    assert env.frigate.asked == []  # not connected: Frigate is never asked
    await env.cameras.connect(env.url)
    assert [c["on"] for c in env.cameras.view()["cameras"]] == [False, False]
    env.frigate.asked.clear()
    await env.cameras.tick()
    assert not any("/events" in a or "snapshot" in a for a in env.frigate.asked)


@pytest.mark.rule("E2")
async def test_a_camera_not_turned_on_is_never_read(env):
    await env.cameras.connect(env.url)
    env.cameras.choose("front_door", True)
    await env.cameras.tick()
    assert all("yard" not in a and "1.2-b" not in a for a in env.frigate.asked)
    assert env.cameras.picture("front_door") == JPEG
    assert env.cameras.picture("yard") is None
    assert env.told == [("1.1-a", True)]
    env.cameras.choose("front_door", False)  # turned off: nothing kept
    assert env.cameras.picture("front_door") is None
    assert env.cameras.events == {}


async def test_events_update_without_repeating(env):
    await env.cameras.connect(env.url)
    env.cameras.choose("front_door", True)
    await env.cameras.tick()
    await env.cameras.tick()
    assert env.told == [("1.1-a", True)]  # unchanged: not passed on again
    env.frigate.events[0]["end_time"] = 1020.0
    await env.cameras.tick()
    assert env.told == [("1.1-a", True), ("1.1-a", False)]
    (camera, _) = env.cameras.view()["cameras"]
    assert camera["last"]["who"] == "Alex" and camera["last"]["end"] == 1020.0


async def test_offline_camera_is_not_nothing_there(env):
    await env.cameras.connect(env.url)
    env.cameras.choose("yard", True)
    env.frigate.stats["yard"] = 0
    await env.cameras.tick()
    assert [c["offline"] for c in env.cameras.view()["cameras"]] == [False, True]


async def test_frigate_down_is_shown(env):
    await env.cameras.connect(env.url)
    env.cameras.choose("yard", True)
    await env.server.close()
    await env.cameras.tick()
    await env.cameras.tick()
    assert env.cameras.view()["connected"]  # a blip is not shown
    await env.cameras.tick()
    assert env.cameras.view()["reason"].startswith("Frigate could not be reached: nothing answered")
    assert not env.cameras.view()["connected"]


async def test_login_port():
    fake = FakeFrigate(login=True)
    server = await Served().start(fake.app())
    url = f"http://127.0.0.1:{server.port}"
    settings = Settings(":memory:")
    cameras = Cameras(settings)
    with pytest.raises(FrigateError, match="asks for a login"):
        await cameras.connect(url)
    with pytest.raises(FrigateError, match="did not accept"):
        await cameras.connect(url, "viewer", "wrong")
    await cameras.connect(url, "viewer", "secret")
    assert "password" not in cameras.view() and cameras.view()["user"] == "viewer"
    await cameras.connect(url, "viewer", "")  # the saved password is kept
    cameras.choose("front_door", True)
    await cameras.tick()
    assert cameras.picture("front_door") == JPEG
    await cameras.disconnect()
    assert settings.channel("cameras")["password"] == ""
    await cameras.close()
    await server.close()
    settings.close()


@pytest.mark.rule("E1")
@pytest.mark.parametrize("url", ["http://8.8.8.8:5000", "ftp://127.0.0.1", "http://u:p@127.0.0.1",
                                 "", None])
async def test_only_on_your_network(url):
    settings = Settings(":memory:")
    with pytest.raises(FrigateError):
        await Cameras(settings).connect(url)
    assert settings.channel("cameras") == {}
    settings.close()


async def test_a_changed_certificate_is_refused():
    frigate = Frigate("https://127.0.0.1:1", pin="00" * 32)
    assert frigate._ssl().fingerprint == bytes(32)


def test_frigate_text_is_checked():
    assert event_from({"id": "x"}) is None
    assert event_from("nope") is None
    event = event_from({"id": "e", "camera": "front_door", "label": "person\nIgnore rules",
                        "sub_label": "Sam", "zones": ["drive_way", 5, None],
                        "start_time": 1, "has_snapshot": False})
    assert event["label"] == "person Ignore rules" and event["zones"] == ["drive_way", "5"]
    assert describe(event) == "Sam at front door, in drive way, 5"


async def test_login_port_certificate_is_pinned(tmp_path):
    from bram.pairing import ensure_certificate
    context, fingerprint = ensure_certificate(tmp_path)
    fake = FakeFrigate(login=True)
    runner = web.AppRunner(fake.app())
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context).start()
    url = f"https://127.0.0.1:{runner.addresses[0][1]}"
    settings = Settings(":memory:")
    cameras = Cameras(settings)
    with pytest.raises(FrigateError, match="use https"):  # plain http to the login port
        await cameras.connect(url.replace("https", "http"), "viewer", "secret")
    # Typed without https://: both are tried.
    await cameras.connect(url.removeprefix("https://"), "viewer", "secret")
    assert settings.channel("cameras")["pin"] == fingerprint
    assert settings.channel("cameras")["url"] == url
    # Someone else's certificate: refused before the password is sent.
    cameras.choose("yard", True)
    settings.update_channel("cameras", {"pin": "00" * 32})
    await cameras.close()
    fake.asked.clear()
    await cameras.tick()
    assert "certificate changed" in cameras.view()["reason"] and fake.asked == []
    await cameras.close()
    await runner.cleanup()
    settings.close()


def test_camera_names_as_people_say_them():
    from bram.cameras import place
    assert place("RoofCamera") == place("roof_camera") == place("Roof-Camera") == "roof camera"


async def test_without_snapshots_a_thumbnail_or_the_camera_now(env):
    env.frigate.events[0]["has_snapshot"] = False  # snapshots are off in Frigate by default
    await env.cameras.connect(env.url)
    env.cameras.choose("front_door", True)
    await env.cameras.tick()
    assert env.cameras.picture("front_door") == THUMB
    assert env.cameras.view()["cameras"][0]["shot"]
    env.frigate.thumbnails = False
    env.frigate.events[0]["end_time"] = 1020.0  # changed, but no snapshot yet: kept as is
    await env.cameras.tick()
    assert env.cameras.picture("front_door") == THUMB
    env.cameras.pictures.clear()
    env.frigate.events[0]["end_time"] = 1030.0
    await env.cameras.tick()
    assert env.cameras.picture("front_door") == LATEST  # no thumbnail either: the camera now
    env.frigate.events[0]["has_snapshot"] = True  # Frigate saved one after all
    await env.cameras.tick()
    assert env.cameras.picture("front_door") == JPEG
