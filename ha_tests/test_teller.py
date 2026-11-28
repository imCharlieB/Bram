import datetime

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bram.teller import (
    EACH_TIME,
    FIXED_FOR,
    MONTH,
    OFFER_LESS,
    Teller,
    grade,
)

pytestmark = pytest.mark.usefixtures("custom")


@pytest.mark.parametrize(("text", "kind"), [
    ("Threaded rods need lubrication now.", "monthly"), ("Replace the HEPA filter", "monthly"),
    ("Firmware update available", "monthly"), ("Nozzle clogged", "until fixed"),
    ("Kitchen sensor is offline", "until fixed")])
def test_words(text, kind):
    assert grade(text) == kind


@pytest.fixture
async def teller(hass, freezer):
    notes = []
    t = Teller(hass, MockConfigEntry(domain="bram"), lambda *a: notes.append(a))
    stop = await t.start()
    t.notes, t.freezer = notes, freezer
    yield t
    stop()


def say(teller, text="Nozzle clogged", usual="until fixed"):
    if teller.allow("k", text, usual):
        teller.told("k", text)
        return True
    return False


async def test_until_fixed(teller):
    assert say(teller)
    assert not say(teller)  # still going
    teller.ended("k")
    teller.freezer.tick(datetime.timedelta(minutes=20))
    assert not say(teller)  # back soon: the same event
    teller.ended("k")
    teller.freezer.tick(FIXED_FOR + 1)
    assert say(teller)
    assert say(teller, "Something else")


async def test_each_time_is_never_held_and_repeats_are_never_hidden_by_themselves(teller):
    for _ in range(10):
        assert say(teller, "Back door open", EACH_TIME)
        teller.ended("k")
        teller.freezer.tick(datetime.timedelta(minutes=15))


async def test_reminders_monthly(teller):
    text = "Threaded rods need lubrication now."
    assert say(teller, text)
    for _ in range(10):
        teller.ended("k")
        teller.freezer.tick(datetime.timedelta(days=2))
        assert not say(teller, text)
    teller.freezer.tick(MONTH)
    assert say(teller, text)


async def test_less_often_is_offered_and_only_the_owner_turns_it_on(hass, teller):
    for i in range(OFFER_LESS):
        assert (teller.actions("k") != []) is (i + 1 >= OFFER_LESS)
        assert say(teller, "Back door open", EACH_TIME)
    (button,) = teller.actions("k")
    hass.bus.async_fire("mobile_app_notification_action", {"action": button["action"]})
    await hass.async_block_till_done()
    assert not say(teller, "Back door open", EACH_TIME)
    teller.freezer.tick(datetime.timedelta(days=1, seconds=1))
    assert say(teller, "Back door open", EACH_TIME)
    teller.allow_all()
    assert say(teller, "Back door open", EACH_TIME)
    assert teller.notes and teller.actions("k") != []  # offered again


@pytest.mark.rule("F4")
async def test_bram_learns_by_itself_what_fixes_itself(teller):
    """No answers needed: something that keeps fixing itself within an hour waits an hour."""
    def ask():
        if teller.allow("k", "Car is offline", finding="f", asks_again=True):
            teller.told("k", "Car is offline")
            return True
        return False
    for _ in range(3):
        assert ask()
        teller.freezer.tick(datetime.timedelta(minutes=10))
        teller.ended("k")
        teller.freezer.tick(FIXED_FOR + 1)
    assert not ask()  # learned: wait and see
    assert "fixed itself within an hour 3 of 3 times" in teller.notes[-1][2]
    teller.freezer.tick(datetime.timedelta(minutes=30))
    assert not ask()
    teller.freezer.tick(datetime.timedelta(minutes=31))
    assert ask()  # still not fixed after an hour: told
    teller.allow_all()  # undo everything learned
    teller.ended("k")
    teller.freezer.tick(FIXED_FOR + 1)
    assert ask()


@pytest.mark.rule("F4")
async def test_learning_never_quiets_silent_safety_sensors(teller):
    for _ in range(8):
        assert teller.allow("silent:sensor.smoke", "Smoke sensor stopped reporting",
                            asks_again=True)
        teller.told("silent:sensor.smoke", "Smoke sensor stopped reporting")
        teller.freezer.tick(datetime.timedelta(minutes=5))
        teller.ended("silent:sensor.smoke")
        teller.freezer.tick(FIXED_FOR + 1)


async def test_what_keeps_coming_back_is_told_once_a_week(teller):
    def say():
        if teller.allow("k", "Nozzle clogged", finding="f"):
            teller.told("k", "Nozzle clogged")
            return True
        return False
    for _ in range(5):
        assert say()
        teller.freezer.tick(datetime.timedelta(hours=3))
        teller.ended("k")
        teller.freezer.tick(FIXED_FOR + 1)
    assert not say()  # the sixth time in two weeks, within a week of the last one
    assert "at most once a week" in teller.notes[-1][2]
    teller.ended("k")
    teller.freezer.tick(datetime.timedelta(days=7))
    assert say()
