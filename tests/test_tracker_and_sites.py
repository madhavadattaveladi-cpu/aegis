"""Tests for new SeriesScout adapters and the tracker's chapter detection."""

from __future__ import annotations

from aegis.seriesscout.sites import (
    ComicHavenAdapter,
    FanFictionAdapter,
    LikeMangaAdapter,
    get_adapter,
)
from aegis.tracker.chapters import extract_chapters, latest_chapter


# ---- new adapters resolve ----
def test_new_adapters_registered():
    assert isinstance(get_adapter("likemanga"), LikeMangaAdapter)
    assert isinstance(get_adapter("comichaven"), ComicHavenAdapter)
    assert isinstance(get_adapter("fanfiction"), FanFictionAdapter)


def test_generic_search_url_uses_query():
    a = LikeMangaAdapter()
    url = a.browse_url(tag="bow")
    assert url.startswith("https://likemanga.ink")
    assert "bow" in url


def test_comichaven_listing_parse():
    html = """
    <div class="bs"><a href="/manga/archer-king/" title="Archer King"></a></div>
    <div class="bs"><a href="/manga/mage-lord/" title="Mage Lord"></a></div>
    <div class="bs"><a href="/other/not-a-series/" title="Nope"></a></div>
    """
    a = ComicHavenAdapter()
    series = a.parse_listing(html, "https://comichaven.net/?s=bow")
    titles = {s.title for s in series}
    assert "Archer King" in titles and "Mage Lord" in titles
    # links that don't look like a series are filtered out
    assert "Nope" not in titles


def test_fanfiction_listing_parse():
    html = """
    <div class="z-list zhover">
      <a class="stitle" href="/s/123/1/Story-Title">Story Title</a>
      <div class="z-indent">A hero with a bow saves the realm.</div>
    </div>
    """
    a = FanFictionAdapter()
    series = a.parse_listing(html, "https://www.fanfiction.net/search/")
    assert len(series) == 1
    assert series[0].title == "Story Title"
    assert "bow" in series[0].description.lower()


# ---- chapter detection ----
def test_extract_chapters_from_links():
    html = """
    <a href="/comic/x/chapter-5">Chapter 5</a>
    <a href="/comic/x/chapter-6">Chapter 6</a>
    <a href="/comic/x/chapter-6">Chapter 6 (dup)</a>
    """
    chapters = extract_chapters(html)
    assert "Chapter 5" in chapters and "Chapter 6" in chapters
    assert chapters.count("Chapter 6") == 1


def test_extract_chapters_text_fallback():
    html = "<div>Latest: Episode 12 released today</div>"
    chapters = extract_chapters(html)
    assert "Chapter 12" in chapters


def test_latest_chapter_picks_highest():
    assert latest_chapter(["Chapter 3", "Chapter 41", "Chapter 7"]) == "Chapter 41"
    assert latest_chapter([]) == ""


def test_decimal_chapters():
    html = '<a href="/x/ch-10.5">Chapter 10.5</a><a href="/x/ch-10">Chapter 10</a>'
    chapters = extract_chapters(html)
    assert latest_chapter(chapters) == "Chapter 10.5"
