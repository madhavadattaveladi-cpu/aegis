"""The SeriesScout engine.

Ties the pieces together:
  1. Build a browse URL for a site + tag/genre.
  2. Fetch & parse listing pages into Series (with AI fallback if selectors miss).
  3. Optionally enrich each series by fetching its detail page for tags/description.
  4. Filter by a natural-language trait using the LLM.
  5. Save results (JSON + Excel).

This is the headline "focused feature built on the AEGIS pipeline" — it reuses
the Fetcher, parser, LLM, and Storage layers rather than reinventing them.
"""

from __future__ import annotations

from typing import Any

from aegis.llm.base import LLMProvider, Message
from aegis.scraping.fetcher import Fetcher
from aegis.scraping.parser import parse_html
from aegis.seriesscout.filters import filter_by_trait
from aegis.seriesscout.models import Series
from aegis.seriesscout.sites import get_adapter
from aegis.storage.store import Storage
from aegis.utils.logging import get_logger

log = get_logger(__name__)

_AI_LISTING_SYSTEM = (
    "You extract a list of fiction series from web page text. "
    "Respond with ONLY a JSON array of objects like "
    '[{"title": "...", "url": "..."}]. If none are found, return [].'
)


def _ai_listing_fallback(llm: LLMProvider, page_text: str, source: str) -> list[Series]:
    """If CSS selectors find nothing, ask the LLM to pull titles from the text."""
    import json

    resp = llm.chat(
        [Message(role="system", content=_AI_LISTING_SYSTEM),
         Message(role="user", content=page_text[:6000])],
        temperature=0.0,
    )
    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[Series] = []
    for it in items if isinstance(items, list) else []:
        title = str(it.get("title", "")).strip()
        if title:
            out.append(Series(title=title, url=str(it.get("url", "")), source=source))
    return out


def enrich_series(fetcher: Fetcher, series: Series) -> Series:
    """Fetch a series' detail page to fill in description and tags."""
    if not series.url:
        return series
    res = fetcher.fetch(series.url)
    if not res.ok:
        return series
    parsed = parse_html(series.url, res.html)
    # Use the cleaned page text as a description proxy; keep it bounded.
    series.description = parsed.text[:1500]
    return series


def scout(
    *,
    llm: LLMProvider,
    trait: str,
    site: str = "novelupdates",
    tag: str | None = None,
    genre: str | None = None,
    max_pages: int = 1,
    enrich: bool = True,
    enrich_limit: int = 15,
    include_unknown: bool = False,
    run_name: str = "seriesscout",
) -> dict[str, Any]:
    """Discover new series matching a trait.

    Args:
        llm: the language model (used for trait judgement and AI fallback).
        trait: plain-English trait, e.g. "main protagonist uses a bow".
        site: which site adapter to use.
        tag/genre: filters passed to the site's browse URL.
        max_pages: how many listing pages to scan.
        enrich: fetch each series' detail page for better filtering.
        enrich_limit: cap on how many series to enrich (politeness/cost).
        run_name: label for the saved output.

    Returns a summary dict with counts and output paths.
    """
    adapter = get_adapter(site)
    collected: list[Series] = []

    with Fetcher() as fetcher:
        for page in range(1, max_pages + 1):
            url = adapter.browse_url(tag=tag, genre=genre, page=page)
            res = fetcher.fetch(url)
            if not res.ok:
                log.warning("Listing fetch failed (%s): %s", res.error, url)
                continue
            series = adapter.parse_listing(res.html, url)
            if not series:
                # Selectors found nothing — fall back to AI extraction.
                parsed = parse_html(url, res.html)
                series = _ai_listing_fallback(llm, parsed.text, adapter.name)
            collected.extend(series)

        # Dedupe across pages by URL (or title if URL missing).
        seen: set[str] = set()
        unique: list[Series] = []
        for s in collected:
            key = s.url or s.title
            if key not in seen:
                seen.add(key)
                unique.append(s)

        if enrich:
            for s in unique[:enrich_limit]:
                enrich_series(fetcher, s)

    matches = filter_by_trait(
        llm, unique, trait, only_matches=True, include_unknown=include_unknown
    )

    storage = Storage(run_name=run_name)
    records = [m.to_record() for m in matches]
    json_path = storage.save_json(records, name=run_name)
    xlsx_path = storage.save_xlsx(records, name=run_name)

    summary = {
        "trait": trait,
        "site": site,
        "series_scanned": len(unique),
        "matches_found": len(matches),
        "json_path": str(json_path),
        "xlsx_path": str(xlsx_path),
        "run_dir": str(storage.run_dir),
        "top_matches": [m.series.title for m in matches[:10]],
    }
    log.info("SeriesScout complete: %s", summary)
    return summary
