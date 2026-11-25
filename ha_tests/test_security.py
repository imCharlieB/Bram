from types import SimpleNamespace
from unittest.mock import patch

import pytest
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
    assert "Your router and network" in result["not_checked"]


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
