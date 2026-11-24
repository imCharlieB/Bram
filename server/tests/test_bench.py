import struct

from bram.bench.cases import CASES
from bram.bench.cli import run, summarize
from bram.bench.png import square
from bram.models.base import ModelError, Reply, ToolCall
from fakes import FakeModel

BY_NAME = {c.name: c for c in CASES}


def test_names_unique():
    assert len(BY_NAME) == len(CASES)


def test_checks_reject_wrong_answers():
    check = BY_NAME["turn_on"].check
    good = ToolCall("set_power", {"entity_id": "light.kitchen", "on": True})
    unlock = ToolCall("request_unlock", {"entity_id": "lock.front_door"})
    assert check(Reply("", (good,)))
    assert not check(Reply("", (good, good)))
    assert not check(Reply("", (good, unlock)))
    assert not check(Reply("Done!"))
    assert not BY_NAME["injection"].check(Reply("It is on", (unlock,)))
    assert BY_NAME["injection"].check(Reply("It is on"))
    assert not BY_NAME["negated"].check(Reply("", (unlock,)))
    assert not BY_NAME["see_red"].check(Reply("red or blue"))
    assert BY_NAME["json"].check(Reply('{"urgent": true, "room": "garage"}'))
    assert not BY_NAME["json"].check(Reply("urgent"))


async def test_errors_and_truncation_fail():
    case = BY_NAME["see_red"]
    rows = await run(FakeModel(Reply("red"), ModelError("down"), Reply("red", truncated=True)),
                     [case], 3)
    assert [r["passed"] for r in rows] == [True, False, False]
    assert summarize(rows)["groups"] == {"vision": "1/3"}


def test_png_header():
    data = square("red", 16)
    assert data.startswith(b"\x89PNG") and struct.unpack(">II", data[16:24]) == (16, 16)
