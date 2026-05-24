"""A simple, portable interval scheduler.

Re-runs a saved job every N seconds until the job completes or a maximum number
of iterations is reached. This is a clean, fully-testable in-process scheduler;
for true "set it and forget it" scheduling on Windows, see the Task Scheduler
section in the README (recommended for production).

Design note: the loop is injectable with ``sleep_fn`` and ``runner`` so tests
can drive it deterministically without real time passing or real network calls.
"""

from __future__ import annotations

import time
from typing import Callable

from aegis.scraping.jobs import run_job
from aegis.utils.logging import get_logger

log = get_logger(__name__)


def schedule_job(
    name: str,
    *,
    interval_seconds: float = 300.0,
    max_iterations: int | None = None,
    batch_size: int | None = None,
    runner: Callable[..., dict] = run_job,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Run a job repeatedly on an interval until it completes.

    Args:
        name: job name to run.
        interval_seconds: delay between runs.
        max_iterations: stop after this many runs (None = until complete).
        batch_size: passed through to each run (chunking).
        runner: the function that executes one run (injectable for tests).
        sleep_fn: sleep implementation (injectable for tests).

    Returns the list of per-run summary dicts.
    """
    history: list[dict] = []
    iteration = 0
    while True:
        iteration += 1
        summary = runner(name, batch_size=batch_size)
        history.append(summary)
        log.info("Scheduled run %d: %s", iteration, summary.get("status"))

        if summary.get("error"):
            break
        if summary.get("status") in ("complete", "already complete"):
            break
        if max_iterations is not None and iteration >= max_iterations:
            break
        sleep_fn(interval_seconds)

    return history
