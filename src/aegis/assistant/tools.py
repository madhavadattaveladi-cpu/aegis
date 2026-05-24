"""Jarvis's toolbox.

These are the concrete capabilities the assistant agent can call: scraping the
web, managing local files, telling the time, and keeping notes. Each is a plain
Python function registered with a :class:`ToolRegistry`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from aegis.agents.tools import ToolRegistry
from aegis.assistant.web_tools import get_weather, web_search
from aegis.llm.base import LLMProvider, Message
from aegis.scraping.pipeline import run_crawl, run_scrape
from aegis.seriesscout.scout import scout as run_scout
from aegis.tracker.bookmarks import add_bookmark, load_bookmarks
from aegis.tracker.engine import check_updates
from aegis.utils.config import get_settings


def build_assistant_tools(llm: LLMProvider) -> ToolRegistry:
    """Create and populate the assistant's tool registry."""
    registry = ToolRegistry()
    settings = get_settings()
    notes_path = settings.output_dir / "jarvis_notes.txt"

    @registry.register(
        name="get_datetime",
        description="Get the current local date and time.",
        parameters={"type": "object", "properties": {}},
    )
    def get_datetime() -> str:
        return datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")

    @registry.register(
        name="scrape_websites",
        description=(
            "Scrape one or more web pages and save the results locally. "
            "Optionally extract structured data using a natural-language "
            "instruction."
        ),
        parameters={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of full http(s) URLs to scrape.",
                },
                "extract_instruction": {
                    "type": "string",
                    "description": "Optional plain-English description of what "
                    "fields to extract from each page.",
                },
                "run_name": {
                    "type": "string",
                    "description": "Short label for this scrape run.",
                },
            },
            "required": ["urls"],
        },
    )
    def scrape_websites(
        urls: list[str],
        extract_instruction: str | None = None,
        run_name: str = "scrape",
    ) -> dict:
        return run_scrape(
            urls,
            llm=llm if extract_instruction else None,
            extract_instruction=extract_instruction,
            run_name=run_name,
        )

    @registry.register(
        name="crawl_website",
        description=(
            "Crawl a website starting from seed URLs, following links up to a "
            "depth limit, and save a Markdown report with an AI-written summary."
        ),
        parameters={
            "type": "object",
            "properties": {
                "seeds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Starting URL(s) for the crawl.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "How many link-hops to follow (default 1).",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Hard cap on pages to fetch (default 20).",
                },
                "run_name": {"type": "string", "description": "Short label."},
            },
            "required": ["seeds"],
        },
    )
    def crawl_website(
        seeds: list[str],
        max_depth: int = 1,
        max_pages: int = 20,
        run_name: str = "crawl",
    ) -> dict:
        return run_crawl(
            seeds,
            max_depth=max_depth,
            max_pages=max_pages,
            llm=llm,
            run_name=run_name,
        )

    @registry.register(
        name="list_files",
        description="List files in a directory under the project's output folder.",
        parameters={
            "type": "object",
            "properties": {
                "subdir": {
                    "type": "string",
                    "description": "Subdirectory relative to the output dir. "
                    "Empty string means the output dir itself.",
                }
            },
        },
    )
    def list_files(subdir: str = "") -> list[str]:
        base = (settings.output_dir / subdir).resolve()
        out_root = settings.output_dir.resolve()
        # Safety: never escape the output directory.
        if out_root not in base.parents and base != out_root:
            return ["ERROR: path is outside the allowed output directory"]
        if not base.exists():
            return [f"(no such directory: {subdir})"]
        return sorted(p.name + ("/" if p.is_dir() else "") for p in base.iterdir())

    @registry.register(
        name="read_file",
        description="Read a UTF-8 text file from under the output directory.",
        parameters={
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "Path relative to the output directory.",
                }
            },
            "required": ["relative_path"],
        },
    )
    def read_file(relative_path: str) -> str:
        target = (settings.output_dir / relative_path).resolve()
        out_root = settings.output_dir.resolve()
        if out_root not in target.parents:
            return "ERROR: path is outside the allowed output directory"
        if not target.is_file():
            return f"ERROR: not a file: {relative_path}"
        return target.read_text(encoding="utf-8")[:8000]

    @registry.register(
        name="add_note",
        description="Append a note/reminder to the user's notes file.",
        parameters={
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "The note text to save."}
            },
            "required": ["note"],
        },
    )
    def add_note(note: str) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with notes_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {note}\n")
        return f"Saved note to {notes_path}"

    @registry.register(
        name="list_notes",
        description="Read back all saved notes/reminders.",
        parameters={"type": "object", "properties": {}},
    )
    def list_notes() -> str:
        if not notes_path.exists():
            return "No notes yet."
        return notes_path.read_text(encoding="utf-8")

    # ----- To-do list (JSON-backed, supports add / list / complete) -----
    todo_path = settings.output_dir / "jarvis_todo.json"

    def _load_todos() -> list[dict]:
        if not todo_path.exists():
            return []
        try:
            return json.loads(todo_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _save_todos(items: list[dict]) -> None:
        todo_path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    @registry.register(
        name="add_todo",
        description="Add a task to the to-do list.",
        parameters={
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        },
    )
    def add_todo(task: str) -> str:
        items = _load_todos()
        items.append({"id": len(items) + 1, "task": task, "done": False})
        _save_todos(items)
        return f"Added task #{len(items)}: {task}"

    @registry.register(
        name="list_todos",
        description="List all to-do tasks and whether they are done.",
        parameters={"type": "object", "properties": {}},
    )
    def list_todos() -> str:
        items = _load_todos()
        if not items:
            return "Your to-do list is empty."
        return "\n".join(
            f"#{i['id']} [{'x' if i['done'] else ' '}] {i['task']}" for i in items
        )

    @registry.register(
        name="complete_todo",
        description="Mark a to-do task as done by its id.",
        parameters={
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    )
    def complete_todo(task_id: int) -> str:
        items = _load_todos()
        for item in items:
            if item["id"] == task_id:
                item["done"] = True
                _save_todos(items)
                return f"Marked task #{task_id} as done."
        return f"No task with id {task_id}."

    # ----- Summarise a local text file using the LLM -----
    @registry.register(
        name="summarize_file",
        description="Read a text file from the output dir and summarise it with AI.",
        parameters={
            "type": "object",
            "properties": {"relative_path": {"type": "string"}},
            "required": ["relative_path"],
        },
    )
    def summarize_file(relative_path: str) -> str:
        target = (settings.output_dir / relative_path).resolve()
        out_root = settings.output_dir.resolve()
        if out_root not in target.parents:
            return "ERROR: path is outside the allowed output directory"
        if not target.is_file():
            return f"ERROR: not a file: {relative_path}"
        content = target.read_text(encoding="utf-8")[:6000]
        resp = llm.chat(
            [
                Message(role="system", content="Summarise the text in 3-5 sentences."),
                Message(role="user", content=content),
            ],
            temperature=0.3,
        )
        return resp.text.strip()

    # ----- Quick text statistics (no LLM needed) -----
    @registry.register(
        name="text_stats",
        description="Return word, line, and character counts for a piece of text.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )
    def text_stats(text: str) -> dict:
        return {
            "characters": len(text),
            "words": len(text.split()),
            "lines": len(text.splitlines()) or (1 if text else 0),
        }

    # ----- Live web search (keyless, needs internet) -----
    @registry.register(
        name="web_search",
        description="Search the web and return the top results (title, url, snippet).",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "description": "Default 5."},
            },
            "required": ["query"],
        },
    )
    def web_search_tool(query: str, max_results: int = 5) -> list[dict] | str:
        hits = web_search(query, max_results=max_results)
        if not hits:
            return "No results (the search service may be unreachable / you may be offline)."
        return [{"title": h.title, "url": h.url, "snippet": h.snippet} for h in hits]

    # ----- Current weather (keyless via Open-Meteo, needs internet) -----
    @registry.register(
        name="weather",
        description="Get current weather for a place name (city, etc).",
        parameters={
            "type": "object",
            "properties": {"place": {"type": "string"}},
            "required": ["place"],
        },
    )
    def weather_tool(place: str) -> dict:
        return get_weather(place)

    # ----- SeriesScout: discover new series matching a trait -----
    @registry.register(
        name="discover_series",
        description=(
            "Discover new manhwa/manga/manhua/novels matching a trait, e.g. "
            "'main protagonist uses a bow'. Scrapes a series site and filters "
            "with AI. Needs internet."
        ),
        parameters={
            "type": "object",
            "properties": {
                "trait": {
                    "type": "string",
                    "description": "The trait to look for, in plain English.",
                },
                "tag": {"type": "string", "description": "Optional site tag filter."},
                "genre": {"type": "string", "description": "Optional genre filter."},
                "pages": {"type": "integer", "description": "Listing pages to scan (default 1)."},
            },
            "required": ["trait"],
        },
    )
    def discover_series(
        trait: str, tag: str | None = None, genre: str | None = None, pages: int = 1
    ) -> dict:
        return run_scout(
            llm=llm, trait=trait, tag=tag, genre=genre, max_pages=pages,
            run_name="jarvis-scout",
        )

    # ----- Tracker: bookmark a series and check for new chapters -----
    @registry.register(
        name="track_series",
        description="Bookmark a comic/series by URL so AEGIS can watch it for new chapters.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "title": {"type": "string", "description": "Optional display title."},
            },
            "required": ["url"],
        },
    )
    def track_series(url: str, title: str | None = None) -> str:
        bm = add_bookmark(url, title=title or "")
        return f"Now tracking {bm.title or bm.url}."

    @registry.register(
        name="list_tracked",
        description="List all series currently being tracked for new chapters.",
        parameters={"type": "object", "properties": {}},
    )
    def list_tracked() -> str:
        bms = load_bookmarks()
        if not bms:
            return "You're not tracking any series yet."
        return "\n".join(
            f"- {bm.title or bm.url} (last seen: {bm.last_seen_chapter or '—'})"
            for bm in bms.values()
        )

    @registry.register(
        name="check_chapter_updates",
        description=(
            "Check all tracked series for new chapters and report what's new. "
            "Writes a whats_new.md report."
        ),
        parameters={"type": "object", "properties": {}},
    )
    def check_chapter_updates() -> str:
        summary = check_updates()
        return summary.get("report_text", summary.get("message", "Done."))

    return registry
