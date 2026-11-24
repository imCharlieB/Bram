"""The one interface every model provider implements.

A provider returns text and tool *requests*. It never executes anything (A1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ModelError(Exception):
    """The model was unreachable or returned something unusable."""


@dataclass(frozen=True)
class Image:
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: str  # system | user | assistant | tool
    content: str
    images: tuple[Image, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class Reply:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    prompt_seconds: float | None = None
    output_seconds: float | None = None
    truncated: bool = False


class ModelProvider(Protocol):
    async def identity(self) -> str:
        """Stable ID of the exact model weights. Changes when the model does (F7)."""

    async def chat(self, messages: list[Message], tools: list[Tool] | None = None,
                   schema: dict[str, Any] | None = None) -> Reply: ...
