"""Trait filtering: decide whether a series matches a user trait like
"main protagonist uses a bow".

Uses the LLM to judge each series from its title, genres, tags, and (when
available) description. Returns a structured verdict with a confidence level so
the user can see *why* something matched.
"""

from __future__ import annotations

import json

from aegis.llm.base import LLMProvider, Message
from aegis.seriesscout.models import Series, TraitMatch
from aegis.utils.logging import get_logger

log = get_logger(__name__)

_FILTER_SYSTEM = (
    "You judge whether a fiction series matches a requested trait. "
    "Base your judgement ONLY on the provided title, genres, tags, and "
    "description. Do NOT use outside knowledge and do NOT guess. "
    "If the available information does not reveal whether the trait holds "
    '(e.g. the title is vague and there is no synopsis), set "matched" to '
    'false and "confidence" to "unknown" and say what was missing. '
    "Respond with ONLY a JSON object: "
    '{"matched": true/false, "reason": "...", '
    '"confidence": "unknown|low|medium|high"}'
)


def judge_series(llm: LLMProvider, series: Series, trait: str) -> TraitMatch:
    """Ask the LLM whether a single series matches ``trait``."""
    info = (
        f"TRAIT TO CHECK: {trait}\n\n"
        f"SERIES TITLE: {series.title}\n"
        f"GENRES: {', '.join(series.genres) or '(none listed)'}\n"
        f"TAGS: {', '.join(series.tags) or '(none listed)'}\n"
        f"DESCRIPTION: {series.description[:1200] or '(none available)'}"
    )
    resp = llm.chat(
        [Message(role="system", content=_FILTER_SYSTEM),
         Message(role="user", content=info)],
        temperature=0.0,
    )
    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    try:
        data = json.loads(raw)
        return TraitMatch(
            series=series,
            matched=bool(data.get("matched", False)),
            reason=str(data.get("reason", "")),
            confidence=str(data.get("confidence", "low")),
        )
    except (json.JSONDecodeError, AttributeError):
        # If the model didn't return clean JSON, treat as an uncertain non-match.
        return TraitMatch(
            series=series, matched=False,
            reason="Could not parse model judgement.", confidence="low",
        )


def filter_by_trait(
    llm: LLMProvider, series_list: list[Series], trait: str,
    *, only_matches: bool = True, include_unknown: bool = False,
) -> list[TraitMatch]:
    """Judge every series against ``trait``.

    Returns TraitMatch objects. If ``only_matches`` is True, non-matches are
    dropped — except that ``include_unknown`` keeps results whose confidence is
    "unknown" (the title/synopsis didn't reveal the trait), so the user can see
    them flagged as unknown rather than silently discarded.
    """
    verdicts = [judge_series(llm, s, trait) for s in series_list]
    if only_matches:
        verdicts = [
            v for v in verdicts
            if v.matched or (include_unknown and v.confidence == "unknown")
        ]
    log.info("Trait filter: %d/%d series matched %r (unknown kept: %s)",
             sum(v.matched for v in verdicts), len(series_list), trait,
             include_unknown)
    return verdicts
