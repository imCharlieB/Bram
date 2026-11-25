"""Authenticator app codes (RFC 6238) and one-time recovery codes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from typing import Any
from urllib.parse import quote

PERIOD, DIGITS = 30, 6
DRIFT = 1  # steps either side, for clocks that disagree
RECOVERY = 8


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(base64.b32decode(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    at = digest[-1] & 15
    number = struct.unpack(">I", digest[at:at + 4])[0] & 0x7FFFFFFF
    return f"{number % 10**DIGITS:0{DIGITS}}"


def link(secret: str, user: str) -> str:
    return (f"otpauth://totp/BRAM:{quote(user, safe='')}?secret={secret}&issuer=BRAM"
            f"&digits={DIGITS}&period={PERIOD}")


def matching_step(secret: str, code: object, now: float, last: int) -> int | None:
    """The step a code belongs to. A code works once: steps already used are refused."""
    text = "".join(code.split()) if isinstance(code, str) else ""
    if len(text) != DIGITS or not text.isascii() or not text.isdigit():
        return None
    here = int(now // PERIOD)
    found = None
    for step in range(here - DRIFT, here + DRIFT + 1):
        if hmac.compare_digest(code_at(secret, step), text) and step > last:
            found = step
    return found


def new_recovery() -> list[str]:
    return [base64.b32encode(secrets.token_bytes(10)).decode().lower() for _ in range(RECOVERY)]


def recovery_hash(code: object) -> str:
    text = "".join(code.split()).lower() if isinstance(code, str) else ""
    return hashlib.sha256(text.encode()).hexdigest()


def check(record: dict[str, Any], code: object, now: float) -> dict[str, Any] | None:
    """The record to keep if the code is right, with that code used up. None if it is wrong."""
    step = matching_step(record["secret"], code, now, record["last"])
    if step is not None:
        return {**record, "last": step}
    hashed = recovery_hash(code)
    if any(hmac.compare_digest(hashed, h) for h in record["recovery"]):
        return {**record, "recovery": [h for h in record["recovery"] if h != hashed]}
    return None
