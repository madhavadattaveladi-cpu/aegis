"""The fetcher: downloads pages politely, with retries and concurrency.

Combines:
  * a shared httpx.Client (connection pooling),
  * robots.txt compliance,
  * per-host rate limiting,
  * exponential-backoff retries via tenacity,
  * a thread pool for "large-scale" concurrent fetching.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from aegis.scraping.politeness import RateLimiter, RobotsCache
from aegis.utils.config import Settings, get_settings
from aegis.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class FetchResult:
    """Outcome of fetching a single URL."""

    url: str
    status_code: int
    html: str
    ok: bool
    error: str | None = None


class Fetcher:
    """Downloads web pages while respecting rate limits and robots.txt."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(
            headers={"User-Agent": self.settings.user_agent},
            follow_redirects=True,
            timeout=30.0,
        )
        self._robots = RobotsCache(
            self.settings.user_agent, enabled=self.settings.respect_robots
        )
        self._limiter = RateLimiter(self.settings.request_delay_seconds)

    # tenacity retries transient network errors with backoff
    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str) -> httpx.Response:
        self._limiter.wait(url)
        resp = self._client.get(url)
        # Retry on server errors but not on 4xx client errors
        if resp.status_code >= 500:
            resp.raise_for_status()
        return resp

    def fetch(self, url: str) -> FetchResult:
        """Fetch a single URL, returning a FetchResult (never raises)."""
        if not self._robots.can_fetch(url):
            return FetchResult(url, 0, "", ok=False, error="blocked by robots.txt")
        try:
            resp = self._get(url)
            ok = 200 <= resp.status_code < 300
            return FetchResult(
                url=url,
                status_code=resp.status_code,
                html=resp.text if ok else "",
                ok=ok,
                error=None if ok else f"HTTP {resp.status_code}",
            )
        except Exception as exc:  # noqa: BLE001 - surface as a result, not a crash
            log.warning("Fetch failed for %s: %s", url, exc)
            return FetchResult(url, 0, "", ok=False, error=str(exc))

    def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """Fetch many URLs concurrently (the 'large-scale' part)."""
        results: list[FetchResult] = []
        max_workers = max(1, self.settings.max_concurrency)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self.fetch, u): u for u in urls}
            for fut in as_completed(futures):
                results.append(fut.result())
        log.info("Fetched %d/%d URLs successfully",
                 sum(r.ok for r in results), len(results))
        return results

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
