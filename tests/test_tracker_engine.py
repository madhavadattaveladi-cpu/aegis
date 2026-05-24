"""Tests for bookmark storage and the chapter-update tracker engine."""

from __future__ import annotations

import httpx
import respx

from aegis.tracker.bookmarks import (
    add_bookmark,
    load_bookmarks,
    remove_bookmark,
)
from aegis.tracker.engine import check_updates
from aegis.tracker.notify import format_terminal_latest, write_markdown_latest


def test_add_and_load_bookmark():
    add_bookmark("https://c.com/manga/x/", title="Series X", site="comichaven")
    bms = load_bookmarks()
    assert "https://c.com/manga/x/" in bms
    assert bms["https://c.com/manga/x/"].title == "Series X"


def test_add_bookmark_is_idempotent():
    add_bookmark("https://c.com/manga/y/", title="Y")
    add_bookmark("https://c.com/manga/y/", title="Y Updated")
    bms = load_bookmarks()
    # Still one entry, title updated, not duplicated.
    matching = [u for u in bms if u == "https://c.com/manga/y/"]
    assert len(matching) == 1
    assert bms["https://c.com/manga/y/"].title == "Y Updated"


def test_remove_bookmark():
    add_bookmark("https://c.com/manga/z/")
    assert remove_bookmark("https://c.com/manga/z/") is True
    assert remove_bookmark("https://c.com/manga/z/") is False


def test_format_terminal_empty():
    assert "none could be read" in format_terminal_latest([])


def test_write_markdown_creates_file():
    results = [{"title": "X", "url": "https://x", "latest_chapter": "Chapter 5",
                "changed": True}]
    path = write_markdown_latest(results, name="test_whats_new.md")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Chapter 5" in content


def test_check_updates_no_bookmarks(monkeypatch, tmp_path):
    # Fresh output dir with no bookmarks file.
    monkeypatch.setenv("AEGIS_OUTPUT_DIR", str(tmp_path / "fresh"))
    import aegis.utils.config as cfg

    cfg._settings = None
    summary = check_updates(notify_desktop=False, write_md=False)
    assert summary["checked"] == 0


@respx.mock
def test_check_updates_reports_latest_and_change(monkeypatch):
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None

    url = "https://comichaven.net/manga/archer-king/"
    add_bookmark(url, title="Archer King")

    # First check: latest is Chapter 2; it's "changed" (no previous).
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text='<a href="/c/1">Chapter 1</a><a href="/c/2">Chapter 2</a>',
        )
    )
    first = check_updates(notify_desktop=False, write_md=False)
    assert first["results"][0]["latest_chapter"] == "Chapter 2"
    assert first["changed"] == 1

    # Second check: same latest -> still reported, but not "changed".
    second = check_updates(notify_desktop=False, write_md=False)
    assert second["results"][0]["latest_chapter"] == "Chapter 2"
    assert second["changed"] == 0

    # Third check: a newer chapter appears -> changed again.
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text='<a href="/c/2">Chapter 2</a><a href="/c/3">Chapter 3</a>',
        )
    )
    third = check_updates(notify_desktop=False, write_md=False)
    assert third["results"][0]["latest_chapter"] == "Chapter 3"
    assert third["changed"] == 1
