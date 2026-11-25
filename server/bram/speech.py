"""Hearing and speaking through Wyoming servers (Whisper, Piper) on the owner's network.

Audio is held in memory only while it is being handled (E10). What is heard is treated
exactly like typed text and can never approve anything (A6).
"""
from __future__ import annotations

import asyncio
import io
import json
import wave
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from .local_model import check_local
from .models.base import ModelError
from .settings import Settings

RATE = 16000
MAX_SECONDS = 30
MAX_AUDIO = RATE * 2 * MAX_SECONDS
MAX_SPEAK = 1500
MAX_REPLY = 20_000_000
MAX_EVENT = 4_000_000
TIMEOUT = 60
PORTS = {"hear": 10300, "speak": 10200}


class SpeechError(Exception):
    """Safe to show."""


async def check_address(kind: str, address: object) -> str:
    """Clean HOST:PORT, only on the owner's own network."""
    if not isinstance(address, str) or not address.strip():
        raise SpeechError("Enter an address like HOST:PORT")
    text = address.strip().removeprefix("tcp://")
    try:
        url = await check_local(f"http://{text}", PORTS[kind])
    except ModelError as err:
        raise SpeechError(str(err)) from None
    return url.removeprefix("http://")


async def _write(writer: asyncio.StreamWriter, kind: str, data: dict | None = None,
                 payload: bytes = b"") -> None:
    header: dict = {"type": kind, "data": data or {}}
    if payload:
        header["payload_length"] = len(payload)
    writer.write(json.dumps(header).encode() + b"\n" + payload)
    await writer.drain()


async def _read(reader: asyncio.StreamReader) -> tuple[str, dict, bytes]:
    line = await reader.readline()
    if not line:
        raise SpeechError("The speech server closed the connection")
    header = json.loads(line)
    if not isinstance(header, dict) or not isinstance(header.get("type"), str):
        raise ValueError("bad event")
    data = header.get("data") or {}
    sizes = [header.get(k) or 0 for k in ("data_length", "payload_length")]
    if not isinstance(data, dict) or any(
            not isinstance(n, int) or not 0 <= n <= MAX_EVENT for n in sizes):
        raise ValueError("bad event")
    if sizes[0]:
        more = json.loads(await reader.readexactly(sizes[0]))
        if not isinstance(more, dict):
            raise ValueError("bad event")
        data = {**data, **more}
    return header["type"], data, await reader.readexactly(sizes[1]) if sizes[1] else b""


@asynccontextmanager
async def _connect(kind: str, address: str) -> AsyncIterator[
        tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    address = await check_address(kind, address)
    host, _, port = address.rpartition(":")
    writer = None
    try:
        async with asyncio.timeout(TIMEOUT):
            reader, writer = await asyncio.open_connection(
                host.strip("[]"), int(port), limit=MAX_EVENT)
            yield reader, writer
    except TimeoutError:
        raise SpeechError("The speech server took too long") from None
    except (OSError, asyncio.IncompleteReadError):
        raise SpeechError("The speech server did not answer") from None
    except ValueError:
        raise SpeechError("That does not look like a Wyoming speech server") from None
    finally:
        if writer is not None:
            writer.close()


async def transcribe(address: str, pcm: bytes) -> str:
    """16 kHz, 16-bit, mono sound to text."""
    if not pcm or len(pcm) > MAX_AUDIO or len(pcm) % 2:
        raise SpeechError(f"Record up to {MAX_SECONDS} seconds")
    shape = {"rate": RATE, "width": 2, "channels": 1}
    async with _connect("hear", address) as (reader, writer):
        await _write(writer, "transcribe", {})
        await _write(writer, "audio-start", shape)
        for start in range(0, len(pcm), 32000):
            await _write(writer, "audio-chunk", shape, pcm[start:start + 32000])
        await _write(writer, "audio-stop", {})
        while True:
            kind, data, _ = await _read(reader)
            if kind == "transcript":
                text = data.get("text")
                if not isinstance(text, str):
                    raise ValueError("bad transcript")
                return " ".join(text.split())[:2000]
            if kind == "error":
                raise SpeechError("The speech server reported an error")


async def synthesize(address: str, text: str, voice: str = "") -> bytes:
    """Text to a WAV file."""
    text = " ".join(text.split())[:MAX_SPEAK]
    if not text:
        raise SpeechError("There is nothing to say")
    request: dict = {"text": text}
    if voice:
        request["voice"] = {"name": voice}
    out, shape, size = io.BytesIO(), None, 0
    frames: list[bytes] = []
    async with _connect("speak", address) as (reader, writer):
        await _write(writer, "synthesize", request)
        while True:
            kind, data, payload = await _read(reader)
            if kind == "audio-start":
                shape = tuple(data.get(k) for k in ("channels", "width", "rate"))
                if (any(not isinstance(v, int) for v in shape) or shape[0] not in (1, 2)
                        or shape[1] not in (1, 2, 4) or not 8000 <= shape[2] <= 48000):
                    raise ValueError("bad audio")
            elif kind == "audio-chunk":
                size += len(payload)
                if shape is None or size > MAX_REPLY:
                    raise ValueError("bad audio")
                frames.append(payload)
            elif kind == "audio-stop":
                break
            elif kind == "error":
                raise SpeechError("The speech server reported an error")
    if shape is None or not frames:
        raise SpeechError("The speech server sent no sound")
    with wave.open(out, "wb") as file:
        file.setnchannels(shape[0])
        file.setsampwidth(shape[1])
        file.setframerate(shape[2])
        file.writeframes(b"".join(frames))
    return out.getvalue()


class Speech:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()

    def config(self) -> dict:
        c = self._settings.channel("speech")
        return {"hear": c.get("hear", ""), "speak": c.get("speak", ""),
                "voice": c.get("voice", "")}

    async def save(self, body: dict) -> None:
        values = {k: await check_address(k, body[k]) if body.get(k) else "" for k in PORTS}
        voice = body.get("voice") or ""
        if not isinstance(voice, str) or len(voice) > 80 or not all(
                c.isalnum() or c in "_-." for c in voice):
            raise SpeechError("That voice name is not valid")
        self._settings.update_channel("speech", {**values, "voice": voice})

    async def hear(self, pcm: bytes) -> str:
        address = self.config()["hear"]
        if not address:
            raise SpeechError("Hearing is not set up")
        async with self._lock:
            return await transcribe(address, pcm)

    async def speak(self, text: str) -> bytes:
        c = self.config()
        if not c["speak"]:
            raise SpeechError("Speaking is not set up")
        async with self._lock:
            return await synthesize(c["speak"], text, c["voice"])
