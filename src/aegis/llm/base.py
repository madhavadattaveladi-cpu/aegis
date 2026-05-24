"""LLM provider abstraction.

Defines a single :class:`LLMProvider` interface so the rest of the app never
cares whether it is talking to a local Ollama model or the Claude API.
Swapping backends is a one-line config change.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    """A single chat message."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


@dataclass
class ToolSpec:
    """Description of a tool the model may call.

    ``parameters`` is a JSON-Schema object describing the arguments.
    """

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    """A request from the model to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalised response from any backend."""

    text: str
    tool_calls: list[ToolCall]

    @property
    def wants_tool(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(abc.ABC):
    """Common interface every backend implements."""

    @abc.abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a conversation and return the model's reply.

        If ``tools`` are supplied and the model decides to call one, the
        returned :class:`LLMResponse` will contain ``tool_calls``.
        """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable backend name for logging."""
