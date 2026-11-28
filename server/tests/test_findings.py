import pytest

from bram.alerts import HOUSE_KEY, Alerts
from bram.audit import Audit
from bram.findings import Findings

KEY = "rules:night:lock.a"


class Env:
    def __init__(self):
        self.now, self.count = 1_700_000_000.0, 0
        self.f = Findings(":memory:", lambda: self.now)

    def note(self, what, key=KEY, house="h1", **extra):
        self.count += 1
        self.now += 10
        self.f.from_home(house, {
            "type": "note", "id": f"{self.count:016x}", "at": self.now, "key": key, "what": what,
            "text": f"text {what}", "source": "rules", "severity": "low", **extra})

    def only(self, which="open"):
        (row,) = self.f.list(which)
        return row


@pytest.fixture
def env():
    e = Env()
    yield e
    e.f.close()


def test_one_finding_with_its_story(env):
    for what in ("open", "sent", "acked", "closed"):
        env.note(what)
    assert env.f.list("open") == []
    row = env.only("closed")
    assert row["told"] and row["acked"] and row["closed"] and row["times"] == 1
    assert [s["what"] for s in env.f.story(row["id"])] == ["closed", "acked", "sent", "open"]


def test_again_is_counted_and_starts_fresh(env):
    for what in ("open", "acked", "closed", "open", "open"):
        env.note(what)
    row = env.only()
    assert row["times"] == 2 and row["acked"] is None and row["closed"] is None
    assert len(env.f.story(row["id"])) == 4


def test_the_same_note_twice_counts_once(env):
    env.note("open")
    env.note("sent")
    again = {"id": f"{env.count:016x}"}
    env.note("sent", **again)
    assert len(env.f.story(env.only()["id"])) == 2


def test_homes_are_kept_apart(env):
    env.note("open")
    env.note("open", house="h2", id=f"{env.count:016x}")  # same id, another home
    assert len(env.f.list("open")) == 2 and len(env.f.list("open", house_id="h2")) == 1
    env.f.forget_house("h1")
    assert len(env.f.list("open")) == 1


def test_end_of_something_never_seen_is_nothing(env):
    env.note("closed")
    assert not env.f.list("closed")


def test_message_without_a_finding_is_not_open(env):
    env.note("sent", key="message:digest", source="message")
    assert env.f.list("open") == [] and env.only("closed")["told"]


@pytest.mark.parametrize("bad", [
    {"id": "x"}, {"id": 5}, {"source": "evil"}, {"what": "unlock"}, {"severity": "x"},
    {"key": None}, {"text": ["x"]}])
def test_bad_notes_are_refused(env, bad):
    with pytest.raises(ValueError):
        env.note(**{"what": "open", **bad})
    assert env.f.list("open") == []


def test_silly_times_and_text_are_made_safe(env):
    env.note("open", at=9e99, text="a\nb\x00" + "x" * 5000)
    row = env.only()
    assert row["first"] == env.now and "\n" not in row["text"] and len(row["text"]) <= 1000


def test_ignore_changes_only_the_list(env):
    env.note("open")
    assert env.f.ignore(env.only()["id"], True) and not env.f.list("open")
    assert env.only("ignored")["is_open"]
    assert not env.f.ignore(True, True) and not env.f.ignore("1", True)


def test_hidden_comes_back_when_it_happens_again(env):
    env.note("open")
    env.f.ignore(env.only()["id"], True)
    env.note("open")  # still the same time: stays hidden
    assert env.f.list("open") == []
    env.note("closed")
    env.note("open")
    assert env.only()["ignored"] == 0


def test_learned_copy(env):
    env.note("learned", key="night:2026-01-04", source="learning", text="[345, 780]")
    env.note("learned", key="night:2026-01-04", source="learning", text="[345, 785]")
    assert env.f.learned("h1") == 1 and env.f.list("open") == []
    for key, text in (("night:x", "[1]"), ("evil:2026-01-04", "[1]"),
                      ("night:2026-01-04", "{}"), ("night:2026-01-04", "nope")):
        with pytest.raises(ValueError):
            env.note("learned", key=key, source="learning", text=text)
    env.note("forgot", key="learned", source="learning")
    assert env.f.learned("h1") == 0


def test_server_alerts_are_findings_too(env):
    alerts = Alerts(":memory:", Audit(":memory:"), clock=lambda: env.now)
    alerts.findings = env.f
    alert = alerts.raise_alert("server", "monitor:1", "NAS is not answering", safety=False)
    assert env.only()["source"] == "monitors"
    alerts.answer(f"ack:{alert}", "Telegram")
    assert env.only()["acked"]
    alerts.clear("server", "monitor:1", "NAS is back", safety=False)
    assert not env.f.list("open") and env.only("closed")["closed"]
    alerts.raise_alert("h1", HOUSE_KEY, "lost", safety=True)
    assert env.only()["source"] == "connection"
    # An escalated home alert is the same finding Home Assistant reported.
    env.note("open", key="safety:binary_sensor.leak", source="safety", severity="high")
    alerts.raise_alert("h1", "binary_sensor.leak", "Leak. Not acknowledged.", safety=True)
    assert len(env.f.list("open")) == 2


PRINT = ('{"printer": "Big One", "file": "boat", "start": 1699990000, "end": 1699999000, '
         '"result": "finished", "whole": true, "progress": 100, "weight": 12}')


def test_prints_are_kept_only_with_history_on(env):
    env.note("print", key="print:x", source="printers", text=PRINT)
    assert env.f.prints("h1") == []
    env.f.keep_prints = lambda: True
    env.note("print", key="print:x", source="printers", text=PRINT)
    env.note("print", key="print:x", source="printers", text=PRINT, id=f"{env.count:016x}")
    (row,) = env.f.prints("h1")
    assert row["file"] == "boat" and row["weight"] == 12 and env.f.prints("h2") == []
    for bad in ("{}", "[]", PRINT.replace("finished", "evil"), PRINT.replace("1699990000", "1e99")):
        with pytest.raises(ValueError):
            env.note("print", key="print:x", source="printers", text=bad)
    env.f.forget_house("h1")
    assert env.f.prints("h1") == []



def test_decisions_are_what_was_told_or_held_and_why(env):
    for what in ("open", "sent", "held", "closed"):
        env.note(what)
    rows = env.f.decisions(0)
    assert [r["what"] for r in rows] == ["held", "sent"] and rows[0]["about"] == "text open"
    assert env.f.decisions(0, "h2") == [] and env.f.sent_since(0) == 1


STOP = {"action": "BRAM_QUIET_night:lock.a", "title": "Stop these"}
LESS = {"action": "BRAM_LESS_0123456789abcdef", "title": "Less often"}


def test_buttons_offered_by_home_assistant(env):
    env.note("open")
    env.note("buttons", buttons=[STOP, LESS])
    row = env.only()
    assert env.f.button(row["id"], LESS["action"]) == ("h1", KEY)
    assert env.f.button(row["id"], "BRAM_ACK_x") is None
    assert env.f.button(str(row["id"]), LESS["action"]) is None
    env.f.pressed(row["id"], LESS["action"])
    assert env.f.button(row["id"], LESS["action"]) is None
    assert env.f.button(row["id"], STOP["action"])
    env.note("closed")
    assert env.f.button(row["id"], STOP["action"]) is None


@pytest.mark.parametrize("buttons", [
    [{"action": "BRAM_ACK_a", "title": "Acknowledge"}],
    [{"action": "BRAM_QUIET_a", "title": "Unlock"}],
    [{"action": "unlock", "title": "Stop these"}],
    [{"action": "BRAM_QUIET_a", "title": "Stop these", "x": 1}],
    [STOP] * 4, "x"])
def test_only_stop_and_less_buttons_are_kept(env, buttons):
    env.note("open")
    with pytest.raises(ValueError):
        env.note("buttons", buttons=buttons)


def test_hidden_again_and_again_becomes_a_suggestion(env):
    for _ in range(3):
        env.note("open")
        env.f.ignore(env.only()["id"], True)
        env.note("closed")
    assert env.f.habits("h1") == [(KEY, "You hid it 3 times in two weeks.")]
    env.f.suggested("h1", KEY)
    assert env.f.habits("h1") == []  # not again for 30 days
    env.now += 31 * 86400
    assert env.f.habits("h1") == []  # and nothing new was hidden since


def test_told_often_with_nothing_done(env):
    env.note("open")
    for _ in range(5):
        env.note("sent")
    (found,) = env.f.habits("h1")
    assert "5 times" in found[1]
    env.note("acked")
    assert env.f.habits("h1") == []  # something was done


@pytest.mark.rule("C3")
def test_safety_is_never_suggested(env):
    env.note("open", key="safety:leak", source="safety", severity="high")
    for _ in range(9):
        env.note("sent", key="safety:leak", source="safety", severity="high")
    assert env.f.habits("h1") == []


def test_bram_learns_what_needs_no_window_on_its_own(env):
    """No answers needed: something that keeps fixing itself stops popping up on Home."""
    env.note("open")
    assert env.f.routine(env.only()) == ""  # the first time always gets a window
    for _ in range(2):
        env.now += 600
        env.note("closed")
        env.now += 86400
        env.note("open")
    assert env.f.routine(env.only()) == "It fixed itself 2 of 3 times in two weeks."


def test_what_stays_open_or_is_safety_always_gets_a_window(env):
    for _ in range(3):
        env.note("open")
        env.now += 7200  # fixed, but only after hours: not routine
        env.note("closed")
    env.note("open")
    assert env.f.routine(env.only()) == ""
    env.f.from_home("h1", {"type": "note", "id": "f" * 16, "at": env.now, "key": "safety:x",
                           "what": "open", "text": "Leak", "source": "safety",
                           "severity": "medium"})
    leak = next(r for r in env.f.list("open") if r["source"] == "safety")
    for _ in range(3):
        env.f.ignore(leak["id"], True)
    assert env.f.routine(leak) == ""


def test_hidden_twice_is_routine(env):
    env.note("open")
    row = env.only()
    env.f.ignore(row["id"], True)
    env.note("closed")
    env.note("open")
    env.f.ignore(env.only()["id"], True)
    env.note("closed")
    env.note("open")
    assert env.f.routine(env.only()) == "You hid it 2 times in two weeks."
