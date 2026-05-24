"""A registry that exposes plain Python functions to the LLM as tools.

Each tool has a name, description, JSON-Schema for its arguments, and a Python
callable. The agent uses this registry to (a) tell the model what tools exist
and (b) actually execute a tool the model chooses to call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from aegis.llm.base import ToolSpec
from aegis.utils.logging import get_logger

log = get_logger(__name__)

ToolFn = Callable[..., Any]


@dataclass
class Tool:
    spec: ToolSpec
    fn: ToolFn


class ToolRegistry:
    """Holds the set of tools available to an agent."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self, name: str, description: str, parameters: dict[str, Any]
    ) -> Callable[[ToolFn], ToolFn]:
        """Decorator that registers a function as a tool.

        Example::

            @registry.register(
                name="add",
                description="Add two numbers",
                parameters={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
            )
            def add(a, b):
                return a + b
        """

        def decorator(fn: ToolFn) -> ToolFn:
            self._tools[name] = Tool(
                spec=ToolSpec(name=name, description=description, parameters=parameters),
                fn=fn,
            )
            return fn

        return decorator

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a registered tool and return its result as a string."""
        tool = self._tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            result = tool.fn(**arguments)
        except Exception as exc:  # noqa: BLE001 - report errors back to the model
            log.warning("Tool %s raised: %s", name, exc)
            return f"ERROR while running {name}: {exc}"
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except TypeError:
            return str(result)
