"""Ollama provider."""
from __future__ import annotations

import base64
from typing import Any

import httpx

from .base import Message, ModelError, Reply, Tool, ToolCall


class OllamaProvider:
    def __init__(self, url: str, model: str, *, context: int = 8192, timeout: float = 120,
                 temperature: float = 0, keep_alive: str | int = "30m", think: bool | None = None,
                 max_output: int = 1024,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model = model
        self._options = {"num_ctx": context, "temperature": temperature,
                         "num_predict": max_output}
        self._keep_alive = keep_alive
        self._think = think
        # trust_env=False: proxy variables must not reroute household data (E1).
        self._client = httpx.AsyncClient(base_url=url, timeout=timeout, transport=transport,
                                         trust_env=False, follow_redirects=False)

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            response = await self._client.request(method, path, json=body)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as err:
            raise ModelError(
                f"Ollama returned HTTP {err.response.status_code}: {err.response.text[:200]}"
            ) from err
        except (httpx.HTTPError, ValueError) as err:
            raise ModelError(f"Ollama request failed: {type(err).__name__}") from err
        if not isinstance(data, dict):
            raise ModelError("Ollama returned an unexpected response")
        return data

    async def identity(self) -> str:
        data = await self._request("GET", "/api/tags")
        names = {self.model, f"{self.model}:latest"}
        for item in data.get("models") or []:
            if item.get("name") in names and item.get("digest"):
                return f"ollama:{item['name']}@{item['digest']}"
        raise ModelError(f"Model {self.model!r} is not installed")

    async def version(self) -> str:
        return str((await self._request("GET", "/api/version")).get("version"))

    async def installed(self) -> list[str]:
        data = await self._request("GET", "/api/tags")
        return [m["name"] for m in data.get("models") or []]

    async def details(self) -> dict[str, Any]:
        return await self._request("POST", "/api/show", {"model": self.model})

    async def loaded(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "/api/ps")).get("models") or []

    async def chat(self, messages: list[Message], tools: list[Tool] | None = None,
                   schema: dict[str, Any] | None = None) -> Reply:
        body: dict[str, Any] = {
            "model": self.model, "stream": False, "options": self._options,
            "keep_alive": self._keep_alive, "messages": [_encode(m) for m in messages],
        }
        if self._think is not None:
            body["think"] = self._think
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters,
            }} for t in tools]
        if schema:
            body["format"] = schema
        return _decode(await self._request("POST", "/api/chat", body))


def _encode(message: Message) -> dict[str, Any]:
    out: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.images:
        out["images"] = [base64.b64encode(i.data).decode() for i in message.images]
    if message.tool_calls:
        out["tool_calls"] = [{"function": {"name": c.name, "arguments": c.arguments}}
                             for c in message.tool_calls]
    if message.tool_name:
        out["tool_name"] = message.tool_name
    return out


def _decode(data: dict[str, Any]) -> Reply:
    message = data.get("message")
    if not isinstance(message, dict):
        raise ModelError("Ollama reply has no message")
    calls = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") if isinstance(raw, dict) else None
        if not isinstance(function, dict):
            raise ModelError("Malformed tool call")
        name, arguments = function.get("name"), function.get("arguments")
        # Never guess what a malformed request meant (F1).
        if not isinstance(name, str) or not name or not isinstance(arguments, dict):
            raise ModelError("Malformed tool call")
        calls.append(ToolCall(name, arguments))

    def seconds(key: str) -> float | None:
        value = data.get(key)
        return value / 1e9 if isinstance(value, (int, float)) else None

    return Reply(text=message.get("content") or "", tool_calls=tuple(calls),
                 prompt_tokens=data.get("prompt_eval_count"),
                 output_tokens=data.get("eval_count"),
                 prompt_seconds=seconds("prompt_eval_duration"),
                 output_seconds=seconds("eval_duration"),
                 truncated=data.get("done_reason") == "length")
