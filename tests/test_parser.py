"""Tests for HTML parsing."""

from __future__ import annotations

from aegis.scraping.parser import parse_html

SAMPLE = """
<html>
  <head><title>  Hello World  </title></head>
  <body>
    <script>var x = 1;</script>
    <h1>Heading</h1>
    <p>Some  text   here.</p>
    <a href="/about">About</a>
    <a href="https://example.com/contact">Contact</a>
    <a href="mailto:a@b.com">Mail</a>
    <a href="/about">About again (dup)</a>
  </body>
</html>
"""


def test_title_is_stripped():
    page = parse_html("https://example.com/", SAMPLE)
    assert page.title == "Hello World"


def test_scripts_removed_and_whitespace_collapsed():
    page = parse_html("https://example.com/", SAMPLE)
    assert "var x" not in page.text
    assert "Some text here." in page.text


def test_links_absolute_deduped_and_filtered():
    page = parse_html("https://example.com/", SAMPLE)
    assert "https://example.com/about" in page.links
    assert "https://example.com/contact" in page.links
    # mailto: filtered out
    assert all("mailto:" not in link for link in page.links)
    # duplicate /about appears only once
    assert page.links.count("https://example.com/about") == 1
