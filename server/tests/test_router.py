"""The router, read directly: every device on every network, on the owner's network only."""
import pytest
from aiohttp import web

from bram.pairing import ensure_certificate
from bram.router import Router, RouterError
from bram.settings import Settings


class FakeOPNsense:
    """OPNsense's API, as much as BRAM reads. Records every request."""

    def __init__(self):
        self.asked, self.leases_allowed, self.status = [], True, "none"
        self.moved_to = ""
        self.arp = [
            {"mac": "AA:BB:CC:00:00:01", "ip": "10.0.10.5", "hostname": "",
             "manufacturer": "Apple", "intf_description": "LAN"},
            {"mac": "aa:bb:cc:00:00:02", "ip": "10.0.20.7", "hostname": "",
             "intf_description": "IOT"},
            {"mac": "not-a-mac", "ip": "x"}]

    def app(self):
        async def handle(request):
            self.asked.append(request.path)
            if request.path.startswith("/old/"):  # an address that moved
                raise web.HTTPMovedPermanently(location=self.moved_to + request.path[4:])
            if request.headers.get("Authorization") != "Basic a2V5OnNlY3JldA==":  # key:secret
                return web.Response(status=401)
            if request.method != "GET":
                return web.Response(status=405)  # BRAM never changes anything
            if request.path == "/api/diagnostics/interface/getArp":
                return web.json_response(self.arp)
            if request.path == "/api/dnsmasq/leases/search":
                if not self.leases_allowed:
                    return web.Response(status=403)
                return web.json_response({"rows": [
                    {"hwaddr": "aa:bb:cc:00:00:02", "hostname": "thermostat",
                     "address": "10.0.20.7"}]})
            if request.path == "/api/core/firmware/status":
                return web.json_response({"status": self.status,
                                          "product": {"product_version": "25.7.3"}})
            return web.Response(status=404)

        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", handle)
        return app


async def serve(app, context=None):
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context).start()
    return runner, runner.addresses[0][1]


@pytest.fixture
async def env(tmp_path):
    class E:
        pass

    e = E()
    e.fake = FakeOPNsense()
    context, e.fingerprint = ensure_certificate(tmp_path)
    e.runner, port = await serve(e.fake.app(), context)
    e.url = f"https://127.0.0.1:{port}"
    e.settings = Settings(":memory:")
    e.router = Router(e.settings, houses=lambda: ["home"])
    yield e
    await e.router.close()
    await e.runner.cleanup()
    e.settings.close()


async def test_every_device_on_every_network(env):
    with pytest.raises(RouterError, match="did not accept"):
        await env.router.connect(env.url, "key", "wrong")
    # https assumed; lines pasted from OPNsense's file keep their key= and secret=
    await env.router.connect(env.url.removeprefix("https://"), " key=key", 'secret="secret"')
    view = env.router.view()
    assert view["connected"] and view["devices"] == 2 and view["version"] == "25.7.3"
    assert "secret" not in str(view) and "key" not in view
    assert env.settings.channel("router")["pin"] == env.fingerprint
    names = {d["mac"]: (d["name"], d["where"]) for d in view["list"]}
    assert names == {"aa:bb:cc:00:00:01": ("Apple", "LAN"),
                     "aa:bb:cc:00:00:02": ("thermostat", "IOT")}  # named from its lease
    told = env.router.for_home()
    assert told["type"] == "network" and {d["key"] for d in told["devices"]} == {
        "router:aa:bb:cc:00:00:01", "router:aa:bb:cc:00:00:02"}


async def test_reads_only(env):
    env.fake.leases_allowed = False  # a key without leases still works, without names
    env.fake.status = "update"
    await env.router.connect(env.url, "key", "secret")
    await env.router.tick()
    assert env.router.view()["update"] is True
    assert all(p.startswith("/api/diagnostics/") or p.startswith("/api/core/firmware/status")
               or "leases" in p for p in env.fake.asked)


async def test_a_changed_certificate_is_refused(env):
    await env.router.connect(env.url, "key", "secret")
    env.settings.update_channel("router", {"pin": "00" * 32})
    await env.router.close()
    env.fake.asked.clear()
    await env.router.tick()
    assert "certificate changed" in env.router.view()["reason"] and env.fake.asked == []


@pytest.mark.rule("E1")
@pytest.mark.parametrize("url", ["https://8.8.8.8", "", None, "ftp://10.0.0.1"])
async def test_only_on_your_network(url):
    settings = Settings(":memory:")
    with pytest.raises(RouterError):
        await Router(settings).connect(url, "key", "secret")
    assert settings.channel("router") == {}
    settings.close()


async def test_disconnect_forgets_the_key(env):
    await env.router.connect(env.url, "key", "secret")
    await env.router.disconnect()
    assert env.settings.channel("router")["secret"] == "" and env.router.view()["devices"] == 0


async def test_following_the_router_to_its_own_https_port(env, tmp_path):
    other = FakeOPNsense()
    other.moved_to = env.url  # http on one port sends BRAM to https on another
    runner, port = await serve(other.app())
    from bram import router as module
    real = module.OPNsense._get

    async def moved_once(self, path, optional=False):
        if self.url.startswith("http://"):
            raise module.Moved(module._base(env.url, self.url))
        return await real(self, path, optional)

    module.OPNsense._get = moved_once
    try:
        await env.router.connect(f"http://127.0.0.1:{port}", "key", "secret")
    finally:
        module.OPNsense._get = real
        await runner.cleanup()
    assert env.settings.channel("router")["url"] == env.url
    assert env.settings.channel("router")["pin"] == env.fingerprint


def test_a_redirect_elsewhere_is_refused():
    from bram.router import RouterError, _base
    assert _base("https://10.0.0.1:8443/ui", "http://10.0.0.1") == "https://10.0.0.1:8443"
    with pytest.raises(RouterError):
        _base("https://evil.example/", "http://10.0.0.1")
