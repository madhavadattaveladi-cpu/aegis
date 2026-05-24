"""Tests for the SeriesScout feature."""

from __future__ import annotations

import httpx
import respx

from aegis.llm.base import LLMResponse
from aegis.seriesscout.filters import filter_by_trait, judge_series
from aegis.seriesscout.models import Series, TraitMatch
from aegis.seriesscout.sites import NovelUpdatesAdapter, get_adapter
from tests.conftest import FakeLLM


# ---- models ----
def test_series_to_record():
    s = Series(title="Archer Lord", url="https://x/series/archer-lord/",
               genres=["Action"], tags=["Archery"], source="novelupdates")
    rec = s.to_record()
    assert rec["title"] == "Archer Lord"
    assert rec["genres"] == "Action"
    assert rec["tags"] == "Archery"


# ---- adapter ----
def test_adapter_browse_url_includes_filters():
    a = NovelUpdatesAdapter()
    url = a.browse_url(tag="archery", genre="Action", page=2)
    assert "series-finder" in url
    assert "tags_include=archery" in url
    assert "gi=Action" in url
    assert "pg=2" in url
    # sorts by start date descending = newest first
    assert "sort=sdate" in url


def test_get_adapter_unknown_raises():
    try:
        get_adapter("nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_adapter_parse_listing():
    html = """
    <div class="search_main_box_nu">
      <div class="search_title"><a href="/series/archer-hero/">Archer Hero</a></div>
    </div>
    <div class="search_main_box_nu">
      <div class="search_title"><a href="/series/sword-guy/">Sword Guy</a></div>
    </div>
    """
    a = NovelUpdatesAdapter()
    series = a.parse_listing(html, "https://www.novelupdates.com/series-finder/")
    titles = {s.title for s in series}
    assert "Archer Hero" in titles and "Sword Guy" in titles
    assert all(s.url.startswith("https://www.novelupdates.com/series/") for s in series)


def test_adapter_parse_listing_empty():
    a = NovelUpdatesAdapter()
    assert a.parse_listing("<html><body>nothing</body></html>", "https://x") == []


# ---- trait filter ----
def test_judge_series_match():
    llm = FakeLLM([LLMResponse(
        text='{"matched": true, "reason": "Tag says archery", "confidence": "high"}',
        tool_calls=[])])
    s = Series(title="Bow Master", url="u", tags=["Archery"])
    verdict = judge_series(llm, s, "protagonist uses a bow")
    assert verdict.matched is True
    assert verdict.confidence == "high"


def test_judge_series_bad_json_is_nonmatch():
    llm = FakeLLM([LLMResponse(text="not json at all", tool_calls=[])])
    verdict = judge_series(llm, Series(title="X", url="u"), "bow")
    assert verdict.matched is False
    assert verdict.confidence == "low"


def test_filter_by_trait_keeps_only_matches():
    llm = FakeLLM([
        LLMResponse(text='{"matched": true, "reason": "a", "confidence": "high"}', tool_calls=[]),
        LLMResponse(text='{"matched": false, "reason": "b", "confidence": "low"}', tool_calls=[]),
    ])
    series = [Series(title="A", url="a"), Series(title="B", url="b")]
    matches = filter_by_trait(llm, series, "bow", only_matches=True)
    assert len(matches) == 1
    assert matches[0].series.title == "A"


# ---- engine (mocked HTTP + fake LLM) ----
@respx.mock
def test_scout_end_to_end(monkeypatch):
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None

    listing_html = """
    <div class="search_main_box_nu">
      <div class="search_title"><a href="/series/archer-hero/">Archer Hero</a></div>
    </div>
    """
    # The listing page (series-finder) — match any query string.
    respx.get(url__regex=r"https://www\.novelupdates\.com/series-finder/.*").mock(
        return_value=httpx.Response(200, text=listing_html)
    )
    # The detail page used during enrichment.
    respx.get("https://www.novelupdates.com/series/archer-hero/").mock(
        return_value=httpx.Response(200, text="<title>Archer Hero</title><p>He wields a bow.</p>")
    )

    from aegis.seriesscout.scout import scout

    llm = FakeLLM([
        LLMResponse(text='{"matched": true, "reason": "wields a bow", "confidence": "high"}',
                    tool_calls=[]),
    ])
    summary = scout(llm=llm, trait="protagonist uses a bow", max_pages=1, enrich=True)
    assert summary["series_scanned"] == 1
    assert summary["matches_found"] == 1
    assert "Archer Hero" in summary["top_matches"]
