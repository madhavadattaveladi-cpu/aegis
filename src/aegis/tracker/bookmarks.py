"""Bookmark store for the chapter-update tracker.

Each bookmark records a series' URL, a display title, the last chapter we've
seen, and when we last checked. Stored as a single JSON file under the output
directory so it persists across runs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from aegis.utils.config import get_settings
from aegis.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class Bookmark:
    """A tracked series and its last-known state."""

    url: str
    title: str = ""
    site: str = ""
    last_seen_chapter: str = ""
    last_checked: str = ""
    # History of chapter labels we've already reported, to avoid duplicates.
    known_chapters: list[str] = field(default_factory=list)


def _store_path() -> Path:
    settings = get_settings()
    return settings.output_dir / "bookmarks.json"


def load_bookmarks() -> dict[str, Bookmark]:
    """Load all bookmarks keyed by URL."""
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {url: Bookmark(**bm) for url, bm in data.items()}


def save_bookmarks(bookmarks: dict[str, Bookmark]) -> Path:
    path = _store_path()
    path.write_text(
        json.dumps({u: asdict(b) for u, b in bookmarks.items()}, indent=2),
        encoding="utf-8",
    )
    return path


def add_bookmark(url: str, title: str = "", site: str = "") -> Bookmark:
    """Add (or update) a bookmark. Idempotent on URL."""
    bookmarks = load_bookmarks()
    if url in bookmarks:
        bm = bookmarks[url]
        if title:
            bm.title = title
        if site:
            bm.site = site
    else:
        bm = Bookmark(url=url, title=title, site=site)
        bookmarks[url] = bm
    save_bookmarks(bookmarks)
    log.info("Bookmarked %s", url)
    return bm


def remove_bookmark(url: str) -> bool:
    bookmarks = load_bookmarks()
    if url in bookmarks:
        del bookmarks[url]
        save_bookmarks(bookmarks)
        return True
    return False


def touch(bm: Bookmark) -> None:
    """Update the last-checked timestamp to now."""
    bm.last_checked = datetime.now().strftime("%Y-%m-%d %H:%M")
