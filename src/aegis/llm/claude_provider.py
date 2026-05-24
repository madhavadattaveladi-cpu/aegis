"""Claude backend — uses the Anthropic API.

Only imported/instantiated when ``AEGIS_LLM_BACKEND=claude``. Requires the
optional dependency ``anthropic`` (``pip install -e ".[claude]"``) and an API
key in ``AEGIS_ANTHROPIC_API_KEY``.

Model strings verified current as of May 2026: ``claude-sonnet-4-6`` is the
recommended default; ``claude-opus-4-7`` for the hardest reasoning.
"""

from __future__ import annotations

from typing import Any

from aegis.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec
from aegis.utils.logging import get_logger

log = get_logger(__name__)


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "AEGIS_ANTHROPIC_API_KEY is empty. Set it in your .env to use the "
                "Claude backend, or switch AEGIS_LLM_BACKEND=ollama."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                'The Claude backend needs the anthropic package. '
                'Install it with:  pip install -e ".[claude]"'
            ) from exc

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"claude:{self._model}"

    @staticmethod
    def _split_system(messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
        """Anthropic takes the system prompt as a separate argument."""
        system_parts = [m.content for m in messages if m.role == "system"]
        convo = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        return "\n\n".join(system_parts), convo

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        system, convo = self._split_system(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 2048,
            "temperature": temperature,
            "messages": convo,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        resp = self._client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)
