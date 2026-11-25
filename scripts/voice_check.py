"""Speak a sentence with Piper, then check that Whisper hears it."""
import array
import asyncio
import io
import sys
import time
import wave

from bram.speech import RATE, SpeechError, synthesize, transcribe

TEXT = "Please turn on the kitchen light."


def to_16k(wav: bytes) -> bytes:
    with wave.open(io.BytesIO(wav)) as file:
        rate = file.getframerate()
        samples = array.array("h", file.readframes(file.getnframes()))
    step = rate / RATE
    out = array.array("h", (samples[int(i * step)] for i in range(int(len(samples) / step))))
    return out.tobytes()


async def main(hear: str, speak: str) -> int:
    for _ in range(60):  # models are downloaded on first start
        try:
            start = time.time()
            wav = await synthesize(speak, TEXT)
            spoke = time.time() - start
            start = time.time()
            heard = await transcribe(hear, to_16k(wav))
            print(f"Spoke in {spoke:.1f}s, heard in {time.time() - start:.1f}s: {heard!r}")
            return 0 if "kitchen light" in heard.lower() else 1
        except SpeechError as err:
            print("Waiting:", err)
            await asyncio.sleep(5)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(*sys.argv[1:3])))
