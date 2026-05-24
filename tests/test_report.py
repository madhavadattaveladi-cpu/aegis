"""Tests for Markdown report generation and AI summarisation."""

from __future__ import annotations

from aegis.llm.base import LLMResponse
from aegis.scraping.parser import ParsedPage
from aegis.scraping.report import ai_summarize, build_markdown_report
from tests.conftest import FakeLLM


def _pages():
    return [
        ParsedPage(url="https://a.com", title="Alpha", text="alpha body", links=["x"]),
        ParsedPage(url="https://b.com", title="Beta", text="beta body", links=[]),
    ]


def test_markdown_report_contains_sections():
    md = build_markdown_report(
        "My Report",
        _pages(),
        summary="A short summary.",
        stats={"pages_collected": 2},
    )
    assert "# My Report" in md
    assert "## Summary statistics" in md
    assert "## AI summary" in md
    assert "Alpha" in md and "Beta" in md
    assert "pages_collected" in md


def test_markdown_report_without_summary():
    md = build_markdown_report("R", _pages())
    assert "## AI summary" not in md
    assert "## Pages" in md


def test_ai_summarize_calls_llm():
    llm = FakeLLM([LLMResponse(text="These pages discuss alpha and beta.", tool_calls=[])])
    out = ai_summarize(llm, _pages())
    assert "alpha" in out.lower()


def test_ai_summarize_empty_pages():
    llm = FakeLLM([])
    out = ai_summarize(llm, [])
    assert "nothing to summarise" in out.lower()
