"""Tests for resumable jobs and the interval scheduler."""

from __future__ import annotations

import httpx
import respx

from aegis.scraping.jobs import Job, create_job, list_jobs, load_job, run_job
from aegis.scraping.scheduler import schedule_job


def test_job_pending_and_complete():
    job = Job(name="t", urls=["a", "b", "c"], completed=["a"])
    assert job.pending == ["b", "c"]
    assert not job.is_complete
    job.completed = ["a", "b", "c"]
    assert job.is_complete


def test_create_and_load_job():
    create_job("myjob", ["https://x.com/1", "https://x.com/2"])
    assert "myjob" in list_jobs()
    loaded = load_job("myjob")
    assert loaded is not None
    assert loaded.urls == ["https://x.com/1", "https://x.com/2"]
    assert loaded.run_count == 0


def test_run_missing_job():
    assert "error" in run_job("does-not-exist")


@respx.mock
def test_run_job_is_resumable(monkeypatch):
    monkeypatch.setenv("AEGIS_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("AEGIS_REQUEST_DELAY_SECONDS", "0")
    import aegis.utils.config as cfg

    cfg._settings = None

    for i in range(3):
        respx.get(f"https://x.com/{i}").mock(
            return_value=httpx.Response(200, text=f"<title>p{i}</title>")
        )
    create_job("resume", [f"https://x.com/{i}" for i in range(3)])

    # First run: only one URL via batch_size -> 2 remaining.
    first = run_job("resume", batch_size=1)
    assert first["processed_this_run"] == 1
    assert first["remaining"] == 2
    assert first["status"] == "in progress"

    # Second run finishes the rest.
    second = run_job("resume")
    assert second["remaining"] == 0
    assert second["status"] == "complete"

    # A third run has nothing to do.
    third = run_job("resume")
    assert third["status"] == "already complete"


def test_scheduler_runs_until_complete():
    # Fake runner: "in progress" twice, then "complete". No real sleeping.
    calls = {"n": 0}

    def fake_runner(name, batch_size=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return {"status": "in progress", "remaining": 3 - calls["n"]}
        return {"status": "complete", "remaining": 0}

    slept: list[float] = []
    history = schedule_job(
        "x", interval_seconds=10, runner=fake_runner, sleep_fn=slept.append
    )
    assert len(history) == 3
    assert history[-1]["status"] == "complete"
    # Slept between runs but not after the final one.
    assert slept == [10, 10]


def test_scheduler_respects_max_iterations():
    def always_pending(name, batch_size=None):
        return {"status": "in progress", "remaining": 5}

    history = schedule_job(
        "x", interval_seconds=0, max_iterations=4,
        runner=always_pending, sleep_fn=lambda s: None,
    )
    assert len(history) == 4
