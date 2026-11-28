"""Cloud models, for owners without one of their own. Off until the owner chooses one (E1).

Nothing here is used unless the owner picked a provider and entered its key; there is no
fallback from the owner's own model to the cloud, or back. Camera pictures go to a cloud model
only with their own switch (E2).
"""
from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from .base import Message, ModelError, Reply, Tool

PROVIDERS = {
    "openai": ("OpenAI", "https://api.openai.com/v1"),
    "anthropic": ("Anthropic", "https://api.anthropic.com/v1"),
    "gemini": ("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "other": ("Another OpenAI-compatible service", ""),
}
ANTHROPIC_VERSION = "2023-06-01"


def _client(url: str, headers: dict[str, str], timeout: float,
            transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    # trust_env=False: proxy variables must not reroute household data (E1).
    return httpx.AsyncClient(base_url=url, headers=headers, timeout=timeout, transport=transport,
                             trust_env=False, follow_redirects=False)


async def _post(client: httpx.AsyncClient, path: str, body: dict, who: str) -> dict:
    try:
        response = await client.post(path, json=body)
    except httpx.HTTPError as err:
        raise ModelError(f"{who} could not be reached") from err
    return _answer(response, who)


def _answer(response: httpx.Response, who: str) -> dict:
    if response.status_code in (401, 403):
        raise ModelError(f"{who} did not accept the API key")
    if response.status_code == 429:
        raise ModelError(f"{who} says too many requests, or the account is out of credit")
    if response.status_code >= 400:
        raise ModelError(f"{who} returned error {response.status_code}")
    try:
        data = response.json()
    except ValueError as err:
        raise ModelError(f"{who} returned something unexpected") from err
    if not isinstance(data, dict):
        raise ModelError(f"{who} returned something unexpected")
    return data


class OpenAICompatible:
    """OpenAI's chat completions, which Gemini and many others also speak."""

    def __init__(self, url: str, key: str, model: str, *, max_output: int = 600,
                 timeout: float = 90, who: str = "The cloud model",
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model, self._max, self._who = model, max_output, who
        self._client = _client(url.rstrip("/"), {"Authorization": f"Bearer {key}"}, timeout,
                               transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def models(self) -> list[str]:
        try:
            data = _answer(await self._client.get("/models"), self._who)
        except httpx.HTTPError as err:
            raise ModelError(f"{self._who} could not be reached") from err
        names = [str(m.get("id", "")).removeprefix("models/") for m in data.get("data", [])
                 if isinstance(m, dict)]
        return sorted(n for n in names if n)

    async def chat(self, messages: list[Message], tools: list[Tool] | None = None,
                   schema: dict[str, Any] | None = None) -> Reply:
        body: dict[str, Any] = {"model": self.model, "max_tokens": self._max,
                                "messages": [_openai(m) for m in messages]}
        if schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "answer", "schema": schema}}
        data = await _post(self._client, "/chat/completions", body, self._who)
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as err:
            raise ModelError(f"{self._who} returned no answer") from err
        return Reply(str(text), truncated=choice.get("finish_reason") == "length")


def _openai(message: Message) -> dict[str, Any]:
    if not message.images:
        return {"role": message.role, "content": message.content}
    parts: list[dict[str, Any]] = [{"type": "text", "text": message.content}]
    parts += [{"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64," + base64.b64encode(i.data).decode()}}
        for i in message.images]
    return {"role": message.role, "content": parts}


class Anthropic:
    def __init__(self, key: str, model: str, *, max_output: int = 600, timeout: float = 90,
                 url: str = PROVIDERS["anthropic"][1],
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model, self._max = model, max_output
        self._client = _client(url, {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION},
                               timeout, transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def models(self) -> list[str]:
        try:
            data = _answer(await self._client.get("/models"), "Anthropic")
        except httpx.HTTPError as err:
            raise ModelError("Anthropic could not be reached") from err
        return sorted(str(m.get("id")) for m in data.get("data", []) if isinstance(m, dict))

    async def chat(self, messages: list[Message], tools: list[Tool] | None = None,
                   schema: dict[str, Any] | None = None) -> Reply:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        if schema:
            system += ("\n\nReply with only a JSON object matching this schema:\n"
                       + json.dumps(schema))
        talk = [_anthropic(m) for m in messages if m.role in ("user", "assistant")]
        body = {"model": self.model, "max_tokens": self._max, "system": system,
                "messages": talk}
        data = await _post(self._client, "/messages", body, "Anthropic")
        text = "".join(part.get("text", "") for part in data.get("content", [])
                       if isinstance(part, dict) and part.get("type") == "text")
        if not text and data.get("stop_reason") != "max_tokens":
            raise ModelError("Anthropic returned no answer")
        return Reply(text, truncated=data.get("stop_reason") == "max_tokens")


def _anthropic(message: Message) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg",
        "data": base64.b64encode(i.data).decode()}} for i in message.images]
    parts.append({"type": "text", "text": message.content})
    return {"role": message.role, "content": parts}


def provider(choice: dict[str, Any], *, max_output: int = 600,
             transport: httpx.AsyncBaseTransport | None = None
             ) -> OpenAICompatible | Anthropic:
    """The provider the owner chose, with its key. Never chosen by anything else (E1)."""
    kind, key, model = choice.get("provider"), choice.get("key", ""), choice.get("model", "")
    if kind not in PROVIDERS or not key:
        raise ModelError("Choose a cloud provider and enter its key under Settings, Model")
    if kind == "anthropic":
        return Anthropic(key, model, max_output=max_output, transport=transport)
    url = choice.get("url", "") if kind == "other" else PROVIDERS[kind][1]
    return OpenAICompatible(url, key, model, max_output=max_output, who=PROVIDERS[kind][0],
                            transport=transport)
