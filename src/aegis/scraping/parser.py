"""Parsing: turn raw HTML into clean, structured data."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass
class ParsedPage:
    """Structured representation of a scraped page."""

    url: str
    title: str
    text: str
    links: list[str] = field(default_factory=list)


def parse_html(url: str, html: str) -> ParsedPage:
    """Extract title, main text, and absolute links from HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content noise
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # Collapse whitespace into clean, readable text
    text = " ".join(soup.get_text(separator=" ").split())

    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href and not href.startswith(("javascript:", "mailto:", "#")):
            links.append(urljoin(url, href))

    # Deduplicate links while preserving order
    seen: set[str] = set()
    unique_links = [x for x in links if not (x in seen or seen.add(x))]

    return ParsedPage(url=url, title=title, text=text, links=unique_links)
