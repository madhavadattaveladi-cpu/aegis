"""Tests for the Fetcher, using respx to mock HTTP — no real network calls."""

from __future__ import annotations

import httpx
import respx

from aegis.scraping.fetcher import Fetcher
from aegis.utils.config import get_settings


@respx.mock
def test_fetch_success(monkeypatch):
    # Disable robots + delay for a fast, isolated test.
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None

    respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="<html><title>ok</title></html>")
    )
    with Fetcher() as fetcher:
        result = fetcher.fetch("https://example.com/")

    assert result.ok
    assert result.status_code == 200
    assert "ok" in result.html


@respx.mock
def test_fetch_client_error_not_ok(monkeypatch):
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None

    respx.get("https://example.com/missing").mock(return_value=httpx.Response(404))
    with Fetcher() as fetcher:
        result = fetcher.fetch("https://example.com/missing")

    assert not result.ok
    assert "404" in (result.error or "")


@respx.mock
def test_fetch_many_concurrent(monkeypatch):
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None

    for i in range(5):
        respx.get(f"https://example.com/{i}").mock(
            return_value=httpx.Response(200, text=f"<title>page {i}</title>")
        )
    urls = [f"https://example.com/{i}" for i in range(5)]
    with Fetcher() as fetcher:
        results = fetcher.fetch_many(urls)

    assert len(results) == 5
    assert all(r.ok for r in results)
