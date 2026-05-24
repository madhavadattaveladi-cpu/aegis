"""Reporting: turn scrape/crawl output into a readable Markdown report, and
optionally have the LLM write a natural-language summary of what was found.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aegis.llm.base import LLMProvider, Message
from aegis.scraping.parser import ParsedPage
from aegis.utils.logging import get_logger

log = get_logger(__name__)

_SUMMARY_SYSTEM = (
    "You are a research assistant. Given titles and short excerpts from web "
    "pages, write a concise, neutral summary (4-6 sentences) of the main themes "
    "and notable points. Do not invent facts not present in the excerpts."
)


def ai_summarize(llm: LLMProvider, pages: list[ParsedPage], max_pages: int = 15) -> str:
    """Ask the LLM to summarise a set of crawled pages."""
    if not pages:
        return "No pages were collected, so there is nothing to summarise."
    lines: list[str] = []
    for p in pages[:max_pages]:
        excerpt = p.text[:400]
        lines.append(f"- TITLE: {p.title or '(untitled)'}\n  URL: {p.url}\n  EXCERPT: {excerpt}")
    prompt = "Summarise these pages:\n\n" + "\n".join(lines)
    resp = llm.chat(
        [Message(role="system", content=_SUMMARY_SYSTEM),
         Message(role="user", content=prompt)],
        temperature=0.3,
    )
    return resp.text.strip()


def build_markdown_report(
    title: str,
    pages: list[ParsedPage],
    *,
    summary: str | None = None,
    stats: dict[str, Any] | None = None,
) -> str:
    """Render a Markdown report string from crawl/scrape results."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out: list[str] = [f"# {title}", "", f"_Generated {now}_", ""]

    if stats:
        out.append("## Summary statistics")
        out.append("")
        for key, value in stats.items():
            out.append(f"- **{key}**: {value}")
        out.append("")

    if summary:
        out.append("## AI summary")
        out.append("")
        out.append(summary)
        out.append("")

    out.append("## Pages")
    out.append("")
    for i, p in enumerate(pages, start=1):
        out.append(f"### {i}. {p.title or '(untitled)'}")
        out.append("")
        out.append(f"- URL: <{p.url}>")
        out.append(f"- Links found: {len(p.links)}")
        excerpt = p.text[:300].strip()
        if excerpt:
            out.append("")
            out.append(f"> {excerpt}...")
        out.append("")

    return "\n".join(out)
