"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

from aegis.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec


class FakeLLM(LLMProvider):
    """A scriptable fake LLM for deterministic tests.

    Hand it a list of LLMResponse objects; each ``chat`` call pops the next one.
    """

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    @property
    def name(self) -> str:
        return "fake"

    def chat(self, messages, tools=None, temperature=0.7) -> LLMResponse:
        self.calls.append(list(messages))
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(text="(no scripted response)", tool_calls=[])


@pytest.fixture
def fake_text_llm() -> FakeLLM:
    return FakeLLM([LLMResponse(text="hello from fake", tool_calls=[])])


@pytest.fixture(autouse=True)
def isolated_output(tmp_path, monkeypatch):
    """Point AEGIS output at a temp dir and reset the settings cache."""
    monkeypatch.setenv("AEGIS_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AEGIS_LLM_BACKEND", "ollama")
    # Reset the cached settings so the env override takes effect.
    import aegis.utils.config as cfg

    cfg._settings = None
    yield
    cfg._settings = None


# Re-export for convenience in tests.
__all__ = ["FakeLLM", "LLMResponse", "ToolCall", "ToolSpec"]
