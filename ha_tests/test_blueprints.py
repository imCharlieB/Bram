"""BRAM's blueprints load in Home Assistant, ask BRAM, and message only as they say."""
import datetime
import shutil
from pathlib import Path

import pytest
from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

ROOT = Path(__file__).parents[1] / "custom_components/bram/blueprints/automation"
# The automations keep their schedule until Home Assistant stops.
pytestmark = pytest.mark.parametrize("expected_lingering_timers", [True])


@pytest.fixture
async def setup(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    shutil.copytree(ROOT, tmp_path / "blueprints/automation/bram")
    await hass.config.async_set_time_zone("UTC")
    asked, answer = [], {"text": ""}

    async def process(call: ServiceCall):
        asked.append(call.data)
        return {"response": {"speech": {"plain": {"speech": answer["text"]}}}}

    hass.services.async_register("conversation", "process", process,
                                 supports_response=SupportsResponse.ONLY)
    sent = async_mock_service(hass, "notify", "mobile_app_phone")

    async def start(name, **inputs):
        assert await async_setup_component(hass, "automation", {"automation": {
            "use_blueprint": {"path": f"bram/{name}.yaml", "input": {
                "agent": "conversation.bram_assist", "notify": "notify.mobile_app_phone",
                **inputs}}}})
        await hass.async_block_till_done()
    return start, asked, answer, sent


async def tick(hass, freezer, when):
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


@pytest.mark.parametrize(("said", "told"), [
    ("Yes, the back door is open.", True), ("No, everything is shut.", False),
    ("Yesterday it was open.", False), ("", False)])
async def test_scheduled_check_tells_only_on_yes(hass, freezer, setup, said, told):
    start, asked, answer, sent = setup
    answer["text"] = said
    freezer.move_to(datetime.datetime(2026, 1, 1, 9, 58, tzinfo=datetime.UTC))
    await start("scheduled_check", question="Is any door open?", every=60)
    await tick(hass, freezer, dt_util.parse_datetime("2026-01-01T09:59:00+00:00"))
    assert asked == []  # not on the hour yet
    await tick(hass, freezer, dt_util.parse_datetime("2026-01-01T10:00:00+00:00"))
    assert len(asked) == 1 and asked[0]["agent_id"] == "conversation.bram_assist"
    assert asked[0]["text"].startswith("Is any door open?")
    assert [c.data["message"] for c in sent] == ([said] if told else [])


async def test_house_summary_at_its_time(hass, freezer, setup):
    start, asked, answer, sent = setup
    answer["text"] = "Everyone is home and everything is locked."
    freezer.move_to(datetime.datetime(2026, 1, 1, 17, 59, tzinfo=datetime.UTC))
    await start("house_summary", at="18:00:00")
    await tick(hass, freezer, dt_util.parse_datetime("2026-01-01T18:00:00+00:00"))
    assert [c.data["message"] for c in sent] == [answer["text"]]
    assert sent[0].data["title"] == "BRAM house summary"


def test_copied_once_updated_when_untouched_and_never_over_the_owners(tmp_path):
    from custom_components.bram.blueprints import _mark, copy
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    (source / "a.yaml").write_text("one", encoding="utf-8")
    written = copy(source, target, {})
    assert (target / "a.yaml").read_text(encoding="utf-8") == "one"
    (source / "a.yaml").write_text("two", encoding="utf-8")
    written = copy(source, target, written)
    assert (target / "a.yaml").read_text(encoding="utf-8") == "two"
    (target / "a.yaml").write_text("mine", encoding="utf-8")
    (source / "a.yaml").write_text("three", encoding="utf-8")
    assert copy(source, target, written) == {"a.yaml": _mark("two")}
    assert (target / "a.yaml").read_text(encoding="utf-8") == "mine"
