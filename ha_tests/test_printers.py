import datetime
import json

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.bram.printer_watch import HEAT_AFTER, LOST_AFTER, PrinterWatch
from custom_components.bram.printers import find, read

pytestmark = pytest.mark.usefixtures("custom")

# What each integration really calls things.
IDS = {
    "bambu_lab": {"status": "SN_print_status", "progress": "SN_print_progress",
                  "left": "SN_remaining_time", "file": "SN_subtask_name",
                  "nozzle": "SN_right_nozzle_temp", "nozzle2": "SN_left_nozzle_temp",
                  "nozzle_target": "SN_right_target_nozzle_temp",
                  "bed": "SN_bed_temp", "bed_target": "SN_target_bed_temp",
                  "chamber": "SN_chamber_temp", "problem": "SN_hms", "weight": "SN_print_weight"},
    "moonraker": {"status": "e1_print_state", "progress": "e1_progress",
                  "left": "e1_print_time_left", "file": "e1_filename", "nozzle": "e1_extruder_temp",
                  "nozzle_target": "e1_extruder_target", "bed": "e1_heater_bed_temp",
                  "bed_target": "e1_heater_bed_target"},
    "octoprint": {"status": "Current State-x", "progress": "Job Percentage-x",
                  "ends": "Estimated Finish Time-x", "file": "Current File-x",
                  "nozzle": "actual tool0 temp-x", "nozzle_target": "target tool0 temp-x",
                  "bed": "actual bed temp-x", "bed_target": "target bed temp-x",
                  "problem": "Printing Error-x"},
    "prusalink": {"status": "e1_printer.state", "progress": "e1_job.progress",
                  "ends": "e1_job.finish", "file": "e1_job.filename",
                  "nozzle": "e1_printer.telemetry.temp-nozzle",
                  "nozzle_target": "e1_printer.telemetry.temp-nozzle.target",
                  "bed": "e1_printer.telemetry.temp-bed"},
}


class Env:
    def __init__(self, hass, freezer, platform="moonraker", **options):
        self.hass, self.freezer, self.platform = hass, freezer, platform
        self.calls = async_mock_service(hass, "notify", "mobile_app_phone")
        self.entry = MockConfigEntry(domain=platform, state=ConfigEntryState.LOADED)
        self.entry.add_to_hass(hass)
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=self.entry.entry_id, identifiers={(platform, "p")}, name="Big One")
        self.ids = {}
        for role, uid in IDS[platform].items():
            self.ids[role] = er.async_get(hass).async_get_or_create(
                "binary_sensor" if role == "problem" else "sensor", platform, uid,
                device_id=device.id, config_entry=self.entry).entity_id
        self.items, self.notes = [], []
        self.watch = PrinterWatch(hass, MockConfigEntry(domain="bram", options={
            "printers": True, "phones": ["mobile_app_phone"],
            "printers_chosen": [device.id], **options}),
            lambda items: self.items.append(items) or True, lambda *a: self.notes.append(a))

    def set(self, **values):
        for role, value in values.items():
            attrs = ({"unit_of_measurement": "\u00b0C"} if role in (
                "nozzle", "nozzle2", "bed", "nozzle_target", "bed_target", "chamber") else
                {"unit_of_measurement": "h"} if role == "left" else {})
            self.hass.states.async_set(self.ids[role], str(value), attrs)

    async def run(self, seconds=30, **values):
        self.set(**values)
        self.freezer.tick(datetime.timedelta(seconds=seconds))
        await self.watch.run()

    def now(self):
        (printer,) = find(self.hass)
        return read(self.hass, printer)

    def texts(self):
        return [c.data["message"] for c in self.calls]

    def opened(self):
        return [n[0].split(":")[1] for n in self.notes if n[1] == "open"]


@pytest.fixture(autouse=True)
def unloaded(hass):
    yield
    # Pretend integrations, so nothing tries to unload them for real.
    for entry in hass.config_entries.async_entries():
        entry.mock_state(hass, ConfigEntryState.NOT_LOADED)


@pytest.fixture
def env(hass, freezer):
    return Env(hass, freezer)


@pytest.mark.parametrize("platform", list(IDS))
async def test_each_integration_is_understood(hass, freezer, platform):
    env = Env(hass, freezer, platform)
    (printer,) = find(hass)
    assert {r: e for r, (e,) in printer.roles.items()} == env.ids
    word = {"bambu_lab": "running"}.get(platform, "printing")
    env.set(status=word, progress=42, file="boat.gcode", nozzle=210, bed=60)
    if "left" in env.ids:
        env.set(left=1.5)
    else:
        env.set(ends=(dt_util.utcnow() + datetime.timedelta(minutes=90)).isoformat())
    now = env.now()
    assert (now["state"], now["progress"], now["file"]) == ("printing", 42, "boat.gcode")
    assert now["left"] == 5400 and now["nozzle"] == 210 and now["unit"] == "\u00b0C"


async def test_other_devices_are_not_printers(hass, freezer):
    env = Env(hass, freezer)
    other = MockConfigEntry(domain="zha", state=ConfigEntryState.NOT_LOADED)
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("zha", "x")})
    er.async_get(hass).async_get_or_create("sensor", "zha", "x_print_state", device_id=device.id,
                                           config_entry=other)
    assert [p.name for p in find(hass)] == ["Big One"] and env


@pytest.mark.parametrize(("status", "state"), [
    ("unavailable", "off"), ("unknown", "unknown"), ("brand_new_word", "unknown"),
    ("standby", "idle"), ("complete", "finished"), ("error", "failed")])
async def test_states(env, status, state):
    env.set(status=status, nozzle="unavailable", file="unknown")
    now = env.now()
    assert now["state"] == state and "nozzle" not in now and "file" not in now


async def test_a_print_from_start_to_finish(env):
    await env.run(status="printing", progress=0, file="boat.gcode")
    for _ in range(3):
        await env.run(1200, progress=60)
    await env.run(status="complete", progress=100)
    await env.run()
    assert env.texts() == ["Big One: boat.gcode is finished after 1 h."]
    (record,) = [json.loads(n[2]) for n in env.notes if n[1] == "print"]
    assert record["result"] == "finished" and record["whole"] and record["file"] == "boat.gcode"
    await env.run(status="standby")
    assert len(env.texts()) == 1
    assert [n[1] for n in env.notes if n[0].startswith("printers:finished")] == [
        "open", "closed", "sent"]


@pytest.mark.parametrize(("status", "progress", "word"), [
    ("error", 40, "failed"), ("cancelled", 40, "was stopped"), ("standby", 40, "was stopped"),
    ("standby", 100, "is finished")])
async def test_how_it_ended(env, status, progress, word):
    await env.run(status="printing", progress=progress, file="boat.gcode")
    await env.run(status=status)
    assert word in env.texts()[0] and "after" not in env.texts()[0]  # its start was not seen


async def test_unreachable_is_not_an_ending(env):
    await env.run(status="printing", progress=50, file="a")
    await env.run(status="unavailable")
    assert env.texts() == []
    await env.run(LOST_AFTER)
    await env.run()
    assert env.texts() == ["Big One stopped answering during a print."]
    await env.run(status="printing")
    assert ("lost", "closed") in [(n[0].split(":")[1], n[1]) for n in env.notes]
    await env.run(status="complete")
    assert "is finished" in env.texts()[-1]


async def test_off_when_idle_is_normal(env):
    await env.run(status="standby")
    for _ in range(30):
        await env.run(60, status="unavailable")
    assert env.texts() == [] and env.opened() == []


async def test_paused(env):
    await env.run(status="paused", progress=30)
    assert env.texts() == []
    await env.run(60)
    await env.run(60)
    assert env.texts() == ["Big One is paused at 30%."]


async def test_heater_left_on(env):
    await env.run(status="standby", nozzle=210, nozzle_target=210, bed=25, bed_target=0)
    await env.run(HEAT_AFTER - 60)
    assert env.texts() == []
    await env.run(120)
    assert env.texts() == ["Big One is not printing, but its nozzle heater is still on."]
    await env.run(status="unavailable")  # cannot tell, so not over
    assert not [n for n in env.notes if n[1] == "closed" and "hot" in n[0]]
    await env.run(status="standby", nozzle=40, nozzle_target=0)
    assert [n for n in env.notes if n[1] == "closed" and "hot" in n[0]]


async def test_cooling_down_is_not_left_on(env):
    for _ in range(60):
        await env.run(60, status="complete", nozzle=150, nozzle_target=0, bed=60, bed_target=0)
    assert env.opened() == []


async def test_cannot_hold_its_temperature(env):
    for _ in range(20):
        await env.run(60, status="printing", progress=30, nozzle=120, nozzle_target=210)
    assert "far below its target" in env.texts()[0] and len(env.texts()) == 1


@pytest.mark.rule("E8")
async def test_quiet_hours_stop_these_and_waiting(hass, freezer):
    env = Env(hass, freezer, quiet_from="00:00:00", quiet_to="23:59:59")
    stop = await env.watch.start()
    await env.run(status="printing", progress=50, file="a")
    await env.run(status="complete")
    assert env.texts() == []
    env.watch._quiet = (None, None)
    await env.run()
    assert len(env.texts()) == 1  # held, not lost
    action = env.calls[0].data["data"]["actions"][0]["action"]
    hass.bus.async_fire("mobile_app_notification_action", {"action": action})
    await hass.async_block_till_done()
    await env.run(status="printing", progress=1)
    await env.run(status="complete")
    assert len(env.texts()) == 1
    stop()


async def test_sent_to_the_server_when_it_changes(env):
    await env.run(status="standby")
    await env.run()
    assert len(env.items) == 1
    await env.run(status="printing")
    assert len(env.items) == 2 and env.items[-1][0]["state"] == "printing"


async def test_a_printer_not_switched_on_is_not_watched(hass, freezer):
    env = Env(hass, freezer)
    env.watch._chosen = []
    await env.run(status="printing", progress=50)
    await env.run(status="complete")
    assert env.items == [[]] and env.texts() == []


async def test_what_the_problem_is(hass, freezer):
    env = Env(hass, freezer, "bambu_lab")
    env.set(status="running")
    hass.states.async_set(env.ids["problem"], "on", {
        "Count": 1, "1-Code": "HMS_0300", "1-Error": "The nozzle\nis clogged", "1-Url": "x"})
    now = env.now()
    assert now["problem"] and now["problem_text"] == "The nozzle is clogged"


async def test_removed_or_disabled_printers_are_gone(hass, freezer):
    env = Env(hass, freezer)
    (printer,) = find(hass)
    dr.async_get(hass).async_update_device(printer.id, disabled_by=dr.DeviceEntryDisabler.USER)
    assert find(hass) == []
    dr.async_get(hass).async_update_device(printer.id, disabled_by=None)
    await hass.config_entries.async_remove(env.entry.entry_id)
    assert find(hass) == []



async def test_a_reminder_is_told_once_even_if_it_comes_and_goes(hass, freezer):
    env = Env(hass, freezer, "bambu_lab")
    lube = {"1-Error": "Threaded rods need lubrication now."}
    for _ in range(6):
        env.hass.states.async_set(env.ids["problem"], "on", lube)
        await env.run(30, status="running", progress=10)
        await env.run(90)
        env.hass.states.async_set(env.ids["problem"], "off")
        await env.run(30)
        await env.run(3600 * 25)
    assert len([t for t in env.texts() if "lubrication" in t]) == 1


async def test_a_real_problem_is_told_again_only_after_a_day_fixed(hass, freezer):
    env = Env(hass, freezer, "bambu_lab")
    clog = {"1-Error": "Nozzle clogged"}
    env.hass.states.async_set(env.ids["problem"], "on", clog)
    await env.run(30, status="running", progress=10)
    await env.run(90)
    for _ in range(5):  # flickering
        env.hass.states.async_set(env.ids["problem"], "off")
        await env.run(300)
        env.hass.states.async_set(env.ids["problem"], "on", clog)
        await env.run(30)
        await env.run(90)
    assert len(env.texts()) == 1
    env.hass.states.async_set(env.ids["problem"], "off")
    await env.run(30)
    await env.run(3600 * 25)
    env.hass.states.async_set(env.ids["problem"], "on", clog)
    await env.run(30)
    await env.run(90)
    assert len(env.texts()) == 2
    env.hass.states.async_set(env.ids["problem"], "on", {"1-Error": "Something else"})
    await env.run(30)
    env.hass.states.async_set(env.ids["problem"], "off")
    await env.run(60)
    env.hass.states.async_set(env.ids["problem"], "on", {"1-Error": "Something else"})
    await env.run(30)
    await env.run(90)
    assert len(env.texts()) == 3 and "Something else" in env.texts()[-1]



async def test_a_failing_integration_says_so_and_an_ignored_one_is_not_there(hass, freezer):
    env = Env(hass, freezer)
    env.entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    (printer,) = find(hass)
    assert read(hass, printer)["state"] == "failing"
    object.__setattr__(env.entry, "source", "ignore")
    assert find(hass) == []
