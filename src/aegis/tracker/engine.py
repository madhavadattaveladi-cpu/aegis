"""The chapter-update tracker engine.

Checks each bookmarked series for chapters newer than the last time we looked,
updates the stored state, and reports via the configured notification channels.

"New" means: a chapter label we have not already recorded in the bookmark's
``known_chapters``. This makes re-running idempotent — you only hear about a
chapter once.
"""

from __future__ import annotations

from typing import Any

from aegis.scraping.fetcher import Fetcher
from aegis.tracker import notify as notify_mod
from aegis.tracker.bookmarks import (
    Bookmark,
    load_bookmarks,
    save_bookmarks,
    touch,
)
from aegis.tracker.chapters import extract_chapters, latest_chapter
from aegis.utils.logging import get_logger

log = get_logger(__name__)


def _check_one(fetcher: Fetcher, bm: Bookmark) -> dict[str, Any]:
    """Check a single bookmark.

    Per the chosen behaviour, this reports the *current latest chapter
    regardless* of history. It also computes whether that latest chapter
    changed since the previous check (``changed``) so the caller can decide
    whether to fire a desktop pop-up (we don't want a pop-up every time when
    nothing is new).
    """
    res = fetcher.fetch(bm.url)
    previous = bm.last_seen_chapter
    touch(bm)
    if not res.ok:
        return {"url": bm.url, "title": bm.title, "ok": False,
                "error": res.error, "latest_chapter": "", "changed": False}

    chapters = extract_chapters(res.html)
    if not chapters:
        return {"url": bm.url, "title": bm.title, "ok": True,
                "latest_chapter": "", "changed": False,
                "note": "no chapters detected"}

    latest = latest_chapter(chapters)
    changed = bool(latest) and latest != previous
    bm.last_seen_chapter = latest

    return {"url": bm.url, "title": bm.title, "ok": True,
            "latest_chapter": latest, "changed": changed,
            "previous_chapter": previous}


def check_updates(
    *,
    notify_desktop: bool = True,
    write_md: bool = True,
    always_notify: bool = False,
) -> dict[str, Any]:
    """Check all bookmarks and report the latest chapter for each.

    Behaviour: the report always shows the *current latest chapter* for every
    tracked series, regardless of whether it changed. Desktop pop-ups, however,
    fire only for series whose latest chapter *changed* since the last check —
    unless ``always_notify`` is set, in which case a pop-up summarises every
    check. This keeps notifications meaningful instead of spammy.
    """
    bookmarks = load_bookmarks()
    if not bookmarks:
        return {"checked": 0, "results": [], "message": "No bookmarks yet."}

    results: list[dict[str, Any]] = []
    with Fetcher() as fetcher:
        for bm in bookmarks.values():
            results.append(_check_one(fetcher, bm))

    save_bookmarks(bookmarks)

    ok_results = [r for r in results if r.get("ok")]
    changed = [r for r in ok_results if r.get("changed")]

    terminal_text = notify_mod.format_terminal_latest(ok_results)
    md_path = notify_mod.write_markdown_latest(ok_results) if write_md else None

    desktop_fired = False
    if notify_desktop:
        if changed:
            # One concise pop-up summarising what changed.
            titles = ", ".join((r["title"] or r["url"]) for r in changed[:3])
            more = f" +{len(changed) - 3} more" if len(changed) > 3 else ""
            desktop_fired = notify_mod.desktop_notify(
                "AEGIS: new chapters",
                f"Updated: {titles}{more}",
            )
        elif always_notify:
            desktop_fired = notify_mod.desktop_notify(
                "AEGIS: chapter check",
                f"Checked {len(bookmarks)} series — nothing new.",
            )

    summary = {
        "checked": len(bookmarks),
        "changed": len(changed),
        "results": results,
        "changed_series": changed,
        "report_text": terminal_text,
        "markdown_path": str(md_path) if md_path else None,
        "desktop_notification_fired": desktop_fired,
        "failures": [r for r in results if not r.get("ok")],
    }
    log.info("Tracker check: %d series, %d changed", summary["checked"], summary["changed"])
    return summary
