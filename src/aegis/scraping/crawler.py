"""A breadth-first web crawler built on top of the Fetcher.

Starts from one or more seed URLs and follows links up to a maximum depth,
staying within the allowed domain(s) and never visiting the same URL twice.
This turns AEGIS from a "scrape these exact URLs" tool into a real crawler.

Design notes worth mentioning in an interview:
  * BFS (a queue), so depth is well-defined and easy to cap.
  * A ``visited`` set gives O(1) dedupe and prevents infinite loops.
  * Domain restriction stops the crawler wandering off across the whole web.
  * ``max_pages`` is a hard safety cap so a crawl always terminates.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse

from aegis.scraping.fetcher import Fetcher
from aegis.scraping.parser import ParsedPage, parse_html
from aegis.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class CrawlResult:
    """Everything a crawl produced."""

    pages: list[ParsedPage] = field(default_factory=list)
    visited: set[str] = field(default_factory=set)
    failed: list[str] = field(default_factory=list)


def _registrable(url: str) -> str:
    """Return the netloc (host) of a URL, lower-cased."""
    return urlparse(url).netloc.lower()


def _same_site(url: str, allowed: set[str]) -> bool:
    host = _registrable(url)
    return any(host == a or host.endswith("." + a) for a in allowed)


def crawl(
    seeds: list[str],
    *,
    max_depth: int = 2,
    max_pages: int = 50,
    same_domain_only: bool = True,
    fetcher: Fetcher | None = None,
) -> CrawlResult:
    """Breadth-first crawl starting from ``seeds``.

    Args:
        seeds: starting URLs.
        max_depth: how many link-hops from a seed to follow (0 = seeds only).
        max_pages: hard cap on total pages fetched.
        same_domain_only: if True, never leave the seeds' domains.
        fetcher: an existing Fetcher to reuse; one is created if omitted.

    Returns:
        A :class:`CrawlResult` with the parsed pages, visited set, and failures.
    """
    own_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()
    allowed = {_registrable(s) for s in seeds} if same_domain_only else set()

    result = CrawlResult()
    queue: deque[tuple[str, int]] = deque((s, 0) for s in seeds)
    queued: set[str] = set(seeds)

    try:
        while queue and len(result.visited) < max_pages:
            url, depth = queue.popleft()
            if url in result.visited:
                continue
            result.visited.add(url)

            res = fetcher.fetch(url)
            if not res.ok:
                result.failed.append(url)
                continue

            page = parse_html(res.url, res.html)
            result.pages.append(page)

            if depth >= max_depth:
                continue

            for link in page.links:
                if link in queued or link in result.visited:
                    continue
                if same_domain_only and not _same_site(link, allowed):
                    continue
                if not link.startswith(("http://", "https://")):
                    continue
                queue.append((link, depth + 1))
                queued.add(link)
    finally:
        if own_fetcher:
            fetcher.close()

    log.info(
        "Crawl finished: %d pages, %d failed, depth<=%d",
        len(result.pages), len(result.failed), max_depth,
    )
    return result
