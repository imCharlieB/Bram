import pytest

from bram.models.base import ModelError, Reply, ToolCall
from fakes import FakeHome, FakeModel, MaliciousModel


async def test_home_can_ignore_a_command():
    home = FakeHome({"lock.a": "unlocked"})
    home.ignores.add("lock.a")
    await home.call("lock", "lock", "lock.a")
    assert home.calls == [("lock", "lock", "lock.a")]
    assert home.state("lock.a") == "unlocked"


async def test_home_unknown_when_missing_or_offline():
    home = FakeHome({"lock.a": "locked"})
    assert home.state("lock.b") == "unknown"
    home.online = False
    assert home.state("lock.a") == "unknown"
    with pytest.raises(ConnectionError):
        await home.call("lock", "unlock", "lock.a")


async def test_models():
    model = FakeModel(Reply("hi"), ModelError("down"))
    assert (await model.chat([])).text == "hi"
    with pytest.raises(ModelError):
        await model.chat([])
    call = ToolCall("unlock", {})
    assert (await MaliciousModel(call).chat([])).tool_calls == (call,)
