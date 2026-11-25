import asyncio
import hashlib
import ssl

import aiohttp
import pytest
from aiohttp import web

from bram.audit import Audit
from bram.pairing import Pairing, ensure_certificate
from bram.server import HOUSES, _log_house, make_app


class Running:
    pass


@pytest.fixture
async def srv(tmp_path):
    s = Running()
    s.now = 1000.0
    context, s.fingerprint = ensure_certificate(tmp_path)
    s.pairing = Pairing(tmp_path / "bram.db", clock=lambda: s.now)
    s.audit = Audit(tmp_path / "bram.db")
    s.app = make_app(s.pairing, s.audit)
    runner = web.AppRunner(s.app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
    await site.start()
    s.port = runner.addresses[0][1]
    s.url = f"https://127.0.0.1:{s.port}"
    s.pin = aiohttp.Fingerprint(bytes.fromhex(s.fingerprint))
    async with aiohttp.ClientSession() as s.http:
        yield s
    await runner.cleanup()
    s.pairing.close()
    s.audit.close()


def secret(srv):
    return srv.pairing.new_code("Test", srv.fingerprint).split("-")[2]


async def pair(srv, value):
    return await srv.http.post(srv.url + "/pair", json={"secret": value}, ssl=srv.pin)


async def paired(srv):
    return await (await pair(srv, secret(srv))).json()


def feed(srv, token):
    return srv.http.ws_connect(srv.url + "/feed", ssl=srv.pin,
                               headers={"Authorization": f"Bearer {token}"})


async def until(check):
    async with asyncio.timeout(3):
        while not check():  # noqa: ASYNC110
            await asyncio.sleep(0.01)


STATE = {"entity_id": "binary_sensor.x", "kind": "leak", "state": "on"}


@pytest.mark.rule("G1")
async def test_unpaired_peers_are_refused(srv):
    for headers in ({}, {"Authorization": "Bearer "}, {"Authorization": "Bearer wrong"},
                    {"Authorization": "Basic x"}):
        with pytest.raises(aiohttp.WSServerHandshakeError) as err:
            await srv.http.ws_connect(srv.url + "/feed", ssl=srv.pin, headers=headers)
        assert err.value.status == 401
    # The client refuses a server whose certificate is not the paired one.
    wrong = aiohttp.Fingerprint(hashlib.sha256(b"other").digest())
    with pytest.raises(aiohttp.ServerFingerprintMismatch):
        await srv.http.get(srv.url + "/health", ssl=wrong)
    # Unencrypted connections fail.
    with pytest.raises(aiohttp.ClientError):
        await srv.http.get(f"http://127.0.0.1:{srv.port}/health")


async def test_code_works_once_and_expires(srv):
    code = secret(srv)
    assert (await pair(srv, code)).status == 200
    assert (await pair(srv, code)).status == 403
    late = secret(srv)
    srv.now += 601
    assert (await pair(srv, late)).status == 403
    assert (await pair(srv, "guess")).status == 403
    assert (await pair(srv, None)).status == 403


async def test_secrets_are_not_stored_in_plain_text(srv, tmp_path):
    code = secret(srv)
    waiting = secret(srv)
    token = (await (await pair(srv, code)).json())["token"]
    stored = b"".join(p.read_bytes() for p in tmp_path.glob("bram.db*"))
    for value in (code, waiting, token):
        assert value.encode() not in stored


async def test_feed_logs_what_it_would_say(srv):
    house = await paired(srv)
    async with feed(srv, house["token"]) as ws:
        await ws.send_json({"type": "snapshot", "states": [STATE]})
        await until(lambda: any(r["decision"] == "noticed"
                                for r in srv.audit.entries(house["house_id"])))
        world = srv.app[HOUSES][house["house_id"]][0]
        assert world.check("binary_sensor.x") == "yes"
    await until(lambda: world.check("binary_sensor.x") == "unknown")


async def test_house_comes_from_token(srv):
    a, b = await paired(srv), await paired(srv)
    async with feed(srv, a["token"]) as ws:
        await ws.send_json({"type": "snapshot",
                            "states": [{**STATE, "house_id": b["house_id"]}]})
        await until(lambda: len(srv.audit.entries(a["house_id"])) == 3)
        assert all(r["decision"] == "paired" for r in srv.audit.entries(b["house_id"]))


@pytest.mark.parametrize("message", [
    "not json", "[]", '{"type": "call_service"}', '{"type": "snapshot"}',
    '{"type": "state", "state": {}}', '{"type": "snapshot", "states": [{"entity_id": 1}]}'])
async def test_bad_message_closes_connection(srv, message):
    house = await paired(srv)
    async with feed(srv, house["token"]) as ws:
        await ws.receive(timeout=3)  # hello
        await ws.send_str(message)
        reply = await asyncio.wait_for(ws.receive(), 3)
        assert reply.type is aiohttp.WSMsgType.CLOSE


async def test_new_connection_replaces_old(srv):
    house = await paired(srv)
    async with feed(srv, house["token"]) as old, feed(srv, house["token"]) as new:
        await old.receive(timeout=3)  # hello
        assert (await asyncio.wait_for(old.receive(), 3)).type is aiohttp.WSMsgType.CLOSE
        await new.send_json({"type": "snapshot", "states": [STATE]})
        world = srv.app[HOUSES][house["house_id"]][0]
        await until(lambda: world.check("binary_sensor.x") == "yes")


async def test_unpaired_house_cannot_reconnect(srv):
    house = await paired(srv)
    assert srv.pairing.remove(house["house_id"])
    with pytest.raises(aiohttp.WSServerHandshakeError):
        await feed(srv, house["token"])


async def test_belief_is_returned_for_display(srv):
    house = await paired(srv)
    async with feed(srv, house["token"]) as ws:
        light = {"entity_id": "light.x", "kind": "light", "state": "on"}
        await ws.send_json({"type": "snapshot", "states": [light]})
        assert (await ws.receive_json(timeout=3))["type"] == "hello"
        assert await ws.receive_json(timeout=3) == {
            "type": "belief", "entity_id": "light.x", "answer": "yes"}
        await ws.send_json({"type": "state", "state": {**light, "state": "unavailable"}})
        assert (await ws.receive_json(timeout=3))["answer"] == "unknown"


def test_log_house_choice():
    one, two = [("a", "A")], [("a", "A"), ("b", "B")]
    assert _log_house(one, None) == "a" and _log_house(two, "b") == "b"
    for houses, wanted in ((one, "HOUSE_ID"), (two, None), ([], None)):
        with pytest.raises(SystemExit):
            _log_house(houses, wanted)


def test_certificate_is_kept(tmp_path):
    context, first = ensure_certificate(tmp_path)
    assert isinstance(context, ssl.SSLContext) and ensure_certificate(tmp_path)[1] == first
