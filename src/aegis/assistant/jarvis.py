"""Jarvis — the interactive AI assistant.

Wraps an :class:`Agent` configured with the assistant's tools and runs a simple
REPL in the terminal. Voice is an optional, clearly-isolated add-on enabled
with ``--voice`` (requires the ``[voice]`` extra).
"""

from __future__ import annotations

from aegis.agents.agent import Agent
from aegis.assistant.tools import build_assistant_tools
from aegis.llm.factory import build_llm
from aegis.utils.config import get_settings
from aegis.utils.logging import console, get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """\
You are Jarvis, a helpful personal assistant for a computer-science student.
You can scrape websites, manage local files, keep notes, and tell the time by
calling the tools available to you. Be concise and friendly.

Guidelines:
- When the user asks you to gather information from the web, use the
  scrape_websites tool with concrete URLs.
- Only call a tool when it is actually needed; otherwise just answer.
- After a tool runs, briefly tell the user what happened in plain language.
- Never invent file paths or scrape results; rely on tool outputs.
"""


def build_jarvis() -> Agent:
    """Construct a ready-to-use Jarvis agent."""
    llm = build_llm()
    registry = build_assistant_tools(llm)
    return Agent(llm=llm, registry=registry, system_prompt=SYSTEM_PROMPT, max_steps=8)


def run_repl(use_voice: bool = False) -> None:
    """Run Jarvis in an interactive loop until the user exits."""
    get_settings()  # ensure dirs exist
    agent = build_jarvis()

    voice = None
    if use_voice:
        try:
            from aegis.assistant.voice import VoiceIO

            voice = VoiceIO()
            console.print("[dim]Voice mode enabled. Speak after the prompt.[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Voice unavailable ({exc}); falling back to text.[/yellow]")

    console.print("[bold cyan]Jarvis is online.[/bold cyan] "
                  "Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            if voice:
                console.print("[dim]Listening...[/dim]")
                user_input = voice.listen()
                console.print(f"[bold green]You:[/bold green] {user_input}")
            else:
                user_input = console.input("[bold green]You:[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]Goodbye![/cyan]")
            break

        if user_input.strip().lower() in {"exit", "quit", "bye"}:
            console.print("[cyan]Goodbye![/cyan]")
            break
        if not user_input.strip():
            continue

        reply = agent.run(user_input)
        console.print(f"[bold magenta]Jarvis:[/bold magenta] {reply}\n")
        if voice:
            voice.speak(reply)
