import asyncio
import io
import json
import wave

import pytest

from bram.settings import Settings
from bram.speech import (
    MAX_AUDIO,
    Speech,
    SpeechError,
    check_address,
    describe,
    find,
    synthesize,
    transcribe,
)


def event(kind, data=None, payload=b"", split=False):
    header, extra = {"type": kind}, b""
    if split:
        extra = json.dumps(data or {}).encode()
        header["data_length"] = len(extra)
    else:
        header["data"] = data or {}
    if payload:
        header["payload_length"] = len(payload)
    return json.dumps(header).encode() + b"\n" + extra + payload


class Fake:
    """A Wyoming server that answers once it has seen a given event."""

    def __init__(self, after, answer):
        self.after, self.answer, self.seen = after, answer, []

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        return self, f"127.0.0.1:{self.server.sockets[0].getsockname()[1]}"

    async def __aexit__(self, *args):
        self.server.close()

    async def handle(self, reader, writer):
        try:
            while line := await reader.readline():
                header = json.loads(line)
                payload = await reader.readexactly(header.get("payload_length", 0))
                self.seen.append((header["type"], header.get("data"), payload))
                if header["type"] == self.after:
                    writer.write(self.answer)
                    await writer.drain()
                    break
        finally:
            writer.close()


SHAPE = {"rate": 22050, "width": 2, "channels": 1}


async def test_hearing():
    answer = event("transcript", {"text": "  turn on\nthe light "}, split=True)
    async with Fake("audio-stop", answer) as (fake, address):
        assert await transcribe(address, b"\x01\x00" * 40000) == "turn on the light"
    kinds = [s[0] for s in fake.seen]
    assert kinds[:2] == ["transcribe", "audio-start"] and kinds[-1] == "audio-stop"
    assert b"".join(s[2] for s in fake.seen) == b"\x01\x00" * 40000


async def test_speaking():
    answer = (event("audio-start", SHAPE) + event("audio-chunk", SHAPE, b"\x00\x01" * 10)
              + event("audio-chunk", SHAPE, b"\x00\x02" * 5) + event("audio-stop"))
    async with Fake("synthesize", answer) as (fake, address):
        wav = await synthesize(address, "Good evening", "en_US-x-medium")
    assert fake.seen[0][1] == {"text": "Good evening", "voice": {"name": "en_US-x-medium"}}
    with wave.open(io.BytesIO(wav)) as file:
        assert (file.getframerate(), file.getnframes()) == (22050, 15)


@pytest.mark.parametrize("answer", [
    b"", b"junk\n", b"[]\n", b'{"type": 5}\n', event("error"),
    b'{"type": "transcript", "payload_length": 99999999999}\n',
    b'{"type": "transcript", "payload_length": -1}\n',
    b'{"type": "transcript", "data_length": 50}\n{}', event("transcript", {"text": 5})])
async def test_bad_hearing_server(answer):
    async with Fake("audio-stop", answer) as (_, address):
        with pytest.raises(SpeechError):
            await transcribe(address, b"\x00\x00")


@pytest.mark.parametrize("answer", [
    event("audio-stop"), event("audio-chunk", SHAPE, b"x"),
    event("audio-start", {**SHAPE, "rate": 10**9}), event("audio-start", {}),
    event("audio-start", SHAPE) + event("audio-stop")])
async def test_bad_speaking_server(answer):
    async with Fake("synthesize", answer) as (_, address):
        with pytest.raises(SpeechError):
            await synthesize(address, "hi")


INFO = {"tts": [{"name": "piper", "voices": [
    {"name": "en_US-a-medium", "languages": ["en_US"], "installed": True},
    {"name": "de_DE-b-low", "languages": ["de_DE"], "installed": False},
    {"name": "../evil", "languages": ["x"]}, "junk"]}], "asr": []}


async def test_describe():
    async with Fake("describe", event("info", INFO)) as (_, address):
        found = await describe("speak", address)
        assert [v["name"] for v in found["voices"]] == ["en_US-a-medium", "de_DE-b-low"]
        assert found["voices"][0]["ready"] and not found["voices"][1]["ready"]
    async with Fake("describe", event("info", INFO)) as (_, address):
        assert await describe("hear", address) is None
    for junk in (b"", b"junk\n", event("info", {"tts": "x"}), event("other") * 9):
        async with Fake("describe", junk) as (_, address):
            assert await describe("speak", address) is None
    for address in ("127.0.0.1:9", "8.8.8.8:10200", "http://x"):
        assert await describe("speak", address) is None


async def test_find(monkeypatch):
    async def fake(kind, address):
        if (kind, address) == ("hear", "127.0.0.1:10300"):
            return {"name": "whisper", "voices": []}
        return None

    monkeypatch.setattr("bram.speech.describe", fake)
    assert await find("127.0.0.1") == {
        "hear": {"address": "127.0.0.1:10300", "name": "whisper", "voices": []}, "speak": None}


async def test_nothing_listening():
    with pytest.raises(SpeechError):
        await transcribe("127.0.0.1:9", b"\x00\x00")


@pytest.mark.parametrize("audio", [b"", b"\x00", b"\x00" * (MAX_AUDIO + 2)])
async def test_audio_limits(audio):
    with pytest.raises(SpeechError):
        await transcribe("127.0.0.1:9", audio)


@pytest.mark.parametrize("address", ["8.8.8.8:10300", "", None, "http://127.0.0.1", "a b", "x/y:1",
                                     "169.254.169.254:80"])
async def test_only_local_addresses(address):
    with pytest.raises(SpeechError):
        await check_address("hear", address)


async def test_default_ports():
    assert await check_address("hear", "127.0.0.1") == "127.0.0.1:10300"
    assert await check_address("speak", "tcp://127.0.0.1") == "127.0.0.1:10200"


async def test_settings():
    settings = Settings(":memory:")
    speech = Speech(settings)
    with pytest.raises(SpeechError, match="not set up"):
        await speech.hear(b"\x00\x00")
    with pytest.raises(SpeechError, match="not set up"):
        await speech.speak("hi")
    with pytest.raises(SpeechError):
        await speech.save({"speak": "127.0.0.1", "voice": "../x"})
    await speech.save({"hear": "127.0.0.1", "speak": "", "voice": "en_US-a-medium"})
    assert speech.config() == {"hear": "127.0.0.1:10300", "speak": "", "voice": "en_US-a-medium"}
    settings.close()
