"""Detect chapter labels and the latest chapter from a series page.

Comic/novel sites vary a lot, so this uses two strategies:
  1. Look for links whose text or href looks like a chapter
     (e.g. "Chapter 42", "/chapter-42/").
  2. Fall back to a regex over the page text for "Chapter <n>" patterns.

Returns chapter labels in the order found; the caller decides which is newest.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Matches "Chapter 12", "Ch. 12", "Episode 7", "Ch 7.5", etc.
_CHAPTER_RE = re.compile(
    r"\b(?:chapter|chap|ch|episode|ep)\.?\s*#?\s*(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)


def _label_for(num: str) -> str:
    return f"Chapter {num}"


def extract_chapters(html: str) -> list[str]:
    """Extract a de-duplicated list of chapter labels from a page."""
    soup = BeautifulSoup(html, "lxml")

    found: list[str] = []
    seen: set[str] = set()

    # Strategy 1: anchor links that look like chapters.
    for a in soup.find_all("a"):
        text = a.get_text(" ", strip=True)
        href = a.get("href", "")
        for source in (text, href):
            m = _CHAPTER_RE.search(source or "")
            if m:
                label = _label_for(m.group(1))
                if label not in seen:
                    seen.add(label)
                    found.append(label)
                break

    # Strategy 2: regex across the visible text (covers non-anchor layouts).
    if not found:
        text = soup.get_text(" ", strip=True)
        for m in _CHAPTER_RE.finditer(text):
            label = _label_for(m.group(1))
            if label not in seen:
                seen.add(label)
                found.append(label)

    return found


def _chapter_number(label: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)", label)
    return float(m.group(1)) if m else -1.0


def latest_chapter(chapters: list[str]) -> str:
    """Return the highest-numbered chapter label, or '' if none."""
    if not chapters:
        return ""
    return max(chapters, key=_chapter_number)
