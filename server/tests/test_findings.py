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
