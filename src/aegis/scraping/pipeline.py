"""The scraping pipeline: fetch -> parse -> (optional AI extraction) -> store.

This ties the scraping, LLM, and storage layers together into one callable
flow. The AI-extraction step uses the LLM to pull *structured* fields out of
messy page text according to a natural-language instruction — the
"generative AI" part of the pipeline.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from aegis.llm.base import LLMProvider, Message
from aegis.scraping.crawler import crawl
from aegis.scraping.fetcher import Fetcher
from aegis.scraping.parser import parse_html
from aegis.scraping.report import ai_summarize, build_markdown_report
from aegis.storage.store import Storage
from aegis.utils.logging import get_logger

log = get_logger(__name__)

_EXTRACT_SYSTEM = (
    "You extract structured data from web page text. "
    "Respond with ONLY a compact JSON object and no other prose, code fences, "
    "or explanation. If a requested field is missing, use null."
)


def ai_extract(llm: LLMProvider, page_text: str, instruction: str) -> dict[str, Any]:
    """Use the LLM to extract structured fields from page text.

    ``instruction`` is plain English, e.g. "Extract the article title,
    author, and publish date".
    """
    # Trim very long pages to keep prompts manageable.
    snippet = page_text[:6000]
    prompt = (
        f"{instruction}\n\n"
        f"Return a JSON object with the requested fields.\n\n"
        f"PAGE TEXT:\n{snippet}"
    )
    resp = llm.chat(
        [Message(role="system", content=_EXTRACT_SYSTEM),
         Message(role="user", content=prompt)],
        temperature=0.0,
    )
    raw = resp.text.strip()
    # Be forgiving about accidental code fences.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": resp.text, "_parse_error": True}


def run_scrape(
    urls: list[str],
    *,
    llm: LLMProvider | None = None,
    extract_instruction: str | None = None,
    run_name: str = "scrape",
) -> dict[str, Any]:
    """Scrape a list of URLs and persist the results.

    If ``llm`` and ``extract_instruction`` are provided, each page is run
    through AI extraction; otherwise the cleaned text/title/links are stored.

    Returns a small summary dict (counts and output paths).
    """
    records: list[dict[str, Any]] = []

    with Fetcher() as fetcher:
        results = fetcher.fetch_many(urls)

    for res in results:
        if not res.ok:
            records.append({"url": res.url, "ok": False, "error": res.error})
            continue
        parsed = parse_html(res.url, res.html)
        record: dict[str, Any] = {
            "url": parsed.url,
            "ok": True,
            "title": parsed.title,
            "num_links": len(parsed.links),
        }
        if llm and extract_instruction:
            record["extracted"] = ai_extract(llm, parsed.text, extract_instruction)
        else:
            record["text"] = parsed.text[:2000]
        records.append(record)

    storage = Storage(run_name=run_name)
    json_path = storage.save_json(records, name=run_name)
    csv_path = storage.save_csv(
        [{k: v for k, v in r.items() if not isinstance(v, (dict, list))} for r in records],
        name=run_name,
    )
    xlsx_path = storage.save_xlsx(records, name=run_name)

    summary = {
        "total": len(records),
        "ok": sum(1 for r in records if r.get("ok")),
        "failed": sum(1 for r in records if not r.get("ok")),
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "xlsx_path": str(xlsx_path),
        "run_dir": str(storage.run_dir),
    }
    log.info("Scrape complete: %s", summary)
    return summary


def run_crawl(
    seeds: list[str],
    *,
    max_depth: int = 2,
    max_pages: int = 50,
    same_domain_only: bool = True,
    llm: LLMProvider | None = None,
    run_name: str = "crawl",
) -> dict[str, Any]:
    """Crawl from seed URLs, persist results, and write a Markdown report.

    If ``llm`` is provided, the report includes an AI-written summary.
    Returns a summary dict with counts and output paths.
    """
    result = crawl(
        seeds,
        max_depth=max_depth,
        max_pages=max_pages,
        same_domain_only=same_domain_only,
    )

    records = [
        {"url": p.url, "title": p.title, "num_links": len(p.links),
         "text": p.text[:2000]}
        for p in result.pages
    ]

    stats = {
        "seeds": ", ".join(seeds),
        "pages_collected": len(result.pages),
        "pages_failed": len(result.failed),
        "max_depth": max_depth,
        "same_domain_only": same_domain_only,
    }

    summary_text = ai_summarize(llm, result.pages) if llm else None
    report_md = build_markdown_report(
        title=f"Crawl report: {run_name}",
        pages=result.pages,
        summary=summary_text,
        stats=stats,
    )

    storage = Storage(run_name=run_name)
    json_path = storage.save_json(records, name=run_name)
    xlsx_path = storage.save_xlsx(records, name=run_name)
    report_path = storage.save_text(report_md, name=f"{run_name}-report.md")

    out = {
        "pages_collected": len(result.pages),
        "pages_failed": len(result.failed),
        "json_path": str(json_path),
        "xlsx_path": str(xlsx_path),
        "report_path": str(report_path),
        "run_dir": str(storage.run_dir),
        "ai_summary_included": summary_text is not None,
    }
    log.info("Crawl complete: %s", out)
    return out
