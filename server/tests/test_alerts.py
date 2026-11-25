import json

import httpx
import pytest

from bram.alerts import (
    DAILY_NOTICES,
    HOUSE_DOWN_AFTER,
    MAX_SAFETY,
    SNOOZE,
    Alerts,
    Outgoing,
    quiet_until,
)
from bram.audit import Audit
from bram.channels import ChannelError, Ntfy, Telegram, new_topic
from bram.settings import Settings


class Box:
    def __init__(self, name="box"):
        self.name, self.sent, self.broken, self.on = name, [], False, True

    def ready(self):
        return self.on

    async def send(self, message):
        if self.broken:
            raise RuntimeError("secret detail")
        self.sent.append(message)


class Env:
    def __init__(self):
        self.now, self.quiet = 1_000_000.0, {}
        self.audit = Audit(":memory:")
        self.alerts = Alerts(":memory:", self.audit, lambda c: self.quiet, lambda: self.now)
        self.box = Box()
        self.alerts.channels = [self.box]

    async def wait(self, seconds):
        end = self.now + seconds
        while self.now < end:
            self.now = min(self.now + 30, end)
            await self.alerts.tick()

    async def leak(self):
        self.alerts.raise_alert("h", "s", "Water leak detected.", safety=True)
        await self.alerts.tick()


@pytest.fixture
def env():
    e = Env()
    yield e
    e.alerts.close()
    e.audit.close()


@pytest.mark.rule("C4")
async def test_safety_repeats_until_limit(env):
    await env.leak()
    assert len(env.box.sent) == 1 and env.box.sent[0].safety
    await env.wait(86400)
    assert len(env.box.sent) == MAX_SAFETY
    assert "reminder" in env.box.sent[1].title


@pytest.mark.rule("C4")
async def test_safety_stops_when_acknowledged(env):
    await env.leak()
    label, action = env.box.sent[0].buttons[0]
    assert label == "Acknowledge" and len(env.box.sent[0].buttons) == 1
    assert env.alerts.answer(action, "test") == "Acknowledged."
    await env.wait(86400)
    assert len(env.box.sent) == 1
    # Still leaking and acknowledged: not a new alert. Cleared and leaking again: it is.
    assert env.alerts.raise_alert("h", "s", "x", safety=True) is None
    env.alerts.clear("h", "s", safety=True)
    assert env.alerts.raise_alert("h", "s", "x", safety=True)


async def test_clearing_does_not_stop_an_unacknowledged_safety_alert(env):
    await env.leak()
    env.alerts.clear("h", "s", "Dry again.", safety=True)
    await env.wait(200)
    reminders = [m for m in env.box.sent if m.safety]
    assert len(reminders) == 2 and "since cleared" in reminders[1].text
    assert [m.text for m in env.box.sent if not m.safety] == ["Dry again."]


@pytest.mark.rule("C3")
async def test_nothing_suppresses_safety(env):
    env.quiet = {"from": 0, "to": 23, "timezone": "UTC"}
    env.alerts._db.execute("INSERT INTO mute VALUES ('h', 's')")
    for i in range(DAILY_NOTICES + 5):
        env.alerts.raise_alert("h", f"n{i}", "notice", safety=False)
    await env.leak()
    assert [m.safety for m in env.box.sent] == [True]
    alert_id = env.box.sent[0].alert_id
    for verb in ("snooze", "mute", "approve", ""):
        env.alerts.answer(f"{verb}:{alert_id}", "test")
    await env.wait(130)
    assert len(env.box.sent) == 2


async def test_broken_channel_does_not_stop_another_and_retries(env):
    other = Box("other")
    env.alerts.channels.append(other)
    env.box.broken = True
    await env.leak()
    assert len(other.sent) == 1 and env.box.sent == []
    env.box.broken = False
    await env.wait(61)
    assert len(env.box.sent) == 1
    assert "secret detail" not in json.dumps(env.audit.recent(50))


async def test_safety_never_gives_up_on_a_broken_channel(env):
    env.box.broken = True
    await env.leak()
    await env.wait(7200)
    env.box.broken = False
    await env.wait(61)
    assert len(env.box.sent) == 1


async def test_survives_restart(tmp_path):
    audit, box = Audit(":memory:"), Box()
    first = Alerts(tmp_path / "a.db", audit)
    first.raise_alert("h", "s", "Water leak detected.", safety=True)
    first.close()
    second = Alerts(tmp_path / "a.db", audit)
    second.channels = [box]
    await second.tick()
    assert [m.text for m in box.sent] == ["Water leak detected."]
    second.close()
    audit.close()


async def test_house_down_and_back(env):
    env.alerts.house_down("h", "Home")
    await env.wait(HOUSE_DOWN_AFTER - 60)
    env.alerts.house_up("h", "Home")
    await env.wait(3600)
    assert env.box.sent == []
    env.alerts.house_down("h", "Home")
    await env.wait(HOUSE_DOWN_AFTER + 60)
    assert len(env.box.sent) == 1 and "lost contact" in env.box.sent[0].text
    env.alerts.house_up("h", "Home")
    await env.wait(86400)
    assert env.box.sent[-1].text == "Home Assistant (Home) is back."
    assert sum(m.safety for m in env.box.sent) == 1


@pytest.mark.rule("E8")
async def test_notice_snooze_mute_and_unmute(env):
    env.alerts.raise_alert("h", "n", "note", safety=False)
    await env.alerts.tick()
    env.alerts.answer(env.box.sent[0].buttons[1][1], "test")
    await env.wait(SNOOZE - 60)
    assert len(env.box.sent) == 1
    await env.wait(120)
    assert len(env.box.sent) == 2
    env.alerts.answer(env.box.sent[1].buttons[2][1], "test")
    env.alerts.clear("h", "n", safety=False)
    assert env.alerts.raise_alert("h", "n", "note", safety=False) is None
    assert env.alerts.muted() == [{"house_id": "h", "key": "n"}]
    env.alerts.unmute("h", "n")
    assert env.alerts.raise_alert("h", "n", "note", safety=False)


@pytest.mark.rule("E8")
async def test_daily_limit(env):
    for i in range(DAILY_NOTICES + 3):
        env.alerts.raise_alert("h", f"n{i}", "note", safety=False)
    await env.alerts.tick()
    await env.alerts.tick()
    assert len(env.box.sent) == DAILY_NOTICES


@pytest.mark.rule("E8")
async def test_quiet_hours_delay_notices(env):
    env.now = 1_700_000_000.0  # 22:13:20 UTC
    env.quiet = {"from": 22, "to": 7, "timezone": "UTC"}
    env.alerts.raise_alert("h", "n", "note", safety=False)
    await env.wait(8 * 3600)
    assert env.box.sent == []
    await env.wait(3600)
    assert len(env.box.sent) == 1


def test_quiet_until():
    at = 1_700_000_000.0
    assert quiet_until({}, at) is None
    assert quiet_until({"from": 5, "to": 5}, at) is None
    assert quiet_until({"from": 1, "to": 6, "timezone": "UTC"}, at) is None
    assert quiet_until({"from": 22, "to": 23, "timezone": "UTC"}, at) == 1_700_002_800
    assert quiet_until({"from": 22, "to": 7, "timezone": "America/New_York"}, at) is None


async def test_late_channel_gets_open_alerts_only(env):
    env.box.on = False
    env.alerts.raise_alert("h", "old", "old", safety=True)
    env.now += 2 * 86400
    await env.leak()
    env.box.on = True
    await env.alerts.tick()
    assert [m.text for m in env.box.sent] == ["Water leak detected."]


async def test_forgotten_house_goes_quiet(env):
    await env.leak()
    env.alerts.house_down("h", "Home")
    env.alerts.forget_house("h")
    await env.wait(86400)
    assert len(env.box.sent) == 1


async def test_answered_in_home_assistant_stops_here_too(env):
    await env.leak()
    env.alerts.settle("h", "s")
    await env.wait(86400)
    assert len(env.box.sent) == 1
    assert env.alerts.raise_alert("h", "s", "x", safety=True)


# --- channels ---

MESSAGE = Outgoing("0" * 16, "BRAM alert", "Leak", True, (("Acknowledge", "ack:" + "0" * 16),))
BOT = "123456789:" + "A" * 35


@pytest.fixture
def settings():
    s = Settings(":memory:")
    yield s
    s.close()


def telegram(settings, handler=None, clock=lambda: 0):
    calls, answers = [], []

    def default(request):
        calls.append((request.url, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {}})

    t = Telegram(settings, lambda a, by: answers.append((a, by)) or "Acknowledged.",
                 httpx.MockTransport(handler or default), clock)
    return t, calls, answers


def text(user, body, chat=None, kind="private", bot=False):
    return {"message": {"from": {"id": user, "is_bot": bot}, "text": body,
                        "chat": {"id": chat or user, "type": kind}}}


async def test_telegram_links_one_account_with_a_one_time_code(settings):
    settings.update_channel("telegram", {"on": True, "token": BOT})
    t, calls, _ = telegram(settings)
    await t.handle(text(5, "/start guess"))
    await t.handle(text(5, "hello"))
    assert calls == [] and not t.ready()
    code = t.new_link()
    for bad in (text(5, f"/start {code}", chat=-9, kind="group"),
                text(5, f"/start {code}", bot=True)):
        await t.handle(bad)
    assert not t.ready()
    await t.handle(text(5, f"/start {code}"))
    assert t.ready() and settings.channel("telegram")["user_id"] == 5
    await t.handle(text(6, f"/start {code}"))
    assert settings.channel("telegram")["user_id"] == 5


async def test_telegram_link_expires_and_limits_guesses(settings):
    settings.update_channel("telegram", {"on": True, "token": BOT})
    now = [0]
    t, _, _ = telegram(settings, clock=lambda: now[0])
    code = t.new_link()
    now[0] = 601
    await t.handle(text(5, f"/start {code}"))
    assert not t.ready()
    code = t.new_link()
    for _ in range(5):
        await t.handle(text(6, "/start no"))
    await t.handle(text(5, f"/start {code}"))
    assert not t.ready()


async def test_telegram_buttons_only_from_the_linked_account(settings):
    settings.update_channel("telegram", {"on": True, "token": BOT, "user_id": 5})
    t, calls, answers = telegram(settings)
    good = "ack:" + "0" * 16
    await t.handle({"callback_query": {"id": "1", "from": {"id": 6}, "data": good}})
    await t.handle({"callback_query": {"id": "1", "from": {}, "data": good}})
    assert answers == [] and calls == []
    for data in ("unlock:" + "0" * 16, "approve", None, good + "x"):
        await t.handle({"callback_query": {"id": "1", "from": {"id": 5}, "data": data}})
    assert answers == []
    await t.handle({"callback_query": {"id": "1", "from": {"id": 5}, "data": good}})
    assert answers == [(good, "telegram")]


async def test_unlinked_telegram_ignores_presses_without_a_sender(settings):
    settings.update_channel("telegram", {"on": True, "token": BOT})
    t, _, answers = telegram(settings)
    await t.handle({"callback_query": {"id": "1", "data": "ack:" + "0" * 16}})
    assert answers == []


async def test_telegram_errors_never_contain_the_token(settings):
    settings.update_channel("telegram", {"on": True, "token": BOT, "user_id": 5})

    def down(request):
        raise httpx.ConnectError(f"failed {request.url}")

    for handler in (down, lambda r: httpx.Response(401, json={"ok": False}),
                    lambda r: httpx.Response(200, text="junk")):
        t, _, _ = telegram(settings, handler)
        with pytest.raises(ChannelError) as err:
            await t.send(MESSAGE)
        assert BOT not in str(err.value) and err.value.__cause__ is None


async def test_telegram_refuses_a_token_that_would_change_the_address(settings):
    t, calls, _ = telegram(settings)
    for token in ("", "x", "123456:abc/../evil" + "a" * 30, BOT + "/x"):
        with pytest.raises(ChannelError):
            await t.bot_name(token)
    assert calls == []


async def test_ntfy_message(settings):
    sent = []

    def handler(request):
        sent.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={})

    settings.update_channel("ntfy", {"on": True, "url": "http://127.0.0.1:80", "reply": "bram-r",
                                     "phone_url": "http://10.0.0.5:2586/", "topic": "bram-t"})
    n = Ntfy(settings, lambda a, b: "", httpx.MockTransport(handler))
    assert n.ready()
    await n.send(MESSAGE)
    url, body = sent[0]
    assert url == "http://127.0.0.1/" and body["topic"] == "bram-t" and body["priority"] == 5
    assert body["actions"][0]["url"] == "http://10.0.0.5:2586/bram-r"
    settings.update_channel("ntfy", {"url": "http://8.8.8.8"})
    with pytest.raises(ChannelError):
        await n.send(MESSAGE)
    assert len(sent) == 1


def test_ntfy_accepts_only_button_presses(settings):
    answers = []
    n = Ntfy(settings, lambda a, by: answers.append(a) or "")
    good = "ack:" + "a" * 16
    for line in ("", "junk", "[]", json.dumps({"event": "keepalive"}),
                 json.dumps({"event": "message", "message": "unlock the door", "id": "1"}),
                 json.dumps({"event": "message", "message": good + " extra"}),
                 json.dumps({"event": "message", "message": ["ack"]})):
        n.handle(line)
    assert answers == []
    assert n.handle(json.dumps({"event": "message", "message": good, "id": "z"})) == "z"
    assert answers == [good]


def test_topics_are_unguessable():
    assert len({new_topic() for _ in range(50)}) == 50 and len(new_topic()) == 15
