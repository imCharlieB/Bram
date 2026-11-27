import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.persistent_notification import async_create
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_mock_service,
)

from custom_components.bram.queries import answer
from custom_components.bram.security import check
from custom_components.bram.security_watch import SecurityWatch

pytestmark = pytest.mark.usefixtures("custom")


def texts(result):
    return [f["text"] for f in result["findings"]]


async def test_a_plain_home_has_no_findings_but_says_what_it_skipped(hass):
    result = await check(hass)
    assert result["findings"] == []
    assert any(n.startswith("Devices on your network") for n in result["not_checked"])


async def test_findings(hass):
    lock = er.async_get(hass).async_get_or_create("lock", "demo", "1", suggested_object_id="front")
    hass.states.async_set(lock.entity_id, "locked", {"friendly_name": "Front lock"})
    async_expose_entity(hass, "conversation", lock.entity_id, True)
    hass.states.async_set("switch.bridge_permit_join", "on")
    hass.states.async_set("update.home_assistant_core_update", "on", {"friendly_name": "Core"})
    hass.config.external_url = "http://example.org"
    async_create(hass, "x", "y", "http-login")
    hass.data["automation"] = SimpleNamespace(entities=[
        SimpleNamespace(raw_config={"triggers": [{"trigger": "webhook", "local_only": False}]}),
        SimpleNamespace(raw_config={"trigger": {"platform": "webhook"}})])
    for i in range(3):
        MockUser(id=f"u{i}", name=f"Secretname{i}", is_owner=True).add_to_hass(hass)
    result = await check(hass)
    del hass.data["automation"]
    said = " | ".join(texts(result))
    for words in ("Assist can see or use Front lock", "joining is open", "not encrypted",
                  "failed to sign in", "1 automation can be started", "administrators", "Core"):
        assert words in said, words
    assert "Secretname" not in str(result)
    assert result["findings"][0]["level"] == "high"


async def test_a_check_that_breaks_is_listed_as_not_run(hass):
    with patch.object(hass.auth, "async_get_users", side_effect=RuntimeError):
        assert "Accounts and tokens" in (await check(hass))["not_checked"]


async def test_the_server_gets_it_only_if_turned_on_and_never_ids(hass):
    off = MockConfigEntry(domain="bram", options={})
    assert await answer(hass, off, {}, "security", "") == {"error": "off"}
    on = MockConfigEntry(domain="bram", options={"share_security": True})
    assert (await answer(hass, on, {}, "security", "")).keys() == {"findings", "not_checked"}


async def test_watch_tells_once_about_something_new(hass):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = MockConfigEntry(domain="bram", options={
        "security_watch": True, "phones": ["mobile_app_phone"]})
    MockUser(id="old", is_owner=True).add_to_hass(hass)
    watch = SecurityWatch(hass, entry)
    stop = await watch.start()
    await watch.run()
    assert calls == []  # what was already there is not news
    MockUser(id="new", is_owner=True).add_to_hass(hass)
    await watch.run()
    await watch.run()
    assert [c.data["message"] for c in calls] == ["A new administrator account was created"]
    stop()


async def test_a_failed_first_look_learns_nothing(hass):
    calls = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = MockConfigEntry(domain="bram", options={
        "security_watch": True, "phones": ["mobile_app_phone"]})
    MockUser(id="old", is_owner=True).add_to_hass(hass)
    watch = SecurityWatch(hass, entry)
    (await watch.start())()
    with patch.object(hass.auth, "async_get_users", side_effect=RuntimeError):
        await watch.run()
    await watch.run()
    await watch.run()
    assert calls == []


async def test_old_tokens_are_judged_by_age_and_never_called_unused(hass, freezer):
    user = await hass.auth.async_create_user("Someone", group_ids=[GROUP_ID_ADMIN])
    await hass.auth.async_create_refresh_token(
        user, client_name="x", token_type="long_lived_access_token")  # noqa: S106
    freezer.tick(datetime.timedelta(days=91))
    said = " ".join(texts(await check(hass)))
    assert "1 access token more than 90 days old" in said and "not used" not in said


async def test_printer_cameras_are_not_security_devices(hass, freezer):
    registry = er.async_get(hass)
    for platform in ("octoprint", "generic"):
        entry = registry.async_get_or_create("camera", platform, "1", suggested_object_id=platform)
        hass.states.async_set(entry.entity_id, "unavailable", {"friendly_name": platform.title()})
    freezer.tick(datetime.timedelta(minutes=31))
    assert texts(await check(hass)) == ["Offline: Generic"]


async def test_new_devices_on_the_network_and_paired(hass):
    from homeassistant.helpers import device_registry as dr

    DATA_DHCP = "dhcp"  # Home Assistant's own key for what its DHCP discovery has seen
    hass.data[DATA_DHCP] = SimpleNamespace(address_data={
        "aa:bb:cc:00:00:01": {"hostname": "laptop", "ip": "10.0.0.5"}})
    zigbee = MockConfigEntry(domain="zha")
    zigbee.add_to_hass(hass)
    first = await check(hass, {})
    assert first["ids"]["network"] == ["dhcp:aa:bb:cc:00:00:01"]
    known = {k: v for k, v in first["ids"].items()}
    assert not [f for f in first["findings"] if f["key"].startswith("new:")]
    hass.data[DATA_DHCP].address_data["AA:BB:CC:00:00:02"] = {"hostname": "", "ip": "10.0.0.9"}
    dr.async_get(hass).async_get_or_create(config_entry_id=zigbee.entry_id, name="Door sensor",
                                           identifiers={("zha", "x")})
    later = await check(hass, known, away=True)
    news = {f["key"]: (f["level"], f["text"]) for f in later["findings"]
            if f["key"].startswith("new:")}
    assert news["new:network:dhcp:aa:bb:cc:00:00:02"] == (
        "high", "A new device joined your network while everyone is away: a device at 10.0.0.9")
    (paired,) = [v for k, v in news.items() if k.startswith("new:radio:")]
    assert paired == ("medium", "A new Zigbee device was paired: Door sensor")
    del hass.data[DATA_DHCP]


async def test_router_update_guest_wifi_and_weak_zwave_locks(hass):
    router = MockConfigEntry(domain="opnsense")
    router.add_to_hass(hass)
    registry = er.async_get(hass)
    for domain, object_id, state in (("update", "firmware", "on"), ("switch", "guest_wifi", "on")):
        made = registry.async_get_or_create(domain, "opnsense", object_id,
                                            config_entry=router, suggested_object_id=object_id)
        hass.states.async_set(made.entity_id, state, {"friendly_name": object_id})
    zwave = MockConfigEntry(domain="zwave_js")
    zwave.add_to_hass(hass)
    from homeassistant.helpers import device_registry as dr
    device = dr.async_get(hass).async_get_or_create(config_entry_id=zwave.entry_id,
                                                    identifiers={("zwave_js", "1")})
    lock = registry.async_get_or_create("lock", "zwave_js", "1", config_entry=zwave,
                                        device_id=device.id, suggested_object_id="front")
    hass.states.async_set(lock.entity_id, "locked", {"friendly_name": "Front lock"})
    with patch("custom_components.bram.security._zwave_security", return_value="S0_LEGACY"):
        said = " | ".join(texts(await check(hass)))
    for words in ("Router update waiting: firmware", "Guest Wi-Fi is on: guest_wifi",
                  "Z-Wave lock without S2 security", "Front lock"):
        assert words in said, words
    with patch("custom_components.bram.security._zwave_security",
               return_value="S2_ACCESS_CONTROL"):
        assert "S2" not in " | ".join(texts(await check(hass)))
