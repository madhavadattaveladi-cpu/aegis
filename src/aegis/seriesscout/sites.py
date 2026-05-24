"""Site adapters: how to turn a specific site's HTML into Series objects.

Each adapter knows two things:
  * how to build a "browse new series" URL for a tag/genre, and
  * how to parse a listing page into Series objects.

Selectors live in one place so that if a site changes its markup, you fix it
here without touching the rest of the code. If the structured selectors find
nothing, callers can fall back to AI extraction (see scout.py).

NOTE ON ETHICS/ToS: scraping is done through AEGIS's polite Fetcher, which
respects robots.txt and rate limits. Some sites' terms restrict scraping; use
responsibly and prefer official APIs where they exist. This adapter is provided
as an educational example of building a focused scraper on top of the pipeline.
"""

from __future__ import annotations

from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from aegis.seriesscout.models import Series


class SiteAdapter:
    """Base adapter. Subclasses set the site specifics.

    ``name`` and ``base_url`` may be provided either as constructor arguments
    or as class attributes on a subclass; the constructor accepts both so the
    generic subclasses (which set them as class attributes) and explicit ones
    both work.
    """

    name: str = ""
    base_url: str = ""

    def __init__(self, name: str | None = None, base_url: str | None = None) -> None:
        if name is not None:
            self.name = name
        if base_url is not None:
            self.base_url = base_url

    def browse_url(self, *, tag: str | None = None, genre: str | None = None,
                   page: int = 1) -> str:
        raise NotImplementedError

    def parse_listing(self, html: str, page_url: str) -> list[Series]:
        raise NotImplementedError


class NovelUpdatesAdapter(SiteAdapter):
    """Adapter for novelupdates.com.

    NovelUpdates exposes a "series finder" that filters by tag/genre, and
    individual series live at ``/series/<slug>/``. We parse the listing page's
    series links and titles. Selectors are intentionally simple and overridable.
    """

    # CSS selectors kept as class attributes for easy maintenance.
    LISTING_ITEM_SELECTORS = ["div.search_main_box_nu", "div.search_title"]
    TITLE_LINK_SELECTOR = "a"

    def __init__(self) -> None:
        super().__init__(name="novelupdates", base_url="https://www.novelupdates.com")

    def browse_url(self, *, tag: str | None = None, genre: str | None = None,
                   page: int = 1) -> str:
        # The series finder accepts genre and tag filters via query params.
        # We sort by "new" so the freshest series surface first.
        params = ["sf=1", "sort=sdate", "order=desc"]
        if genre:
            params.append(f"gi={quote(genre)}")
        if tag:
            params.append(f"tags_include={quote(tag)}")
        if page > 1:
            params.append(f"pg={page}")
        return f"{self.base_url}/series-finder/?{'&'.join(params)}"

    def parse_listing(self, html: str, page_url: str) -> list[Series]:
        soup = BeautifulSoup(html, "lxml")
        out: list[Series] = []

        # Try each known container selector until one yields results.
        containers = []
        for sel in self.LISTING_ITEM_SELECTORS:
            containers = soup.select(sel)
            if containers:
                break

        for box in containers:
            link = box.select_one("a[href*='/series/']") or box.select_one(
                self.TITLE_LINK_SELECTOR
            )
            if not link or not link.get("href"):
                continue
            href = urljoin(self.base_url, link["href"])
            title = link.get_text(strip=True) or link.get("title", "")
            if not title:
                continue
            # Genres/tags sometimes appear as small links within the box.
            genres = [
                g.get_text(strip=True)
                for g in box.select("a[href*='/genre/'], a[href*='/series-finder']")
                if g.get_text(strip=True)
            ]
            out.append(
                Series(title=title, url=href, genres=genres, source=self.name)
            )

        # Dedupe by URL while preserving order.
        seen: set[str] = set()
        unique = [s for s in out if not (s.url in seen or seen.add(s.url))]
        return unique


class _GenericSearchAdapter(SiteAdapter):
    """A reusable adapter for sites with a simple ``?s=<query>`` search page.

    Many comic/novel sites (often WordPress + a manga theme) expose search at
    ``/?s=<query>`` and list results as anchor links inside cards. This base
    class encodes that common shape; subclasses just set ``base_url``,
    ``name``, ``search_path``, and the selectors. Selector lists are tried in
    order so a theme update only needs a new entry here.
    """

    name = "generic"
    base_url = ""
    search_path = "/?s="
    ITEM_SELECTORS: list[str] = ["div.bsx", "div.utao", "div.list-update_item", "article"]
    LINK_SELECTOR = "a[href]"
    SERIES_HREF_HINT = "/"  # substring that marks a real series link

    def browse_url(self, *, tag: str | None = None, genre: str | None = None,
                   page: int = 1) -> str:
        # These sites search by free-text query; we pass the tag/genre as the
        # query term (whichever is provided). The trait filter does the real work.
        query = tag or genre or ""
        return f"{self.base_url}{self.search_path}{quote(query)}"

    def parse_listing(self, html: str, page_url: str) -> list[Series]:
        soup = BeautifulSoup(html, "lxml")
        items = []
        for sel in self.ITEM_SELECTORS:
            items = soup.select(sel)
            if items:
                break

        out: list[Series] = []
        for box in items:
            link = box.select_one(self.LINK_SELECTOR)
            if not link or not link.get("href"):
                continue
            href = urljoin(self.base_url, link["href"])
            if self.SERIES_HREF_HINT not in href:
                continue
            title = (
                link.get("title")
                or link.get_text(strip=True)
                or (box.select_one("img") or {}).get("alt", "")
            )
            title = (title or "").strip()
            if title:
                out.append(Series(title=title, url=href, source=self.name))

        seen: set[str] = set()
        return [s for s in out if not (s.url in seen or seen.add(s.url))]


class LikeMangaAdapter(_GenericSearchAdapter):
    """Adapter for likemanga.ink (free-text search)."""

    name = "likemanga"
    base_url = "https://likemanga.ink"
    search_path = "/?act=search&f[status]=all&f[sortby]=lastupdate&f[keyword]="
    ITEM_SELECTORS = ["div.book_detailed_item", "div.bsx", "article"]
    SERIES_HREF_HINT = "/manga/"


class ComicHavenAdapter(_GenericSearchAdapter):
    """Adapter for comichaven.net (free-text search)."""

    name = "comichaven"
    base_url = "https://comichaven.net"
    search_path = "/?s="
    ITEM_SELECTORS = ["div.bs", "div.bsx", "div.list-update_item", "article"]
    SERIES_HREF_HINT = "/manga/"


class FanFictionAdapter(SiteAdapter):
    """Adapter for fanfiction.net.

    WARNING: fanfiction.net uses aggressive bot protection (Cloudflare). This
    adapter is structurally correct but in practice will often be blocked when
    run through a simple HTTP client; in that case the fetch returns not-ok and
    SeriesScout reports the site as unreachable. Treat results as best-effort.
    """

    name = "fanfiction"
    base_url = "https://www.fanfiction.net"

    def browse_url(self, *, tag: str | None = None, genre: str | None = None,
                   page: int = 1) -> str:
        query = tag or genre or ""
        # The public search endpoint takes a ready-query string.
        return f"{self.base_url}/search/?keywords={quote(query)}&ready=1&type=story"

    def parse_listing(self, html: str, page_url: str) -> list[Series]:
        soup = BeautifulSoup(html, "lxml")
        out: list[Series] = []
        for box in soup.select("div.z-list, div.zhover"):
            link = box.select_one("a.stitle") or box.select_one("a[href*='/s/']")
            if not link or not link.get("href"):
                continue
            href = urljoin(self.base_url, link["href"])
            title = link.get_text(strip=True)
            blurb = box.select_one("div.z-indent")
            desc = blurb.get_text(strip=True) if blurb else ""
            if title:
                out.append(Series(title=title, url=href, description=desc,
                                  source=self.name))
        seen: set[str] = set()
        return [s for s in out if not (s.url in seen or seen.add(s.url))]


# Registry of available adapters, keyed by short name.
ADAPTERS: dict[str, type[SiteAdapter]] = {
    "novelupdates": NovelUpdatesAdapter,
    "likemanga": LikeMangaAdapter,
    "comichaven": ComicHavenAdapter,
    "fanfiction": FanFictionAdapter,
}


def get_adapter(name: str) -> SiteAdapter:
    """Instantiate an adapter by name."""
    cls = ADAPTERS.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown site {name!r}. Available: {', '.join(ADAPTERS)}"
        )
    return cls()  # type: ignore[call-arg]
