# AEGIS — Agentic Engine for Gathering, Intelligence & Scraping

> An agentic-AI pipeline that automates large-scale web scraping, AI-powered data
> extraction, and local file management — plus **Jarvis**, a tool-using AI
> assistant that runs in your terminal.

AEGIS is built around one idea: a language model that *acts*. Instead of
hard-coding a scraping script, AEGIS gives an LLM a set of tools (scrape pages,
read/write files, take notes) and lets it plan and execute multi-step tasks on
its own — the core pattern behind modern agentic AI.

It runs **100% free and offline** by default using a local model via
[Ollama](https://ollama.com), and switches to the **Anthropic Claude API** with
a single line of config.

---

## Highlights

- **Agentic loop** — a model that reasons, calls tools, observes results, and
  repeats until the task is done (`src/aegis/agents/agent.py`).
- **Swappable LLM backend** — clean `LLMProvider` interface with two
  implementations (Ollama and Claude); choose via one env var.
- **Recursive crawler** — breadth-first crawl with depth limits, domain
  restriction, dedupe, and a hard page cap (`src/aegis/scraping/crawler.py`).
- **Resumable jobs + scheduler** — save a scrape config as a job, run it in
  batches, resume after interruption (it skips completed URLs), and re-run it on
  an interval (`src/aegis/scraping/jobs.py`, `scheduler.py`).
- **Polite, large-scale scraping** — concurrent fetching with `robots.txt`
  compliance, per-host rate limiting, and exponential-backoff retries.
- **Generative AI extraction & summaries** — turn messy page text into
  structured JSON, and have the LLM write a summary report of a whole crawl.
- **Markdown / Excel / JSON / JSONL / CSV export** — results saved to
  timestamped runs; Excel sheets get a formatted header row.
- **SeriesScout** — a focused discovery feature *built on* the core pipeline:
  scrapes series sites (NovelUpdates, likemanga, comichaven, fanfiction) for new
  titles by tag/keyword and uses the AI to filter by a plain-English trait, e.g.
  "protagonist uses a bow". When a title/synopsis doesn't reveal the trait it
  reports "unknown" instead of guessing (`src/aegis/seriesscout/`).
- **Chapter-update tracker** — bookmark comics/series (by command or by asking
  Jarvis), then check them: it reports the current latest chapter for every
  tracked series and fires a Windows desktop pop-up when a series' latest
  chapter changes (use `--always-notify` to pop up on every check, or
  `--no-desktop` to silence it). Also writes a `whats_new.md`
  (`src/aegis/tracker/`). Desktop pop-ups need `pip install -e ".[notify]"`.
- **Jarvis assistant** — a conversational CLI assistant with 18 tools: scrape,
  crawl, discover-series, track-series, check-updates, web search, weather, file
  read/list, notes, a to-do list, file summarisation, text stats, and time.
  Optional voice I/O.
- **Tested** — a `pytest` suite covering parsing, storage, Excel export, the
  agent loop, the tool registry, the fetcher, the crawler, reporting, jobs,
  the scheduler, and the web tools (HTTP and LLM mocked, no network needed).

---

## Architecture

```
                 ┌──────────────────────────┐
   you ─────────▶│   CLI  (aegis ...)        │
                 └────────────┬──────────────┘
              scrape          │          assistant
        ┌───────────────┐     │     ┌──────────────────┐
        │ Scrape        │     │     │ Jarvis (Agent)   │
        │ pipeline      │     │     │  reason→act→obs  │
        └──────┬────────┘     │     └────────┬─────────┘
               │              │              │ calls tools
   ┌───────────▼───┐   ┌──────▼──────┐  ┌────▼─────────┐
   │ Fetcher       │   │ LLM Provider│  │ Tool Registry│
   │ (httpx +      │   │  (interface)│  │ scrape/files │
   │ robots + rate)│   └──────┬──────┘  │ notes/time   │
   └───────┬───────┘          │         └──────────────┘
           │           ┌──────┴───────┐
   ┌───────▼──────┐    │              │
   │ HTML Parser  │  Ollama         Claude
   │ (bs4/lxml)   │  (local)        (API)
   └───────┬──────┘
   ┌───────▼──────┐
   │ Storage      │  JSON / JSONL / CSV in data/output/
   └──────────────┘
```

Each layer is independent and unit-tested. The `LLMProvider` abstraction is the
key design decision: the scraping pipeline and the assistant never know or care
which model is behind them.

---

## Quick start

```bash
# 1. Install (editable, with dev tools)
pip install -e ".[dev]"

# 2a. Default: free local model
#     Install Ollama from https://ollama.com, then:
ollama pull llama3.1

# 2b. Or use Claude instead — set in .env:
#     AEGIS_LLM_BACKEND=claude
#     AEGIS_ANTHROPIC_API_KEY=sk-ant-...
#     (and: pip install -e ".[claude]")

# 3. Check your config
aegis info

# 4. Scrape with AI extraction
aegis scrape https://news.ycombinator.com --extract "Extract the page title and the top story headline" --name hn

# 4b. Crawl a site (follow links) and get an AI-written report
aegis crawl https://example.com --depth 2 --max-pages 20 --summarize --name demo

# 4c. Resumable jobs: create once, run in batches, resume any time
aegis job create newsjob https://example.com/a https://example.com/b
aegis job run newsjob --batch-size 1     # process 1, leaves the rest pending
aegis job status newsjob                 # see progress
aegis job run newsjob                     # finish the rest
# Re-run automatically every 5 minutes until complete:
aegis job schedule newsjob --interval 300

# 5. Talk to Jarvis
aegis assistant

# 6. SeriesScout: find new series matching a trait, across sites
aegis scout "main protagonist uses a bow" --site comichaven --tag bow --include-unknown
#   ...or just ask Jarvis: "find new manhwa where the hero uses a bow"

# 7. Track comics for new chapters (desktop pop-up on changes)
#    For the pop-up:  pip install -e ".[notify]"
aegis track add https://comichaven.net/manga/some-series/ --title "Some Series"
aegis track list
aegis track check        # shows latest chapter per series + pops up on changes
```

Example Jarvis session:

```
You: scrape https://example.com and tell me the page title
Jarvis: I scraped 1 page successfully and saved the results to
        data/output/scrape-20260523-101500/. The page title is "Example Domain".
You: add a note to review it tomorrow
Jarvis: Saved your note.
```

---

## Configuration

All settings come from environment variables (or a `.env` file). Copy the
template and edit:

```bash
cp .env.example .env
```

| Variable | Default | Meaning |
|---|---|---|
| `AEGIS_LLM_BACKEND` | `ollama` | `ollama` (local) or `claude` (API) |
| `AEGIS_OLLAMA_MODEL` | `llama3.1` | local model name |
| `AEGIS_CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model string |
| `AEGIS_ANTHROPIC_API_KEY` | *(empty)* | required for the Claude backend |
| `AEGIS_REQUEST_DELAY_SECONDS` | `1.0` | min delay between hits to one host |
| `AEGIS_MAX_CONCURRENCY` | `4` | parallel fetch workers |
| `AEGIS_RESPECT_ROBOTS` | `true` | obey `robots.txt` |
| `AEGIS_OUTPUT_DIR` | `data/output` | where results are written |

---

## Running the tests

```bash
pytest -v
```

The suite mocks all network and LLM calls, so it runs fast and offline.

## A note on offline use

AEGIS runs fully offline by default — scraping, crawling, extraction, storage,
and the assistant all work with a local Ollama model. Two assistant tools are
the exception and need the internet: `web_search` (DuckDuckGo) and `weather`
(Open-Meteo). Both are **keyless** and fail gracefully with a friendly message
when you're offline, so nothing crashes.

## Scheduling in production (Windows Task Scheduler)

The built-in `aegis job schedule` command runs an in-process loop — great for a
demo or a session you keep open. For true "set it and forget it" scheduling that
survives reboots, wire a single job run into Windows Task Scheduler:

1. Open **Task Scheduler** ▸ **Create Basic Task**.
2. Name it (e.g. "AEGIS news crawl"), choose a trigger (e.g. Daily).
3. Action: **Start a program**.
   - Program/script: the Python in your venv, e.g.
     `C:\path\to\aegis\.venv\Scripts\python.exe`
   - Arguments: `-m aegis.cli job run newsjob`
   - Start in: `C:\path\to\aegis`
4. Finish. Because jobs are resumable, each scheduled run just picks up whatever
   is still pending.

---

## Tech stack

Python 3.10+ · httpx · BeautifulSoup/lxml · pydantic-settings · tenacity ·
Rich · pytest/respx · Ollama · Anthropic Claude API.

## What I learned / what this demonstrates

- Designing a provider abstraction so components are swappable and testable.
- Implementing an agentic tool-calling loop from first principles.
- Writing an ethical, production-minded scraper (robots, rate limits, retries).
- Layering a focused feature (SeriesScout) on top of generic infrastructure,
  with site adapters whose selectors are isolated for easy maintenance.
- Structuring a real Python package with a CLI, typed settings, and a test suite.

## License

MIT — see `LICENSE`.
