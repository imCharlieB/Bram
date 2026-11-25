"""Reach the owner's local model without sending anything outside the network (E1)."""
from __future__ import annotations

import asyncio
import datetime
import ipaddress
from urllib.parse import urlsplit

from .models.base import ModelError
from .models.ollama import OllamaProvider


async def check_local(url: str, default_port: int = 11434) -> str:
    """Return the URL if every address it names is on a private network."""
    try:
        parts = urlsplit(url.strip())
        host, port = parts.hostname, parts.port or default_port
    except ValueError:
        raise ModelError("That is not a valid address") from None
    if (parts.scheme not in ("http", "https") or not host or parts.username or parts.password
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ModelError("Use an address like http://HOST:11434")
    try:
        found = await asyncio.get_running_loop().getaddrinfo(host, port)
    except OSError:
        raise ModelError("That address could not be found") from None
    for item in found:
        address = ipaddress.ip_address(item[4][0].split("%")[0])
        address = getattr(address, "ipv4_mapped", None) or address
        if not address.is_private or address.is_unspecified or address.is_link_local:
            raise ModelError("Only addresses on your own network can be used for now")
    shown = f"[{host}]" if ":" in host else host
    return f"{parts.scheme}://{shown}:{port}"


def _is_remote(item: dict) -> bool:
    """Ollama can list models that really run on someone else's computer."""
    tag = str(item.get("name", "")).rpartition(":")[2]
    return bool(item.get("remote_host") or item.get("remote_model")
                or tag == "cloud" or tag.endswith("-cloud"))


async def local_models(url: str) -> list[str]:
    provider = OllamaProvider(await check_local(url), "", timeout=10)
    try:
        return [m["name"] for m in await provider.tags() if not _is_remote(m)]
    finally:
        await provider.close()


async def open_model(url: str, model: str, context: int) -> OllamaProvider:
    """Open a model, keeping the settings it is already loaded with.

    Others may share this Ollama. A different context size or unload time would
    reload the model or change it for them.
    """
    url = await check_local(url)
    if model not in await local_models(url):
        raise ModelError("That model is not installed there, or does not run locally")
    probe = OllamaProvider(url, model, timeout=10)
    try:
        loaded = next((m for m in await probe.loaded() if m.get("name") == model), None)
    finally:
        await probe.close()
    keep: str | int = "30m"
    if loaded:
        context = loaded.get("context_length") or context
        keep = _keep_alive(loaded.get("expires_at"))
    return OllamaProvider(url, model, context=context, keep_alive=keep, think=False,
                          temperature=0.8, max_output=300, timeout=90)


def _keep_alive(expires_at: object) -> str | int:
    try:
        # Fractions of a second can be longer than Python accepts.
        year = int(str(expires_at)[:4])
    except ValueError:
        return "30m"
    return -1 if year > datetime.datetime.now(datetime.UTC).year + 1 else "30m"
