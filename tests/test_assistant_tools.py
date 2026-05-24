"""Tests for the assistant's tools (the new breadth features)."""

from __future__ import annotations

from aegis.assistant.tools import build_assistant_tools
from aegis.llm.base import LLMResponse
from tests.conftest import FakeLLM


def _registry(responses=None):
    return build_assistant_tools(FakeLLM(responses or []))


def test_all_tools_registered():
    reg = _registry()
    names = {s.name for s in reg.specs()}
    expected = {
        "get_datetime", "scrape_websites", "crawl_website", "list_files",
        "read_file", "add_note", "list_notes", "add_todo", "list_todos",
        "complete_todo", "summarize_file", "text_stats",
    }
    assert expected <= names


def test_todo_lifecycle():
    reg = _registry()
    assert reg.call("list_todos", {}) == "Your to-do list is empty."
    reg.call("add_todo", {"task": "write README"})
    reg.call("add_todo", {"task": "push to GitHub"})
    listing = reg.call("list_todos", {})
    assert "write README" in listing and "push to GitHub" in listing
    reg.call("complete_todo", {"task_id": 1})
    listing2 = reg.call("list_todos", {})
    assert "[x] write README" in listing2
    # completing a non-existent id is handled gracefully
    assert "No task" in reg.call("complete_todo", {"task_id": 99})


def test_text_stats():
    reg = _registry()
    out = reg.call("text_stats", {"text": "hello world\nsecond line"})
    assert '"words": 4' in out or "'words': 4" in out


def test_summarize_file_path_guard():
    reg = _registry([LLMResponse(text="summary", tool_calls=[])])
    # path escaping the output dir must be refused
    assert "outside" in reg.call("summarize_file", {"relative_path": "../../etc/passwd"})
