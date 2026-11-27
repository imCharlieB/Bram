import datetime
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.house_rules import HouseRules
from custom_components.bram.learning import Learner, empty, quiet_gap, suggest

pytestmark = pytest.mark.usefixtures("custom")

MOTION, DOOR = "binary_sensor.hall", "binary_sensor.back"


class Feed:
    learner = None

    def __init__(self):
        self.notes = []

    def note(self, *a):
        self.notes.append(a)

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


GOOD = {"2026-01-03": [345, 780]}


async def test_summaries_from_the_servers_history_are_used(env):
    assert env.learner.received(GOOD, {"2026-01-03": [7, 2]})
    assert env.learner.data["nights"] == GOOD
    assert env.learner.data["opens"] == {"2026-01-03": [7, 2]}


@pytest.mark.parametrize(("nights", "opens"), [
    ({"2026-01-04": [345, 780]}, {}),  # tonight is not over
    ({"2025-01-03": [345, 780]}, {}),  # too old
    ({"2026-01-03": [345, 1200]}, {}),  # past noon
    ({"2026-01-03": [345, 400]}, {}),  # too short to be a night
    ({"2026-01-03": [345.0, 780]}, {}),
    ({"2026-01-03": "345,780"}, {}),
    ({"tomorrow": [345, 780]}, {}),
    ({}, {"2026-01-03": [0]}),
    ({}, {"2026-01-03": [5] * 201}),
    ({}, {"2026-01-04": [5]}),  # today is not over
    ([], {}), ({}, None)])
async def test_bad_summaries_change_nothing(env, nights, opens):
    env.learner.received(GOOD, {})
    assert not env.learner.received(nights, opens)
    assert env.learner.data["nights"] == GOOD and env.learner.data["opens"] == {}


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
    (item,) = env.learner.review()
    return env.learner.answer(item["id"], word, "Owner")


@pytest.mark.rule("F4")
async def test_nothing_changes_until_approved_and_it_can_be_undone(env):
    env.fill()
    env.at(13)
    before = dict(env.entry.options)
    with patch.object(env.hass.config_entries, "async_schedule_reload") as reload:
        env.learner.tick()
        assert dict(env.entry.options) == before
        (item,) = env.learner.review()
        assert "nights" in item["text"]  # the evidence
        assert item["changes"] == [
            {"name": "Night starts", "now": "10:00 PM", "new": "11:45 PM"},
            {"name": "Night ends", "now": "6:00 AM", "new": "7:00 AM"}]
        assert not env.learner.answer("learning:open", "approve", "Owner")  # not the one waiting
        assert await answer(env, "approve")
    assert reload.called
    assert env.entry.options["night_from"] == "23:45:00"
    assert env.entry.options["night_to"] == "07:00:00"
    # Only hours can ever change: nothing that turns a rule or alert off.
    assert {k for k in env.entry.options if env.entry.options[k] != before.get(k)} == {
        "night_from", "night_to"}
    assert env.learner.undone(dict(env.entry.options)) == before
    assert env.learner.review() == []


@pytest.mark.rule("F4")
async def test_a_suggestion_expires(env):
    env.fill()
    env.at(13)
    env.learner.tick()
    env.now += datetime.timedelta(days=31)
    env.learner.tick()
    assert env.learner.data["suggestion"] is None and env.learner.review() == []


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


async def test_off_takes_nothing_and_forget_starts_again(hass, env):
    env.fill()
    await env.learner.forget()
    assert env.learner.data == {**empty(), "since": "2026-01-04"}
    assert env.learner.received(GOOD, {}) and env.learner.data["nights"] == {}
    off = MockConfigEntry(domain="bram", options={"entities": [MOTION]})
    learner = Learner(hass, off, Feed())
    (await learner.start())()
    assert not learner.received(GOOD, {}) and learner.data == empty()


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


async def test_a_suggestion_sends_one_message_that_opens_the_review_page(env):
    calls = async_mock_service(env.hass, "notify", "mobile_app_phone")
    env.hass.config_entries.async_update_entry(env.entry, options={
        **env.entry.options, "phones": ["mobile_app_phone"]})
    env.fill()
    env.at(13)
    env.learner.tick()
    env.learner.tick()
    await env.hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["message"] == "Better night hours. Tap to review."
    assert calls[0].data["data"]["url"] == "/bram-review"
    assert calls[0].data["data"]["clickAction"] == "/bram-review"
