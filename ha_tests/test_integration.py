"""Integration tests, including the real server over real TLS."""
import asyncio
import json
import re
from pathlib import Path

import pytest
from aiohttp import web
from homeassistant.components import conversation
from homeassistant.core import Context, CoreState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from bram.alerts import Alerts
from bram.audit import Audit
from bram.chat import Reply
from bram.pairing import Pairing, ensure_certificate
from bram.server import CHAT, HOUSES, SOCKETS, make_app
from bram.settings import Settings
from custom_components.bram import gate
from custom_components.bram.client import InvalidCode, parse_code
from custom_components.bram.const import GROUPS
from custom_components.bram.feed import Feed, kind_of

ROOT = Path(__file__).parents[1]


@pytest.fixture
async def server(tmp_path, socket_enabled):
    context, fingerprint = ensure_certificate(tmp_path)
    audit, settings = Audit(":memory:"), Settings(":memory:")
    app = make_app(Pairing(":memory:"), audit, settings, fingerprint, Alerts(":memory:", audit))
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


async def reconnected(hass, entry):
    """Saving options reloads BRAM. Cutting off its handshake is an error on Linux."""
    await hass.async_block_till_done()
    await until(lambda: entry.runtime_data.connected)


async def options(hass, entry, step, values):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] is FlowResultType.MENU
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": step})
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await reconnected(hass, entry)


async def choose(hass, entry, entities):
    groups = {"people": [], "doors": [], "safety": [], "motion": [], "lights": []}
    for entity in entities:
        state = hass.states.get(entity)
        kind = kind_of(entity, state and state.attributes.get("device_class"))
        groups[next((g for g, kinds in GROUPS.items() if kind in kinds), "safety")].append(entity)
    await options(hass, entry, "see", groups)


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


def named(hass, source):
    for item in er.async_get(hass).entities.values():
        if item.platform == "bram" and item.unique_id.endswith(f"_{source}"):
            return hass.states.get(item.entity_id)
    return None


async def test_device_page_shows_what_bram_believes(hass, server):
    hass.states.async_set("light.a", "on", {"friendly_name": "Lamp"})
    hass.states.async_set("binary_sensor.m", "off", {"device_class": "motion"})
    entry = await start(hass, server)
    connected = next(s for s in hass.states.async_all("binary_sensor")
                     if s.attributes.get("device_class") == "connectivity")
    await choose(hass, entry, ["light.a", "binary_sensor.m"])
    await until(lambda: (s := named(hass, "light.a")) and s.state == "on")
    assert named(hass, "light.a").name == "BRAM Lamp"
    await until(lambda: named(hass, "binary_sensor.m").state == "clear")
    assert hass.states.get(connected.entity_id).state == "on"
    hass.states.async_set("binary_sensor.m", "on", {"device_class": "motion"})
    await until(lambda: named(hass, "binary_sensor.m").state == "detected")
    hass.states.async_set("light.a", "unavailable")
    await until(lambda: named(hass, "light.a").state == "unknown")

    for sock in list(server[0][SOCKETS].values()):
        await sock.close()
    await until(lambda: named(hass, "binary_sensor.m").state == "unavailable")
    assert hass.states.get(connected.entity_id).state == "off"

    await choose(hass, entry, ["binary_sensor.m"])
    await until(lambda: named(hass, "light.a") is None)
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_option_pages_keep_each_other(hass, server):
    async_mock_service(hass, "notify", "mobile_app_phone")
    hass.states.async_set(LEAK, "off", {"device_class": "moisture"})
    hass.states.async_set(LOCK, "locked")
    entry = await start(hass, server)
    await choose(hass, entry, [LOCK, LEAK])
    alerts = {"phones": ["mobile_app_phone"], "escalate": True}
    await options(hass, entry, "alerts", {
        **alerts, "quiet_from": "22:00:00", "quiet_to": "07:00:00"})
    assert entry.options["entities"] == [LOCK, LEAK] and entry.options["quiet_from"]
    # A missing sensor is kept when the page is saved unchanged.
    hass.states.async_remove(LEAK)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "see"})
    shown = {str(k): k.description["suggested_value"] for k in flow["data_schema"].schema}
    assert shown["safety"] == [LEAK] and shown["doors"] == [LOCK]
    hass.config_entries.options.async_abort(flow["flow_id"])
    await options(hass, entry, "see", shown)
    assert set(entry.options["entities"]) == {LOCK, LEAK}
    # An emptied group arrives as a missing one, and must stop being shared.
    await options(hass, entry, "see", {"safety": [LEAK]})
    assert entry.options["entities"] == [LEAK]
    assert entry.options["phones"] == ["mobile_app_phone"] and entry.options["escalate"]
    await options(hass, entry, "alerts", alerts)
    assert "quiet_from" not in entry.options
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_assist(hass, server, monkeypatch):
    assert await async_setup_component(hass, "homeassistant", {})
    calls = []
    hass.bus.async_listen("call_service", lambda e: calls.append(e))
    entry = await start(hass, server)
    asked = []

    async def ask(key, text, *, house):
        asked.append((key, text, house))
        return Reply("The door is locked.", [])

    monkeypatch.setattr(server[0][CHAT], "ask", ask)

    async def say(text):
        result = await conversation.async_converse(
            hass, text, None, Context(), agent_id="conversation.bram_assist")
        return result.response.speech["plain"]["speech"]

    await until(lambda: entry.runtime_data.connected)
    assert await say("is the door locked") == "The door is locked."
    assert asked[0][1:] == ("is the door locked", entry.data["house_id"])
    for sock in list(server[0][SOCKETS].values()):
        await sock.close()
    await until(lambda: not entry.runtime_data.connected)
    assert "can't reach" in await say("hello")
    assert calls == []
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unasked_answers_are_refused(hass):
    feed = Feed(hass, MockConfigEntry(domain="bram", options={"entities": []}))
    feed.handle_message('{"type": "answer", "id": "x", "text": "unlock"}')
    assert feed._asked == {}


async def test_version_warning(hass):
    feed = Feed(hass, MockConfigEntry(domain="bram", options={"entities": ["light.a"]}))
    feed.version = "0.6.3"

    def issue():
        found = ir.async_get(hass).async_get_issue("bram", "version")
        return found and found.translation_key

    def hello(version):
        feed.handle_message(json.dumps({"type": "hello", "version": version}))

    feed.handle_message('{"type": "belief", "entity_id": "light.a", "answer": "yes"}')
    assert issue() == "server_outdated"  # too old to say
    for version, expected in (("0.6.3", None), ("0.6.2", "server_outdated"),
                              ("0.10.0", "integration_outdated"), ("0.6.3", None)):
        hello(version)
        assert issue() == expected
    for bad in ("<b>1</b>", "1.2", "", 5):
        hello(bad)
        assert feed.server_version == "0.6.3"


async def test_names_wait_for_startup(hass, server):
    entry = await start(hass, server)
    hass.set_state(CoreState.starting)
    await choose(hass, entry, ["light.a"])
    assert named(hass, "light.a") is None
    hass.states.async_set("light.a", "on", {"friendly_name": "Lamp"})
    hass.set_state(CoreState.running)
    hass.bus.async_fire("homeassistant_started")
    await hass.async_block_till_done()
    await until(lambda: named(hass, "light.a"))
    assert named(hass, "light.a").name == "BRAM Lamp"
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_escalation_reaches_the_server(hass, server):
    from bram.server import ALERTS

    hass.states.async_set(LEAK, "on", {"device_class": "moisture"})
    entry = await start(hass, server)
    await choose(hass, entry, [LEAK])
    app = server[0]
    world = app[HOUSES][entry.data["house_id"]][0]
    await until(lambda: world.check(LEAK) == "yes")
    feed = entry.runtime_data
    assert feed.send({"type": "escalate", "entity_id": "lock.other"})
    assert feed.send({"type": "escalate", "entity_id": LEAK})

    def open_alerts():
        return [r[0] for r in app[ALERTS]._db.execute(
            "SELECT key FROM alert WHERE cleared IS NULL AND safety = 1")]

    await until(lambda: open_alerts() == [LEAK])
    feed.send({"type": "deescalate", "entity_id": LEAK})
    await until(lambda: open_alerts() == [])
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not app[SOCKETS])
    assert feed.send({"type": "heartbeat"}) is False


async def test_test_button(hass, server):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = await start(hass, server)
    await options(hass, entry, "alerts", {
        "phones": ["mobile_app_phone"], "escalate": False,
        "quiet_from": "22:00:00", "quiet_to": "07:00:00"})
    button = "button.bram_send_test_message"
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    assert calls[0].data["message"] == "This is a test message."
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


@pytest.mark.parametrize("raw", [
    "junk", "[]", "null", '{"type": "belief"}', '{"type": "call_service"}',
    '{"type": "belief", "entity_id": "lock.other", "answer": "yes"}',
    '{"type": "belief", "entity_id": ["light.a"], "answer": "yes"}',
    '{"type": "belief", "entity_id": "light.a", "answer": "unlock"}',
    '{"type": "belief", "entity_id": "light.a", "answer": ["yes"]}',
    '{"type": "belief", "entity_id": "light.a", "answer": "yes", "service": "x"}'])
async def test_unexpected_server_messages_change_nothing(hass, raw):
    entry = MockConfigEntry(domain="bram", options={"entities": ["light.a"]})
    feed = Feed(hass, entry)
    feed.handle_message(raw)
    assert feed.beliefs == {}


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


def test_only_the_notifier_calls_a_service_and_only_to_notify():
    text = (ROOT / "custom_components/bram/notifier.py").read_text(encoding="utf-8")
    assert re.findall(r"async_call\((\S+)", text) == ['"notify",']


def test_rest_of_integration_has_no_way_to_call_a_service():
    for path in (ROOT / "custom_components/bram").glob("*.py"):
        if path.name == "notifier.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\.services\b|async_call|async_fire|states\.async_set", text), path


@pytest.mark.parametrize(("entity", "device_class", "kind"), [
    ("person.a", None, "person"), ("lock.a", None, "lock"),
    ("binary_sensor.a", "moisture", "leak"), ("binary_sensor.a", "motion", "motion"),
    ("binary_sensor.a", "occupancy", "motion"), ("binary_sensor.a", "battery", None),
    ("cover.a", "garage", "opening"), ("cover.a", "blind", None),
    ("light.a", None, "light"), ("switch.a", None, None)])
def test_kinds(entity, device_class, kind):
    assert kind_of(entity, device_class) == kind


def test_code_format():
    with pytest.raises(InvalidCode):
        parse_code("bram1-x-y")
