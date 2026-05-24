"""Tests for the BFS crawler, using respx to mock HTTP."""

from __future__ import annotations

import httpx
import respx

from aegis.scraping.crawler import crawl


def _setup_env(monkeypatch):
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None


@respx.mock
def test_crawl_follows_links_to_depth(monkeypatch):
    _setup_env(monkeypatch)
    respx.get("https://site.com/").mock(
        return_value=httpx.Response(
            200,
            text='<title>Home</title><a href="/a">a</a><a href="/b">b</a>',
        )
    )
    respx.get("https://site.com/a").mock(
        return_value=httpx.Response(200, text="<title>A</title>")
    )
    respx.get("https://site.com/b").mock(
        return_value=httpx.Response(200, text="<title>B</title>")
    )

    result = crawl(["https://site.com/"], max_depth=1, max_pages=10)
    titles = {p.title for p in result.pages}
    assert titles == {"Home", "A", "B"}


@respx.mock
def test_crawl_depth_zero_only_seed(monkeypatch):
    _setup_env(monkeypatch)
    respx.get("https://site.com/").mock(
        return_value=httpx.Response(200, text='<title>Home</title><a href="/a">a</a>')
    )
    result = crawl(["https://site.com/"], max_depth=0, max_pages=10)
    assert len(result.pages) == 1
    assert result.pages[0].title == "Home"


@respx.mock
def test_crawl_respects_max_pages(monkeypatch):
    _setup_env(monkeypatch)
    links = "".join(f'<a href="/p{i}">p{i}</a>' for i in range(10))
    respx.get("https://site.com/").mock(
        return_value=httpx.Response(200, text=f"<title>Home</title>{links}")
    )
    for i in range(10):
        respx.get(f"https://site.com/p{i}").mock(
            return_value=httpx.Response(200, text=f"<title>P{i}</title>")
        )
    result = crawl(["https://site.com/"], max_depth=1, max_pages=3)
    assert len(result.visited) <= 3


@respx.mock
def test_crawl_stays_on_domain(monkeypatch):
    _setup_env(monkeypatch)
    respx.get("https://site.com/").mock(
        return_value=httpx.Response(
            200,
            text='<title>Home</title><a href="https://other.com/x">off</a>',
        )
    )
    result = crawl(["https://site.com/"], max_depth=2, same_domain_only=True)
    visited_hosts = {p.url for p in result.pages}
    assert all("other.com" not in u for u in visited_hosts)
