"""Resumable scrape jobs.

A *job* is a saved configuration (a name, a list of URLs, scrape options) plus
persistent state tracking which URLs have already been completed. Re-running a
job skips URLs it has already finished — so an interrupted large scrape can be
resumed instead of restarting from zero.

Jobs are stored as JSON under ``<output_dir>/jobs/<name>.json``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from aegis.scraping.fetcher import Fetcher
from aegis.scraping.parser import parse_html
from aegis.storage.store import Storage
from aegis.utils.config import get_settings
from aegis.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class Job:
    """A resumable scrape job and its progress."""

    name: str
    urls: list[str]
    extract_instruction: str | None = None
    completed: list[str] = field(default_factory=list)
    run_count: int = 0

    @property
    def pending(self) -> list[str]:
        done = set(self.completed)
        return [u for u in self.urls if u not in done]

    @property
    def is_complete(self) -> bool:
        return not self.pending


def _jobs_dir() -> Path:
    path = get_settings().output_dir / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_path(name: str) -> Path:
    return _jobs_dir() / f"{name}.json"


def save_job(job: Job) -> Path:
    path = _job_path(job.name)
    path.write_text(json.dumps(asdict(job), indent=2), encoding="utf-8")
    return path


def load_job(name: str) -> Job | None:
    path = _job_path(name)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Job(**data)


def list_jobs() -> list[str]:
    return sorted(p.stem for p in _jobs_dir().glob("*.json"))


def create_job(
    name: str, urls: list[str], extract_instruction: str | None = None
) -> Job:
    """Create and persist a new job (overwrites any existing one of that name)."""
    job = Job(name=name, urls=urls, extract_instruction=extract_instruction)
    save_job(job)
    log.info("Created job %r with %d URLs", name, len(urls))
    return job


def run_job(name: str, *, batch_size: int | None = None) -> dict:
    """Run (or resume) a job, scraping only its pending URLs.

    Args:
        name: the job name.
        batch_size: if set, process at most this many pending URLs this run
            (handy for chunking a very large job across multiple runs).

    Returns a summary dict including how many URLs remain.
    """
    job = load_job(name)
    if job is None:
        return {"error": f"No job named {name!r}."}

    pending = job.pending
    if batch_size is not None:
        pending = pending[:batch_size]

    if not pending:
        return {"job": name, "status": "already complete", "remaining": 0}

    records: list[dict] = []
    with Fetcher() as fetcher:
        results = fetcher.fetch_many(pending)

    for res in results:
        if res.ok:
            parsed = parse_html(res.url, res.html)
            records.append(
                {"url": parsed.url, "ok": True, "title": parsed.title,
                 "num_links": len(parsed.links)}
            )
            job.completed.append(res.url)
        else:
            records.append({"url": res.url, "ok": False, "error": res.error})
            # A hard failure still counts as "attempted" so we don't loop forever
            # on a permanently dead URL.
            job.completed.append(res.url)

    job.run_count += 1
    save_job(job)

    storage = Storage(run_name=f"job-{name}")
    json_path = storage.save_json(records, name=f"{name}-run{job.run_count}")

    return {
        "job": name,
        "status": "complete" if job.is_complete else "in progress",
        "processed_this_run": len(records),
        "remaining": len(job.pending),
        "run_count": job.run_count,
        "json_path": str(json_path),
    }
