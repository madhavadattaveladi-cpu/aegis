"""Politeness helpers: robots.txt compliance and per-host rate limiting.

Good scrapers are *polite* scrapers. This module makes AEGIS respect
``robots.txt`` and avoid hammering any single host — important to mention on a
resume because it shows awareness of ethics and rate limits.
"""

from __future__ import annotations

import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

from aegis.utils.logging import get_logger

log = get_logger(__name__)


class RobotsCache:
    """Fetches and caches robots.txt rules per host."""

    def __init__(self, user_agent: str, enabled: bool = True) -> None:
        self._user_agent = user_agent
        self._enabled = enabled
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._lock = threading.Lock()

    def can_fetch(self, url: str) -> bool:
        if not self._enabled:
            return True
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            parser = self._cache.get(host)
            if parser is None:
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(f"{host}/robots.txt")
                try:
                    parser.read()
                except Exception as exc:  # network/parse failure -> be permissive
                    log.warning("Could not read robots.txt for %s: %s", host, exc)
                self._cache[host] = parser
        allowed = parser.can_fetch(self._user_agent, url)
        if not allowed:
            log.info("robots.txt disallows %s", url)
        return allowed


class RateLimiter:
    """Enforces a minimum delay between requests to the same host."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay = delay_seconds
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        with self._lock:
            now = time.monotonic()
            last = self._last_hit.get(host, 0.0)
            elapsed = now - last
            if elapsed < self._delay:
                sleep_for = self._delay - elapsed
                time.sleep(sleep_for)
            self._last_hit[host] = time.monotonic()
