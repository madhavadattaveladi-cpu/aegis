"""Data models for SeriesScout."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Series:
    """A single discovered series (manhwa / manga / manhua / novel / etc.)."""

    title: str
    url: str
    description: str = ""
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = ""  # which site it came from

    def to_record(self) -> dict:
        """Flatten for storage/export."""
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "genres": ", ".join(self.genres),
            "tags": ", ".join(self.tags),
            "description": self.description[:500],
        }


@dataclass
class TraitMatch:
    """A series plus why it matched a requested trait."""

    series: Series
    matched: bool
    reason: str = ""
    confidence: str = "low"  # low | medium | high

    def to_record(self) -> dict:
        rec = self.series.to_record()
        rec.update(
            {"matched": self.matched, "match_reason": self.reason,
             "confidence": self.confidence}
        )
        return rec
