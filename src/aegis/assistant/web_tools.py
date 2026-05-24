"""Keyless web-search and weather helpers for Jarvis.

These intentionally use public, no-API-key endpoints so the project needs no
secrets:
  * Web search  -> DuckDuckGo's HTML endpoint (scraped politely).
  * Weather     -> Open-Meteo (free, keyless) with its geocoding API.

Both require internet access. When offline they return a clear, friendly
message instead of raising — Jarvis stays usable without a connection.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from aegis.utils.config import get_settings
from aegis.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


def web_search(query: str, max_results: int = 5) -> list[SearchHit]:
    """Search the web via DuckDuckGo's HTML endpoint. Returns [] on failure."""
    settings = get_settings()
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": settings.user_agent},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("web_search failed: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    hits: list[SearchHit] = []
    for result in soup.select(".result")[:max_results]:
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        hits.append(
            SearchHit(
                title=link.get_text(strip=True),
                url=link.get("href", ""),
                snippet=snippet.get_text(strip=True) if snippet else "",
            )
        )
    return hits


def _geocode(place: str) -> tuple[float, float, str] | None:
    """Resolve a place name to (lat, lon, label) via Open-Meteo geocoding."""
    try:
        resp = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("geocode failed: %s", exc)
        return None
    results = resp.json().get("results")
    if not results:
        return None
    top = results[0]
    label = ", ".join(
        part for part in (top.get("name"), top.get("country")) if part
    )
    return float(top["latitude"]), float(top["longitude"]), label


def get_weather(place: str) -> dict:
    """Return current weather for a place name. Keyless via Open-Meteo."""
    geo = _geocode(place)
    if geo is None:
        return {"error": f"Could not find a location named {place!r} (or you are offline)."}
    lat, lon, label = geo
    try:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("weather fetch failed: %s", exc)
        return {"error": "Could not reach the weather service (are you offline?)."}

    current = resp.json().get("current", {})
    return {
        "location": label,
        "temperature_c": current.get("temperature_2m"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
    }
