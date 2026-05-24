"""Ollama backend — runs a model locally, free and offline.

Uses Ollama's HTTP API (``/api/chat``). Tool calling is supported by recent
Ollama versions for tool-capable models (e.g. llama3.1). If the local model
or server does not support tools, calls simply come back as plain text.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from aegis.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec
from aegis.utils.logging import get_logger

log = get_logger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, host: str) -> None:
        self._model = model
        self._host = host.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def _tools_payload(self, tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        tool_payload = self._tools_payload(tools)
        if tool_payload:
            payload["tools"] = tool_payload

        try:
            resp = httpx.post(f"{self._host}/api/chat", json=payload, timeout=120.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self._host}. "
                "Is it installed and running? See https://ollama.com"
            ) from exc

        data = resp.json()
        message = data.get("message", {})
        text = message.get("content", "") or ""

        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls", []) or []:
            fn = call.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(
                ToolCall(id=str(uuid.uuid4()), name=fn.get("name", ""), arguments=args)
            )

        return LLMResponse(text=text, tool_calls=tool_calls)
