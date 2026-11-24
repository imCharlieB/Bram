"""Integration tests, including the real server over real TLS."""
import asyncio
import re
from pathlib import Path

import pytest
from aiohttp import web
from homeassistant.data_entry_flow import FlowResultType

from bram.audit import Audit
from bram.pairing import Pairing, ensure_certificate
from bram.server import HOUSES, SOCKETS, make_app
from custom_components.bram import gate
from custom_components.bram.client import InvalidCode, parse_code
from custom_components.bram.feed import kind_of

ROOT = Path(__file__).parents[1]


@pytest.fixture
async def server(tmp_path, socket_enabled):
    context, fingerprint = ensure_certificate(tmp_path)
    app = make_app(Pairing(":memory:"), Audit(":memory:"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context).start()
    app_info = (app, fingerprint, runner.addresses[0][1])
    yield app_info
    await runner.cleanup()


async def until(check):
    async with asyncio.timeout(5):
        while not check():  # noqa: ASYNC110
            await asyncio.sleep(0.01)


async def start(hass, server):
    from bram.server import PAIRING

    app, fingerprint, port = server
    flow = await hass.config_entries.flow.async_init("bram", context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {
        "host": "127.0.0.1", "port": port, "code": app[PAIRING].new_code("T", fingerprint)})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await until(lambda: app[SOCKETS])
    return result["result"]


async def choose(hass, entry, entities):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"entities": entities})
    assert result["type"] is FlowResultType.CREATE_ENTRY


LEAK, LOCK = "binary_sensor.leak", "lock.a"


async def test_end_to_end_read_only(hass, server):
    calls = []
    hass.bus.async_listen("call_service", lambda e: calls.append(e))
    hass.states.async_set(LEAK, "off", {"device_class": "moisture"})
    hass.states.async_set(LOCK, "locked")
    entry = await start(hass, server)
    app = server[0]
    world = app[HOUSES][entry.data["house_id"]][0]
    await until(lambda: world.live)
    assert world.check(LEAK) == "unknown"  # nothing shared by default

    await choose(hass, entry, [LEAK])
    await until(lambda: world.check(LEAK) == "no")
    assert world.check(LOCK) == "unknown"  # not chosen, not shared
    hass.states.async_set(LEAK, "on", {"device_class": "moisture"})
    await until(lambda: world.check(LEAK) == "yes")
    hass.states.async_remove(LEAK)
    await until(lambda: world.check(LEAK) == "unknown")

    # A server that asks for an action gets nothing.
    ws = next(iter(app[SOCKETS].values()))
    await ws.send_json({"type": "call_service", "domain": "lock", "service": "unlock"})
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    assert calls == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not app[SOCKETS])


async def test_bad_code_and_wrong_server(hass, server):
    from bram.server import PAIRING

    app, fingerprint, port = server
    secret = app[PAIRING].new_code("T", fingerprint).split("-")[2]
    flow = await hass.config_entries.flow.async_init("bram", context={"source": "user"})
    for code, error in (("nonsense", "invalid_code"),
                        (f"bram1-{'0' * 64}-{secret}", "cannot_connect"),
                        (f"bram1-{fingerprint}-{'0' * 32}", "invalid_code")):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "127.0.0.1", "port": port, "code": code})
        assert result["errors"] == {"base": error}
    # The wrong-server attempt never sent the secret, so it still works.
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {
        "host": "127.0.0.1", "port": port, "code": f"bram1-{fingerprint}-{secret}"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("request_", [None, {}, "unlock", {"approved": True, "tier": 1}])
def test_gate_refuses_everything(request_):
    assert gate.decide(request_).allowed is False


def test_integration_has_no_way_to_call_a_service():
    for path in (ROOT / "custom_components/bram").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\.services\b|async_call|async_fire|states\.async_set", text), path


@pytest.mark.parametrize(("entity", "device_class", "kind"), [
    ("person.a", None, "person"), ("lock.a", None, "lock"),
    ("binary_sensor.a", "moisture", "leak"), ("binary_sensor.a", "motion", None),
    ("cover.a", "garage", "opening"), ("cover.a", "blind", None), ("light.a", None, None)])
def test_kinds(entity, device_class, kind):
    assert kind_of(entity, device_class) == kind


def test_code_format():
    with pytest.raises(InvalidCode):
        parse_code("bram1-x-y")
