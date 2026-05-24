"""Tests for the tool registry and the agentic loop."""

from __future__ import annotations

from aegis.agents.agent import Agent
from aegis.agents.tools import ToolRegistry
from aegis.llm.base import LLMResponse, ToolCall
from tests.conftest import FakeLLM


def make_registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.register(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    )
    def add(a: float, b: float) -> float:
        return a + b

    return reg


def test_registry_calls_tool():
    reg = make_registry()
    assert reg.call("add", {"a": 2, "b": 3}) == "5"


def test_registry_unknown_tool():
    reg = make_registry()
    assert "unknown tool" in reg.call("nope", {})


def test_registry_reports_errors():
    reg = make_registry()
    # missing required argument -> TypeError surfaced as a string
    out = reg.call("add", {"a": 1})
    assert out.startswith("ERROR")


def test_agent_runs_tool_then_answers():
    reg = make_registry()
    # First the model asks to call `add`, then it returns a final answer.
    llm = FakeLLM(
        [
            LLMResponse(
                text="",
                tool_calls=[ToolCall(id="1", name="add", arguments={"a": 2, "b": 3})],
            ),
            LLMResponse(text="The answer is 5.", tool_calls=[]),
        ]
    )
    agent = Agent(llm=llm, registry=reg, system_prompt="be helpful", max_steps=4)
    result = agent.run("what is 2 + 3?")
    assert result == "The answer is 5."
    # The tool result must have been fed back into the conversation.
    assert any("[tool:add result]" in m.content for m in agent.messages)


def test_agent_respects_step_limit():
    reg = make_registry()
    # Model always asks for a tool, never finishes.
    looping = [
        LLMResponse(text="", tool_calls=[ToolCall(id="x", name="add", arguments={"a": 1, "b": 1})])
        for _ in range(10)
    ]
    agent = Agent(llm=FakeLLM(looping), registry=reg, system_prompt="x", max_steps=3)
    result = agent.run("loop forever")
    assert "step limit" in result.lower()
