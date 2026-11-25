import asyncio

import httpx
import pytest

from bram.alerts import Alerts
from bram.audit import Audit
from bram.models.base import ModelError
from bram.monitors import FAILURES, LIMIT, Monitors, diagnose, probe
from bram.settings import Settings


class Box:
    name = "box"

    def __init__(self):
        self.sent = []

    def ready(self):
        return True

    async def send(self, message):
        self.sent.append(message)


@pytest.fixture
def env():
    class E:
        pass

    e = E()
    e.up, e.box = True, Box()
    e.settings, e.audit = Settings(":memory:"), Audit(":memory:")
    e.alerts = Alerts(":memory:", e.audit)
    e.alerts.channels = [e.box]

    async def check(kind, url):
        return "" if e.up else "could not connect"

    e.monitors = Monitors(e.settings, e.alerts, check)

    async def run(times):
        for _ in range(times):
            await e.monitors.tick()
        await e.alerts.tick()

    e.run = run
    yield e
    for item in (e.alerts, e.settings, e.audit):
        item.close()


async def test_tells_after_repeated_failures_and_when_back(env):
    await env.monitors.add("ollama", "My Ollama", "http://127.0.0.1")
    await env.run(1)
    env.up = False
    await env.run(FAILURES - 1)
    assert env.box.sent == []
    await env.run(10)
    assert [m.text for m in env.box.sent] == ["My Ollama is not answering."]
    assert not env.box.sent[0].safety
    env.up = True
    await env.run(2)
    assert env.box.sent[-1].text == "My Ollama is back." and len(env.box.sent) == 2


async def test_checked_as_soon_as_it_is_added(env):
    await env.monitors.add("device", "Router", "127.0.0.1:80")
    assert env.monitors.status == {env.monitors.all()[0]["id"]: True}


async def test_brief_failure_is_ignored(env):
    await env.monitors.add("device", "Router", "127.0.0.1:80")
    for _ in range(5):
        env.up = False
        await env.run(FAILURES - 1)
        env.up = True
        await env.run(1)
    assert env.box.sent == []


async def test_removed_monitor_goes_quiet(env):
    await env.monitors.add("device", "Router", "127.0.0.1:80")
    env.up = False
    for _ in range(FAILURES):
        await env.monitors.tick()
    env.monitors.remove(env.monitors.all()[0]["id"])
    await env.run(5)
    assert env.box.sent == [] and env.monitors.all() == []


@pytest.mark.parametrize(("kind", "name", "url"), [
    ("website", "x", "http://127.0.0.1"), ("docker", "x", "http://127.0.0.1"),
    ("device", "", "127.0.0.1"), ("device", "x" * 61, "127.0.0.1"), ("device", "x", None),
    ("device", "x", "8.8.8.8:80"), ("frigate", "x", "https://example.com/path"), (None, "x", "x")])
async def test_bad_monitors_are_refused(env, kind, name, url):
    with pytest.raises((ValueError, ModelError)):
        await env.monitors.add(kind, name, url)
    assert env.monitors.all() == []


async def test_limit(env):
    for i in range(LIMIT):
        await env.monitors.add("device", f"d{i}", "127.0.0.1:80")
    with pytest.raises(ValueError, match="At most"):
        await env.monitors.add("device", "more", "127.0.0.1:80")


async def test_probe_http():
    def answering(status):
        return httpx.MockTransport(lambda r: httpx.Response(status))

    assert await probe("ollama", "http://127.0.0.1", answering(200))
    assert not await probe("frigate", "http://127.0.0.1", answering(502))
    assert await probe("frigate", "https://127.0.0.1:8971", answering(401))
    assert not await probe("ollama", "http://127.0.0.1", answering(401))
    assert not await probe("frigate", "http://8.8.8.8", answering(200))


async def test_frigate_is_tried_with_and_without_https():
    def only(scheme, status):
        def handler(request):
            if request.url.scheme != scheme:
                return httpx.Response(400)
            return httpx.Response(status)
        return httpx.MockTransport(handler)

    for typed in ("http://127.0.0.1:8971", "https://127.0.0.1:8971"):
        assert await probe("frigate", typed, only("https", 401))
        assert await probe("frigate", typed, only("http", 200))
        assert not await probe("frigate", typed, only("https", 502))

    def down(request):
        raise httpx.ConnectError("no")

    assert not await probe("frigate", "http://127.0.0.1", httpx.MockTransport(down))


async def test_says_why():
    def transport(result):
        def handler(request):
            if isinstance(result, Exception):
                raise result
            return httpx.Response(result)
        return httpx.MockTransport(handler)

    for result, reason in ((500, "error 500"), (httpx.ConnectTimeout("x"), "in time"),
                           (httpx.ConnectError("x"), "could not connect"),
                           (httpx.ConnectError("CERTIFICATE_VERIFY_FAILED"), "not trusted")):
        assert reason in await diagnose("ollama", "http://127.0.0.1", transport(result))


async def test_failing_monitor_keeps_its_reason(env):
    env.up = False
    await env.monitors.add("ollama", "x", "http://127.0.0.1")
    assert list(env.monitors.reasons.values()) == ["could not connect"]


async def test_probe_device():
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    assert await probe("device", f"http://127.0.0.1:{port}")
    server.close()
    await server.wait_closed()
