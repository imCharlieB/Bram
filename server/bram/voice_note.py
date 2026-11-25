"""Turn a phone's voice note into sound Whisper understands."""
from __future__ import annotations

import io

import av

from .speech import MAX_AUDIO, RATE, SpeechError

MAX_FILE = 1_000_000


def decode(data: bytes) -> bytes:
    """Any common audio file to 16 kHz, 16-bit, mono. Runs in a thread."""
    if not data or len(data) > MAX_FILE:
        raise SpeechError("That recording is too long")
    out = bytearray()
    try:
        with av.open(io.BytesIO(data), format="ogg") as file:
            resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
            for frame in file.decode(audio=0):
                for part in resampler.resample(frame):
                    out += part.to_ndarray().tobytes()
                if len(out) > MAX_AUDIO:
                    raise SpeechError("Keep it under 30 seconds")
            for part in resampler.resample(None):
                out += part.to_ndarray().tobytes()
    except (av.error.FFmpegError, IndexError, ValueError):
        raise SpeechError("I could not read that recording") from None
    if not out:
        raise SpeechError("I could not read that recording")
    return bytes(out[:MAX_AUDIO])
