import datetime
from unittest.mock import patch

import pytest
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bram.house_rules import HouseRules
from custom_components.bram.learning import ISSUE, MIN_SEEN, Learner, empty, quiet_gap, suggest
from custom_components.bram.repairs import async_create_fix_flow

pytestmark = pytest.mark.usefixtures("custom")

MOTION, DOOR = "binary_sensor.hall", "binary_sensor.back"


class Feed:
    learner = None

    def kind(self, entity_id):
        return {MOTION: "motion", DOOR: "opening"}.get(entity_id)


class Env:
    def __init__(self, hass):
        self.hass, self.now = hass, datetime.datetime(2026, 1, 4, 18, tzinfo=datetime.UTC)
        self.entry = MockConfigEntry(domain="bram", options={
            "entities": [MOTION, DOOR], "learn": True, "night_from": "22:00:00",
            "night_to": "06:00:00"})
        self.entry.add_to_hass(hass)

    async def start(self):
        feed = Feed()
        self.learner = feed.learner = Learner(self.hass, self.entry, feed)
        self.entry.runtime_data = feed
        self.stop = await self.learner.start()

    async def flip(self, entity=MOTION):
        for value in ("off", "on"):
            self.hass.states.async_set(entity, value)
            await self.hass.async_block_till_done()

    def at(self, hour, minute=0):
        self.now = self.now.replace(hour=hour, minute=minute)

    def fill(self, count=20, gap=(345, 780)):
        """Nights quiet from 11:45 PM to 7 AM."""
        first = datetime.date(2025, 12, 10)
        self.learner.data["nights"] = {
            (first + datetime.timedelta(days=i)).isoformat(): list(gap) for i in range(count)}


@pytest.fixture
async def env(hass):
    await hass.config.async_set_time_zone("UTC")
    e = Env(hass)
    with patch("homeassistant.util.dt.utcnow", side_effect=lambda: e.now), patch(
            "homeassistant.util.dt.now", side_effect=lambda *a: dt_util.as_local(e.now)):
        await e.start()
        yield e
        e.stop()


def test_longest_quiet_stretch():
    assert quiet_gap([0, 20, 60, 160]) == [300, 800]
    assert quiet_gap([]) is None and quiet_gap([5]) is None
    assert quiet_gap([0, 10, 20]) is None  # no long quiet
    assert quiet_gap([0, 200]) is None  # nobody home


async def test_a_night_becomes_one_line(env):
    await env.flip()
    env.at(23, 45)
    await env.flip()
    env.now += datetime.timedelta(days=1)
    env.at(7)
    await env.flip()
    env.learner.data["pending"]["seen"] = MIN_SEEN
    env.at(12, 5)
    env.learner.tick()
    assert env.learner.data["nights"] == {"2026-01-04": [345, 780]}
    assert env.learner.data["pending"] == {}


async def test_a_night_not_watched_is_left_out(env):
    await env.flip()
    env.learner.data["pending"]["active"] = [0, 69, 156]
    env.learner.data["pending"]["seen"] = MIN_SEEN - 1
    env.at(12, 5)
    env.learner.tick()
    assert env.learner.data["nights"] == {}


async def test_open_lengths_are_kept_and_unknown_is_not_a_closing(env):
    await env.flip(DOOR)
    env.now += datetime.timedelta(minutes=7)
    env.hass.states.async_set(DOOR, "off")
    await env.hass.async_block_till_done()
    await env.flip(DOOR)
    for value in ("unavailable", "off"):
        env.hass.states.async_set(DOOR, value)
        await env.hass.async_block_till_done()
    assert env.learner.data["opens"] == {"2026-01-04": [7]}


async def test_nothing_before_enough_days_and_nothing_for_small_changes(env):
    env.fill(13)
    assert suggest(env.learner.data, dict(env.entry.options)) is None
    env.fill(20, (245, 725))  # 10:05 PM to 6:05 AM
    assert suggest(env.learner.data, dict(env.entry.options)) is None


async def test_weekends_can_differ(env):
    env.fill(28, (240, 720))
    for day in env.learner.data["nights"]:
        if datetime.date.fromisoformat(day).weekday() in (4, 5):
            env.learner.data["nights"][day] = [420, 840]
    found = suggest(env.learner.data, dict(env.entry.options))
    assert found["set"] == {"weekend_night_from": "01:00:00", "weekend_night_to": "08:00:00"}


async def test_left_open_minutes():
    learned = {**empty(), "opens": {f"2026-01-{d:02}": [2, 24] for d in range(1, 15)}}
    assert suggest(learned, {"open_minutes": 10})["set"] == {"open_minutes": 25}
    learned["never"] = ["open"]
    assert suggest(learned, {"open_minutes": 10}) is None


async def answer(env, word):
    issue = ir.async_get(env.hass).async_get_issue("bram", ISSUE)
    flow = await async_create_fix_flow(env.hass, ISSUE, issue.data)
    flow.hass, flow.handler, flow.flow_id = env.hass, "bram", "x"
    flow.context = {}
    return await getattr(flow, f"async_step_{word}")()


@pytest.mark.rule("F4")
async def test_nothing_changes_until_approved_and_it_can_be_undone(env):
    env.fill()
    env.at(13)
    before = dict(env.entry.options)
    with patch.object(env.hass.config_entries, "async_schedule_reload") as reload:
        env.learner.tick()
        assert dict(env.entry.options) == before
        issue = ir.async_get(env.hass).async_get_issue("bram", ISSUE)
        assert "nights" in issue.translation_placeholders["text"]  # the evidence
        await answer(env, "approve")
    assert reload.called
    assert env.entry.options["night_from"] == "23:45:00"
    assert env.entry.options["night_to"] == "07:00:00"
    # Only hours can ever change: nothing that turns a rule or alert off.
    assert {k for k in env.entry.options if env.entry.options[k] != before.get(k)} == {
        "night_from", "night_to"}
    assert env.learner.undone(dict(env.entry.options)) == before


@pytest.mark.rule("F4")
async def test_a_suggestion_expires(env):
    env.fill()
    env.at(13)
    env.learner.tick()
    env.now += datetime.timedelta(days=31)
    env.learner.tick()
    assert env.learner.data["suggestion"] is None
    assert ir.async_get(env.hass).async_get_issue("bram", ISSUE) is None


@pytest.mark.parametrize("word", ["later", "never"])
async def test_no_is_respected(env, word):
    env.fill()
    env.at(13)
    env.learner.tick()
    before = dict(env.entry.options)
    await answer(env, word)
    env.learner.tick()
    assert dict(env.entry.options) == before and env.learner.data["suggestion"] is None
    assert env.learner.data["never"] == (["night"] if word == "never" else [])


async def test_off_notices_nothing_and_forget_deletes(hass, env):
    env.fill()
    await env.learner.forget()
    assert env.learner.data == empty()
    off = MockConfigEntry(domain="bram", options={"entities": [MOTION]})
    learner = Learner(hass, off, Feed())
    (await learner.start())()
    await env.flip()
    assert learner.data == empty()


@pytest.mark.parametrize(("day", "hour", "minute", "night"), [
    (1, 22, 30, True), (2, 22, 30, False), (3, 0, 30, False), (3, 1, 30, True),
    (4, 7, 0, True), (5, 7, 0, False)])
async def test_weekend_night_hours(env, day, hour, minute, night):
    # 1 January 2026 is a Thursday.
    rules = HouseRules(env.hass, MockConfigEntry(domain="bram", options={
        "night_from": "22:00:00", "night_to": "06:00:00",
        "weekend_night_from": "01:00:00", "weekend_night_to": "08:00:00"}))
    env.now = datetime.datetime(2026, 1, day, hour, minute, tzinfo=datetime.UTC)
    assert rules.is_night() is night


async def test_the_answer_works_through_home_assistants_own_repairs(env):
    env.hass.config.components.add("bram")
    assert await async_setup_component(env.hass, "repairs", {})
    await env.hass.async_block_till_done()
    env.fill()
    env.at(13)
    env.learner.tick()
    flows = env.hass.data["repairs"]["flow_manager"]
    shown = await flows.async_init("bram", data={"issue_id": ISSUE})
    assert shown["type"] == "menu" and "nights" in shown["description_placeholders"]["text"]
    done = await flows.async_configure(shown["flow_id"], {"next_step_id": "never"})
    assert done["type"] == "create_entry" and env.learner.data["never"] == ["night"]
