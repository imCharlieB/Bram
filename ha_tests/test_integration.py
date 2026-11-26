"""Integration tests, including the real server over real TLS."""
import asyncio
import json
import re
from pathlib import Path

import pytest
from aiohttp import web
from homeassistant.components import conversation
from homeassistant.const import EntityCategory
from homeassistant.core import Context, CoreState, State
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from bram.alerts import Alerts
from bram.audit import Audit
from bram.chat import Reply
from bram.findings import Findings
from bram.pairing import Pairing, ensure_certificate
from bram.server import CHAT, FINDINGS, HOUSES, SOCKETS, make_app
from bram.settings import Settings
from custom_components.bram import gate
from custom_components.bram.client import InvalidCode, parse_code
from custom_components.bram.const import GROUPS
from custom_components.bram.discover import find, suggest
from custom_components.bram.feed import Feed, kind_of, say

pytestmark = pytest.mark.usefixtures("custom")

ROOT = Path(__file__).parents[1]


@pytest.fixture
async def server(tmp_path, socket_enabled):
    context, fingerprint = ensure_certificate(tmp_path)
    audit, settings = Audit(":memory:"), Settings(":memory:")
    app = make_app(Pairing(":memory:"), audit, settings, fingerprint, Alerts(":memory:", audit),
                   findings=Findings(":memory:"))
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
    groups = {g: [] for g in GROUPS}
    for entity in entities:
        state = hass.states.get(entity)
        kind = kind_of(entity, state and state.attributes.get("device_class"))
        groups[next((g for g, kinds in GROUPS.items() if kind in kinds), "other")].append(entity)
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
    async_mock_service(hass, "notify", "mobile_app_other")
    await options(hass, entry, "alerts", {
        **alerts, "safety_phones": ["mobile_app_other"],
        "quiet_from": "22:00:00", "quiet_to": "07:00:00"})
    assert entry.options["safety_phones"] == ["mobile_app_other"]
    assert entry.options["entities"] == [LOCK, LEAK] and entry.options["quiet_from"]
    # A missing sensor is kept when the page is saved unchanged.
    hass.states.async_remove(LEAK)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "see"})
    shown = {str(k): k.description["suggested_value"] for k in flow["data_schema"].schema}
    assert shown["other"] == [LEAK] and shown["doors"] == [LOCK]  # kept, type not known
    hass.config_entries.options.async_abort(flow["flow_id"])
    await options(hass, entry, "see", shown)
    assert set(entry.options["entities"]) == {LOCK, LEAK}
    # An emptied group arrives as a missing one, and must stop being shared.
    await options(hass, entry, "see", {"other": [LEAK]})
    assert entry.options["entities"] == [LEAK]
    assert entry.options["phones"] == ["mobile_app_phone"] and entry.options["escalate"]
    await options(hass, entry, "alerts", alerts)
    assert "quiet_from" not in entry.options and "safety_phones" not in entry.options
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


@pytest.mark.rule("A1")
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


def add_entity(hass, entity_id, device_class=None, device=None, state="off", **kw):
    domain, name = entity_id.split(".")
    er.async_get(hass).async_get_or_create(
        domain, "test", name, suggested_object_id=name, device_id=device and device.id, **kw)
    hass.states.async_set(entity_id, state, {"device_class": device_class})


async def test_find_devices(hass):
    MockConfigEntry(domain="test", entry_id="t").add_to_hass(hass)
    den = ar.async_get(hass).async_create("Den").id
    sensor = dr.async_get(hass).async_get_or_create(
        config_entry_id="t", identifiers={("test", "radar")})
    dr.async_get(hass).async_update_device(sensor.id, area_id=den)
    for name, cls in (("zone_1", "motion"), ("zone_2", "occupancy"), ("zone_3", "occupancy")):
        add_entity(hass, f"binary_sensor.{name}", cls, sensor)
    add_entity(hass, "binary_sensor.hall", "motion")
    add_entity(hass, "light.hidden", hidden_by=er.RegistryEntryHider.USER)
    add_entity(hass, "light.status", entity_category=EntityCategory.CONFIG)
    add_entity(hass, "light.lamp")
    add_entity(hass, "binary_sensor.battery", "battery")
    hass.states.async_set("person.alex", "home")
    hass.states.async_set("lock.front", "locked")
    assert set(find(hass, list(GROUPS), [])) == {
        "binary_sensor.zone_2", "binary_sensor.hall", "light.lamp", "person.alex", "lock.front"}
    assert set(find(hass, ["motion", "people", "lights"], [den])) == {
        "binary_sensor.zone_2", "person.alex"}
    assert find(hass, ["safety"], []) == []


async def test_suggestions(hass):
    MockConfigEntry(domain="test", entry_id="t").add_to_hass(hass)
    areas = {n: ar.async_get(hass).async_create(n).id for n in ("Den", "Hall")}
    for name, area in (("den_1", "Den"), ("den_2", "Den"), ("hall_1", "Hall"), ("loose", None)):
        add_entity(hass, f"binary_sensor.{name}", "motion")
        if area:
            er.async_get(hass).async_update_entity(
                f"binary_sensor.{name}", area_id=areas[area])
    hass.states.async_set("light.a", "on")
    hass.states.async_set(LOCK, "locked")
    hass.states.async_set("person.alex", "home")
    assert set(suggest(hass, [])) == {
        LOCK, "person.alex", "binary_sensor.den_1", "binary_sensor.hall_1"}
    assert suggest(hass, [LOCK, "person.alex", "binary_sensor.den_2"]) == [
        "binary_sensor.hall_1"]


async def test_suggestions_page(hass, server):
    entry = await start(hass, server)

    async def begin():
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        return await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "suggest"})

    assert (await begin())["reason"] == "nothing_to_suggest"
    hass.states.async_set(LOCK, "locked")
    flow = await begin()
    assert entry.options["entities"] == []
    with pytest.raises(InvalidData):  # only what was offered
        await hass.config_entries.options.async_configure(
            flow["flow_id"], {"skip": ["light.x"]})
    await hass.config_entries.options.async_configure(flow["flow_id"], {})
    await reconnected(hass, entry)
    assert entry.options["entities"] == [LOCK]
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_quick_add(hass, server):
    hass.states.async_set("light.a", "on")
    hass.states.async_set("light.b", "on")
    hass.states.async_set(LOCK, "locked")
    entry = await start(hass, server)
    await choose(hass, entry, ["light.a"])

    async def begin(groups):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "quick"})
        return await hass.config_entries.options.async_configure(
            flow["flow_id"], {"groups": groups})

    flow = await begin(["safety"])
    assert flow["errors"] == {"base": "nothing_found"}
    hass.config_entries.options.async_abort(flow["flow_id"])
    flow = await begin(["lights", "doors"])
    assert flow["description_placeholders"]["found"] == "- a\n- b"
    assert entry.options["entities"] == ["light.a"]  # nothing is shared by looking
    await hass.config_entries.options.async_configure(flow["flow_id"], {"skip": ["light.b"]})
    await reconnected(hass, entry)
    assert entry.options["entities"] == ["light.a", LOCK]
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_server_can_look_things_up_only_when_allowed(hass, server):
    from bram.server import ask_house

    entry = await start(hass, server)
    app, house = server[0], entry.data["house_id"]
    assert await ask_house(app, house, "problems") == {"error": "off"}
    await options(hass, entry, "chat", {"share_history": False, "share_problems": True})
    assert "errors" in await ask_house(app, house, "problems")
    assert await ask_house(app, house, "call_service") == {"error": "refused"}
    assert await ask_house(app, "other", "problems") is None
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not app[SOCKETS])
    assert await ask_house(app, house, "problems") is None


async def test_recommended_setup(hass, server):
    async_mock_service(hass, "notify", "mobile_app_phone")
    hass.states.async_set(LOCK, "locked")
    hass.states.async_set("person.alex", "home")
    entry = await start(hass, server)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "basic"})
    fields = {str(k): k for k in flow["data_schema"].schema}
    assert fields["phones"].default() == ["mobile_app_phone"]  # the only one
    assert "skip" in fields and not fields["skip"].description  # nothing filled in for you
    assert "away" not in fields and entry.options["entities"] == []
    await hass.config_entries.options.async_configure(flow["flow_id"], {
        "phones": ["mobile_app_phone"], "skip": ["person.alex"], "night": True, "left_open": True,
        "offline": False, "share_history": True, "summary": True})
    await reconnected(hass, entry)
    assert entry.options["entities"] == [LOCK] and entry.options["digest"] == "08:00:00"
    assert entry.runtime_data.rules._on == {"night", "left_open"}
    # Again, changing only what is asked, and keeping what was set elsewhere.
    hass.config_entries.async_update_entry(entry, options={
        **entry.options, "night_from": "23:30:00", "away": True})
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "basic"})
    await hass.config_entries.options.async_configure(flow["flow_id"], {
        "phones": ["mobile_app_phone"], "skip": ["person.alex"], "night": True,
        "left_open": True, "offline": False, "share_history": True, "summary": False})
    await reconnected(hass, entry)
    assert entry.options["entities"] == [LOCK] and "digest" not in entry.options
    assert entry.options["night_from"] == "23:30:00" and entry.options["away"]
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_mood(hass, server):
    from bram.server import SETTINGS, _tell_mood

    entry = await start(hass, server)
    app, mood = server[0], "select.bram_mood"
    await until(lambda: hass.states.get(mood).state == "Professional")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": mood, "option": "Unhinged"}, blocking=True)
    await until(lambda: hass.states.get(mood).state == "Unhinged")
    assert app[SETTINGS].all()["personality"] == "unhinged"
    app[SETTINGS].update({"personality": "dry"})
    await _tell_mood(app)
    await until(lambda: hass.states.get(mood).state == "Dry")
    entry.runtime_data.send({"type": "mood", "mode": "evil"})
    entry.runtime_data.handle_message('{"type": "mood", "mode": ["dry"]}')
    await asyncio.sleep(0.2)
    assert app[SETTINGS].all()["personality"] == "dry"
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not app[SOCKETS])


def test_a_known_sensor_is_never_downgraded(hass):
    feed = Feed(hass, MockConfigEntry(domain="bram", options={"entities": [LEAK]}))
    for attrs, value in (({"device_class": "moisture"}, "off"), ({}, "unavailable"), ({}, "on")):
        assert feed._state(LEAK, State(LEAK, value, attrs))["kind"] == "leak"
    assert feed._state(LEAK, None)["kind"] == "leak"


async def test_room_changes_reach_the_server(hass, server):
    MockConfigEntry(domain="bermuda", entry_id="b").add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(
        config_entry_id="b", identifiers={("bermuda", "phone")})
    for domain, name in (("device_tracker", "phone"), ("sensor", "phone_area")):
        er.async_get(hass).async_get_or_create(
            domain, "bermuda", name, suggested_object_id=name, device_id=phone.id)
    hass.states.async_set("sensor.phone_area", "Den")
    hass.states.async_set("person.alex", "home", {"device_trackers": ["device_tracker.phone"]})
    entry = await start(hass, server)
    await choose(hass, entry, ["person.alex"])
    world = server[0][HOUSES][entry.data["house_id"]][0]

    def room():
        event = world.event("person.alex")
        return event and event.detail.get("area")

    await until(lambda: room() == "Den")
    hass.states.async_set("sensor.phone_area", "Kitchen")
    await until(lambda: room() == "Kitchen")
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_choose_room_sensor(hass, server):
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})
    hass.states.async_set("sensor.alex_room", "Den")
    entry = await start(hass, server)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "rooms"})
    assert flow["reason"] == "no_people"
    await choose(hass, entry, ["person.alex"])
    await options(hass, entry, "rooms", {"Alex": "sensor.alex_room"})
    assert entry.options["rooms"] == {"person.alex": "sensor.alex_room"}
    world = server[0][HOUSES][entry.data["house_id"]][0]

    def room():
        event = world.event("person.alex")
        return event and event.detail.get("area")

    await until(lambda: room() == "Den")
    hass.states.async_set("sensor.alex_room", "Kitchen")
    await until(lambda: room() == "Kitchen")
    hass.states.async_set("sensor.alex_room", "unknown")
    await until(lambda: room() is None)
    await options(hass, entry, "rooms", {})
    assert entry.options["rooms"] == {}
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_watch_page(hass, server):
    entry = await start(hass, server)
    watch = {"night": True, "away": False, "left_open": True, "offline": False,
             "night_from": "23:00:00", "night_to": "05:00:00", "open_minutes": 15}
    await options(hass, entry, "watch", watch)
    assert watch.items() <= entry.options.items() and entry.options["entities"] == []
    assert entry.runtime_data.rules._on == {"night", "left_open"}
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.bram_allow_stopped_messages"}, blocking=True)
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


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
    for version, expected in (("0.6.3", None), ("0.6.9", None), ("0.5.9", "server_outdated"),
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


@pytest.mark.rule("A1")
def test_only_the_notifier_calls_a_service_and_only_to_notify():
    text = (ROOT / "custom_components/bram/notifier.py").read_text(encoding="utf-8")
    assert re.findall(r"async_call\((\S+)", text) == ['"notify",']


@pytest.mark.rule("A1")
def test_rest_of_integration_has_no_way_to_call_a_service():
    for path in (ROOT / "custom_components/bram").glob("*.py"):
        if path.name == "notifier.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\.services\b|async_call|async_fire|states\.async_set", text), path


@pytest.mark.parametrize(("entity", "device_class", "kind"), [
    ("person.a", None, "person"), ("lock.a", None, "lock"),
    ("binary_sensor.a", "moisture", "leak"), ("binary_sensor.a", "motion", "motion"),
    ("binary_sensor.a", "occupancy", "motion"), ("binary_sensor.a", "battery", "other"),
    ("cover.a", "garage", "opening"), ("cover.a", "blind", None),
    ("light.a", None, "light"), ("switch.a", None, "switch"), ("media_player.a", None, "media"),
    ("assist_satellite.a", None, "satellite"), ("sensor.a", "temperature", "temperature"),
    ("sensor.a", "battery", "other"), ("climate.a", None, "climate"), ("camera.a", None, None)])
def test_kinds(entity, device_class, kind):
    assert kind_of(entity, device_class) == kind


@pytest.mark.parametrize(("entity", "state", "attrs", "text"), [
    ("sensor.t", "71.2", {"unit_of_measurement": "F"}, "71.2 F"),
    ("climate.a", "heat", {"current_temperature": 70, "temperature": 72.5},
     "heat, now 70, set to 72.5"),
    ("climate.a", "off", {"temperature": None}, "off"),
    ("climate.a", "unavailable", {"temperature": 70}, "unavailable"),
    ("media_player.a", "playing", {}, "playing")])
def test_say(entity, state, attrs, text):
    assert say(State(entity, state, attrs)) == text


def test_code_format():
    with pytest.raises(InvalidCode):
        parse_code("bram1-x-y")


async def test_what_home_assistant_found_reaches_the_server(hass, server):
    hass.states.async_set(LEAK, "off", {"device_class": "moisture"})
    entry = await start(hass, server)
    await choose(hass, entry, [LEAK])
    found = server[0][FINDINGS]
    hass.states.async_set(LEAK, "on", {"device_class": "moisture"})
    await until(lambda: found.list("open"))
    (row,) = found.list("open")
    assert row["source"] == "safety" and row["house_id"] == entry.data["house_id"]
    hass.states.async_set(LEAK, "off", {"device_class": "moisture"})
    await until(lambda: found.list("closed"))
    await until(lambda: not entry.runtime_data.outbox._waiting)  # confirmed
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_printers_reach_the_server(hass, server):
    from bram.server import PRINTERS

    entry = await start(hass, server)
    feed, house = entry.runtime_data, entry.data["house_id"]
    await until(lambda: feed.takes_notes())
    assert feed.send_printers([{"id": "x", "name": "Big", "state": "printing", "progress": 5}])
    await until(lambda: server[0][PRINTERS].get(house))
    assert server[0][PRINTERS][house][0]["progress"] == 5
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: house not in server[0][PRINTERS])


async def test_leaving_everything_out_shares_nothing(hass, server):
    hass.states.async_set(LOCK, "locked")
    hass.states.async_set("person.alex", "home")
    entry = await start(hass, server)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "suggest"})
    await hass.config_entries.options.async_configure(
        flow["flow_id"], {"skip": [LOCK, "person.alex"]})
    await reconnected(hass, entry)
    assert entry.options["entities"] == []
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_turned_off_in_home_assistant_is_left_out(hass, server):
    registry = er.async_get(hass)
    leak = registry.async_get_or_create("binary_sensor", "demo", "leak1").entity_id
    hass.states.async_set(leak, "off", {"device_class": "moisture"})
    entry = await start(hass, server)
    await choose(hass, entry, [leak])
    world = server[0][HOUSES][entry.data["house_id"]][0]
    await until(lambda: world.check(leak) == "no")
    registry.async_update_entity(leak, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()
    await reconnected(hass, entry)
    await until(lambda: world.event(leak) is None and world.live)
    assert entry.runtime_data.entities == [] and entry.options["entities"] == [leak]
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])


async def test_renamed_in_home_assistant_is_followed(hass, server):
    registry = er.async_get(hass)
    lock = registry.async_get_or_create("lock", "demo", "l1", suggested_object_id="front").entity_id
    hass.states.async_set(lock, "locked")
    entry = await start(hass, server)
    await choose(hass, entry, [lock])
    registry.async_update_entity(lock, new_entity_id="lock.front_door")
    hass.states.async_set("lock.front_door", "unlocked")
    await hass.async_block_till_done()
    await reconnected(hass, entry)
    world = server[0][HOUSES][entry.data["house_id"]][0]
    assert entry.options["entities"] == ["lock.front_door"]
    await until(lambda: world.check("lock.front_door") == "yes")
    await hass.config_entries.async_unload(entry.entry_id)
    await until(lambda: not server[0][SOCKETS])
