"""Notification helpers for the tracker.

Three channels, all best-effort:
  * terminal — always available (returns a formatted string),
  * markdown — writes a ``whats_new.md`` you can open,
  * desktop  — optional Windows toast via the ``plyer`` package if installed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aegis.utils.config import get_settings
from aegis.utils.logging import get_logger

log = get_logger(__name__)


def format_terminal_latest(results: list[dict]) -> str:
    """Build a human-readable report of the latest chapter for each series.

    Shows every tracked series and its current latest chapter regardless of
    whether it changed; changed entries are marked with a star.
    """
    if not results:
        return "No series tracked, or none could be read."
    lines = ["Latest chapters:", ""]
    for r in results:
        marker = " *NEW*" if r.get("changed") else ""
        latest = r.get("latest_chapter") or "(no chapter detected)"
        lines.append(f"  • {r['title'] or r['url']}: {latest}{marker}")
        lines.append(f"      {r['url']}")
    changed = sum(1 for r in results if r.get("changed"))
    lines.append("")
    lines.append(f"({changed} updated since last check)")
    return "\n".join(lines)


def write_markdown_latest(results: list[dict], name: str = "whats_new.md") -> Path:
    """Write the latest-chapter report to a Markdown file in the output dir."""
    settings = get_settings()
    path = settings.output_dir / name
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Latest chapters — {now}", ""]
    if not results:
        lines.append("No series tracked, or none could be read.")
    else:
        for r in results:
            marker = " **(new!)**" if r.get("changed") else ""
            latest = r.get("latest_chapter") or "_(no chapter detected)_"
            lines.append(f"## {r['title'] or r['url']}{marker}")
            lines.append("")
            lines.append(f"- Latest: {latest}")
            lines.append(f"- <{r['url']}>")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def desktop_notify(title: str, message: str) -> bool:
    """Try to show a desktop notification. Returns True if it fired.

    Uses ``plyer`` if available (install via the ``[notify]`` extra). Silently
    returns False when unavailable, so the tracker never crashes over this.
    """
    try:
        from plyer import notification  # type: ignore

        notification.notify(title=title, message=message[:240], timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("Desktop notify unavailable: %s", exc)
        return False
