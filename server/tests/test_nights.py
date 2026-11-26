import datetime
from zoneinfo import ZoneInfo

from bram.history import History
from bram.nights import MIN_SEEN, quiet_gap, summarize
from bram.world import Event, World

UTC = ZoneInfo("UTC")
NIGHT = datetime.datetime(2026, 1, 4, 18, tzinfo=datetime.UTC).timestamp()  # 6 PM
NOW = NIGHT + 20 * 3600  # 2 PM the next day
ALL = range(int(NIGHT), int(NIGHT + 18 * 3600), 300)


def at(minutes):
    return NIGHT + minutes * 60


def test_longest_quiet_stretch():
    assert quiet_gap([0, 20, 60, 160]) == [300, 800]
    assert quiet_gap([]) is None and quiet_gap([5]) is None
    assert quiet_gap([0, 10, 20]) is None  # no long quiet
    assert quiet_gap([0, 200]) is None  # nobody home


def test_a_watched_night_becomes_its_quiet_stretch():
    changes = [(1, "motion", at(0), "no"), (1, "motion", at(5), "yes"),
               (1, "motion", at(345), "no"), (1, "motion", at(346), "yes"),
               (1, "motion", at(780), "no"), (1, "motion", at(781), "yes")]
    found = summarize(changes, ALL, UTC, NOW)
    assert found["nights"] == {"2026-01-04": [345, 780]}


def test_a_night_not_watched_is_left_out():
    changes = [(1, "motion", at(0), "no"), (1, "motion", at(5), "yes"),
               (1, "motion", at(780), "no"), (1, "motion", at(781), "yes")]
    assert summarize(changes, list(ALL)[:MIN_SEEN - 1], UTC, NOW)["nights"] == {}


def test_motion_ending_is_not_activity_and_unknown_is_not_a_change():
    changes = [(1, "motion", at(0), "no"), (1, "motion", at(10), "yes"),
               (1, "motion", at(300), "no"),  # motion clearing is not someone moving
               (1, "motion", at(400), "unknown"), (1, "motion", at(410), "yes"),
               (1, "motion", at(700), "no"), (1, "motion", at(701), "yes")]
    assert summarize(changes, ALL, UTC, NOW)["nights"] == {"2026-01-04": [10, 700]}


def test_how_long_doors_stay_open_and_unknown_is_not_a_closing():
    changes = [(2, "opening", at(0), "no"), (2, "opening", at(10), "yes"),
               (2, "opening", at(17), "no"), (2, "opening", at(20), "yes"),
               (2, "opening", at(25), "unknown"), (2, "opening", at(30), "no")]
    assert summarize(changes, ALL, UTC, NOW)["opens"] == {"2026-01-04": [7]}
    # A day not over yet is left out.
    assert summarize(changes, ALL, UTC, at(60))["opens"] == {}


def test_history_counts_nights_from_what_it_recorded(tmp_path):
    clock = [NIGHT - 600]
    history = History(tmp_path / "h.db", lambda: True, clock=lambda: clock[0])
    world = World("h1", clock=lambda: clock[0])
    motion = 0
    while clock[0] < NOW:
        minutes = (clock[0] - NIGHT) / 60
        if minutes < 0 or minutes < 345 or minutes >= 780:
            motion += 1  # someone moving about every minute, except 11:45 PM to 7 AM
            e = Event("h1", "binary_sensor.hall", "motion", "on" if motion % 2 else "off",
                      "Hall", {})
            world.update(e)
            history.record(e, world)
        world.heartbeat()
        history.sample([world])
        clock[0] += 60
    # The last movement is at 11:44 PM, in the 11:40 step.
    assert history.learning("h1", UTC)["nights"] == {"2026-01-04": [340, 780]}
    assert history.learning("h2", UTC)["nights"] == {}  # another home's nights stay apart
    history.close()


async def test_sent_to_home_assistant_only_when_it_understands():
    from bram.server import HISTORY, HOUSES, SOCKETS, tell_learning

    class Socket:
        def __init__(self):
            self.sent = []

        async def send_json(self, message):
            self.sent.append(message)

    class Kept:
        on = True

        def learning(self, house_id, zone):
            return {"nights": {"2026-01-04": [345, 780]}, "opens": {}}

    world, ws = World("h1"), Socket()
    app = {SOCKETS: {"h1": ws}, HOUSES: {"h1": (world, None)}, HISTORY: Kept()}
    told = {}
    world.version = "0.33.0"
    await tell_learning(app, "h1", told)
    assert ws.sent == []
    world.version = "0.34.0"
    await tell_learning(app, "h1", told)
    await tell_learning(app, "h1", told)  # unchanged, so not again
    assert ws.sent == [{"type": "learned", "nights": {"2026-01-04": [345, 780]}, "opens": {}}]
