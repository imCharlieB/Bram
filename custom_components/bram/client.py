"""Encrypted connection to the BRAM Server, pinned to the paired certificate (G1)."""
from __future__ import annotations

import re

import aiohttp

_CODE = re.compile(r"bram1-([0-9a-f]{64})-([0-9a-f]{32})")


class InvalidCode(Exception):
    """The pairing code is malformed or was refused."""


class CannotConnect(Exception):
    """The server was unreachable or is not the paired server."""


def parse_code(code: str) -> tuple[str, str]:
    match = _CODE.fullmatch(code.strip())
    if match is None:
        raise InvalidCode
    return match[1], match[2]


def _base(host: str, port: int) -> str:
    host = host.strip()
    return f"https://[{host}]:{port}" if ":" in host else f"https://{host}:{port}"


def _pin(fingerprint: str) -> aiohttp.Fingerprint:
    return aiohttp.Fingerprint(bytes.fromhex(fingerprint))


async def pair(session: aiohttp.ClientSession, host: str, port: int, code: str) -> dict:
    """Redeem a one-time code. Returns the connection data to store."""
    fingerprint, secret = parse_code(code)
    try:
        async with session.post(
            f"{_base(host, port)}/pair", json={"secret": secret}, ssl=_pin(fingerprint),
            allow_redirects=False, timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status == 403:
                raise InvalidCode
            if response.status != 200:
                raise CannotConnect
            data = await response.json()
            return {"fingerprint": fingerprint, "house_id": data["house_id"],
                    "token": data["token"]}
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError) as err:
        raise CannotConnect from err


async def connect(session: aiohttp.ClientSession, host: str, port: int, fingerprint: str,
                  token: str) -> aiohttp.ClientWebSocketResponse:
    return await session.ws_connect(
        f"{_base(host, port)}/feed", ssl=_pin(fingerprint), max_msg_size=65536,
        headers={"Authorization": f"Bearer {token}"})
