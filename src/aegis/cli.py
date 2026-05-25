"""AEGIS command-line interface.

Subcommands:
  * ``aegis scrape URL [URL ...]``  — run the scraping pipeline
  * ``aegis assistant``             — start the Jarvis assistant
  * ``aegis info``                  — show current configuration

After ``pip install -e .`` the ``aegis`` command is available, or run
``python -m aegis.cli ...``.
"""

from __future__ import annotations

import argparse
import sys

from aegis.assistant.jarvis import run_repl
from aegis.llm.factory import build_llm
from aegis.scraping.jobs import create_job, list_jobs, load_job, run_job
from aegis.scraping.pipeline import run_crawl, run_scrape
from aegis.scraping.scheduler import schedule_job
from aegis.seriesscout.scout import scout as run_scout
from aegis.tracker.bookmarks import add_bookmark, load_bookmarks, remove_bookmark
from aegis.tracker.engine import check_updates
from aegis.utils.config import get_settings
from aegis.utils.logging import console, set_verbose


def _cmd_scrape(args: argparse.Namespace) -> int:
    llm = build_llm() if args.extract else None
    summary = run_scrape(
        args.urls,
        llm=llm,
        extract_instruction=args.extract,
        run_name=args.name,
    )
    console.print(summary)
    return 0


def _cmd_crawl(args: argparse.Namespace) -> int:
    llm = build_llm() if args.summarize else None
    summary = run_crawl(
        args.seeds,
        max_depth=args.depth,
        max_pages=args.max_pages,
        same_domain_only=not args.allow_offsite,
        llm=llm,
        run_name=args.name,
    )
    console.print(summary)
    return 0


def _cmd_assistant(args: argparse.Namespace) -> int:
    run_repl(use_voice=args.voice)
    return 0


def _cmd_scout(args: argparse.Namespace) -> int:
    llm = build_llm()
    summary = run_scout(
        llm=llm,
        trait=args.trait,
        site=args.site,
        tag=args.tag,
        genre=args.genre,
        max_pages=args.pages,
        enrich=not args.no_enrich,
        include_unknown=args.include_unknown,
        run_name=args.name,
    )
    console.print(summary)
    return 0


def _cmd_track(args: argparse.Namespace) -> int:
    if args.action == "add":
        bm = add_bookmark(args.url, title=args.title or "", site=args.site or "")
        console.print(f"Tracking: {bm.title or bm.url}")
    elif args.action == "remove":
        ok = remove_bookmark(args.url)
        console.print("Removed." if ok else "That URL wasn't tracked.")
    elif args.action == "list":
        bms = load_bookmarks()
        if not bms:
            console.print("No bookmarks yet.")
        else:
            for bm in bms.values():
                last = bm.last_seen_chapter or "—"
                console.print(f"  • {bm.title or bm.url}  (last seen: {last})")
    elif args.action == "check":
        summary = check_updates(
            notify_desktop=not args.no_desktop,
            write_md=not args.no_markdown,
            always_notify=args.always_notify,
        )
        console.print(summary.get("report_text", summary.get("message", "")))
        if summary.get("markdown_path"):
            console.print(f"\n(Report written to {summary['markdown_path']})")
    return 0


def _cmd_job(args: argparse.Namespace) -> int:
    if args.action == "create":
        job = create_job(args.name, args.urls, extract_instruction=args.extract)
        console.print(f"Created job {job.name!r} with {len(job.urls)} URLs.")
    elif args.action == "run":
        console.print(run_job(args.name, batch_size=args.batch_size))
    elif args.action == "list":
        jobs = list_jobs()
        console.print(jobs if jobs else "No jobs yet.")
    elif args.action == "status":
        job = load_job(args.name)
        if job is None:
            console.print(f"No job named {args.name!r}.")
        else:
            console.print({
                "name": job.name, "total_urls": len(job.urls),
                "completed": len(job.completed), "remaining": len(job.pending),
                "runs": job.run_count, "complete": job.is_complete,
            })
    elif args.action == "schedule":
        history = schedule_job(
            args.name,
            interval_seconds=args.interval,
            max_iterations=args.max_iterations,
            batch_size=args.batch_size,
        )
        console.print(f"Ran {len(history)} scheduled iteration(s).")
        console.print(history[-1] if history else {})
    return 0


def _cmd_info(_: argparse.Namespace) -> int:
    s = get_settings()
    console.print("[bold]AEGIS configuration[/bold]")
    console.print(f"  LLM backend     : {s.llm_backend}")
    console.print(f"  Ollama model    : {s.ollama_model} @ {s.ollama_host}")
    console.print(f"  Claude model    : {s.claude_model}")
    console.print(f"  Output dir      : {s.output_dir}")
    console.print(f"  Respect robots  : {s.respect_robots}")
    console.print(f"  Request delay   : {s.request_delay_seconds}s")
    console.print(f"  Max concurrency : {s.max_concurrency}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis", description="Agentic scraping + AI assistant")
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show the detailed thinking process (step-by-step tool calls and HTTP logs).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="Scrape one or more URLs")
    p_scrape.add_argument("urls", nargs="+", help="URLs to scrape")
    p_scrape.add_argument(
        "--extract", "-e", default=None,
        help="Plain-English instruction for AI extraction (enables the LLM step).",
    )
    p_scrape.add_argument("--name", "-n", default="scrape", help="Run label")
    p_scrape.set_defaults(func=_cmd_scrape)

    p_crawl = sub.add_parser("crawl", help="Crawl a site by following links")
    p_crawl.add_argument("seeds", nargs="+", help="Seed URL(s)")
    p_crawl.add_argument("--depth", "-d", type=int, default=1, help="Max link depth")
    p_crawl.add_argument("--max-pages", "-m", type=int, default=20, help="Page cap")
    p_crawl.add_argument("--summarize", "-s", action="store_true",
                         help="Include an AI-written summary in the report")
    p_crawl.add_argument("--allow-offsite", action="store_true",
                         help="Allow following links off the seed domain")
    p_crawl.add_argument("--name", "-n", default="crawl", help="Run label")
    p_crawl.set_defaults(func=_cmd_crawl)

    p_assistant = sub.add_parser("assistant", help="Start the Jarvis assistant")
    p_assistant.add_argument("--voice", action="store_true", help="Enable voice I/O")
    p_assistant.set_defaults(func=_cmd_assistant)

    p_job = sub.add_parser("job", help="Create/run/resume/schedule scrape jobs")
    job_sub = p_job.add_subparsers(dest="action", required=True)

    j_create = job_sub.add_parser("create", help="Create a resumable job")
    j_create.add_argument("name")
    j_create.add_argument("urls", nargs="+")
    j_create.add_argument("--extract", "-e", default=None)

    j_run = job_sub.add_parser("run", help="Run/resume a job (skips completed URLs)")
    j_run.add_argument("name")
    j_run.add_argument("--batch-size", "-b", type=int, default=None)

    job_sub.add_parser("list", help="List all jobs")

    j_status = job_sub.add_parser("status", help="Show a job's progress")
    j_status.add_argument("name")

    j_sched = job_sub.add_parser("schedule", help="Re-run a job on an interval")
    j_sched.add_argument("name")
    j_sched.add_argument("--interval", "-i", type=float, default=300.0,
                         help="Seconds between runs")
    j_sched.add_argument("--max-iterations", "-x", type=int, default=None)
    j_sched.add_argument("--batch-size", "-b", type=int, default=None)

    p_job.set_defaults(func=_cmd_job)

    p_scout = sub.add_parser(
        "scout", help="Discover new series matching a trait (e.g. bow-using hero)"
    )
    p_scout.add_argument("trait", help='e.g. "main protagonist uses a bow"')
    p_scout.add_argument(
        "--site", default="novelupdates",
        help="Site adapter: novelupdates, likemanga, comichaven, fanfiction",
    )
    p_scout.add_argument("--tag", default=None, help="Tag/keyword filter for the site")
    p_scout.add_argument("--genre", default=None, help="Genre filter for the site")
    p_scout.add_argument("--pages", "-p", type=int, default=1, help="Listing pages to scan")
    p_scout.add_argument("--no-enrich", action="store_true",
                         help="Skip fetching each series' detail page (faster, less accurate)")
    p_scout.add_argument("--include-unknown", action="store_true",
                         help="Also list series where the trait could not be determined")
    p_scout.add_argument("--name", "-n", default="seriesscout", help="Run label")
    p_scout.set_defaults(func=_cmd_scout)

    p_track = sub.add_parser("track", help="Bookmark series and check for new chapters")
    track_sub = p_track.add_subparsers(dest="action", required=True)

    t_add = track_sub.add_parser("add", help="Bookmark a series by URL")
    t_add.add_argument("url")
    t_add.add_argument("--title", default=None)
    t_add.add_argument("--site", default=None)

    t_rm = track_sub.add_parser("remove", help="Stop tracking a URL")
    t_rm.add_argument("url")

    track_sub.add_parser("list", help="List tracked series")

    t_check = track_sub.add_parser("check", help="Check all bookmarks for new chapters")
    t_check.add_argument("--no-desktop", action="store_true",
                         help="Don't attempt a desktop notification")
    t_check.add_argument("--no-markdown", action="store_true",
                         help="Don't write whats_new.md")
    t_check.add_argument("--always-notify", action="store_true",
                         help="Pop up a notification on every check, even if nothing changed")

    p_track.set_defaults(func=_cmd_track)

    p_info = sub.add_parser("info", help="Show current configuration")
    p_info.set_defaults(func=_cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Apply verbosity: the --verbose flag overrides the config/.env default.
    if getattr(args, "verbose", False):
        set_verbose(True)
    else:
        set_verbose(get_settings().verbose)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())