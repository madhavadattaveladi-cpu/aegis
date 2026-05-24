"""The agentic loop.

An :class:`Agent` wraps an LLM provider plus a tool registry and runs the
classic agent cycle:

    1. Send the conversation (and available tools) to the model.
    2. If the model asks to call a tool, run it and feed the result back.
    3. Repeat until the model produces a final text answer (or we hit a step cap).

This is the heart of "agentic AI": the model decides which tools to use and in
what order, rather than following a hard-coded script.
"""

from __future__ import annotations

from aegis.agents.tools import ToolRegistry
from aegis.llm.base import LLMProvider, Message
from aegis.utils.logging import get_logger

log = get_logger(__name__)


class Agent:
    def __init__(
        self,
        llm: LLMProvider,
        registry: ToolRegistry,
        system_prompt: str,
        max_steps: int = 8,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_steps = max_steps
        self.messages: list[Message] = [Message(role="system", content=system_prompt)]

    def run(self, user_input: str) -> str:
        """Run the agent on a single user request and return the final answer."""
        self.messages.append(Message(role="user", content=user_input))
        tools = self.registry.specs()

        for step in range(1, self.max_steps + 1):
            response = self.llm.chat(self.messages, tools=tools)

            if not response.wants_tool:
                # Final answer.
                self.messages.append(Message(role="assistant", content=response.text))
                return response.text

            # The model asked to use tools. Run each, then loop again.
            if response.text:
                self.messages.append(Message(role="assistant", content=response.text))

            for call in response.tool_calls:
                log.info("Step %d: calling tool %s(%s)", step, call.name, call.arguments)
                result = self.registry.call(call.name, call.arguments)
                # Feed the observation back as context for the next step.
                self.messages.append(
                    Message(
                        role="user",
                        content=f"[tool:{call.name} result]\n{result}",
                    )
                )

        return (
            "I reached my step limit without finishing. "
            "Try narrowing the request or raising max_steps."
        )
