# SETUP — Baby-step guide (Windows)

This walks you through running AEGIS from a completely fresh start. You said you
already have **Python, Git, and VS Code** installed — perfect. Follow each step
in order.

> Throughout, lines starting with `>` are commands you type into the terminal.

---

## Step 0 — Open the project in VS Code

1. Put the `aegis` folder somewhere easy, e.g. `C:\Users\YOU\projects\aegis`.
2. Open VS Code → **File ▸ Open Folder…** → select the `aegis` folder.
3. Open the integrated terminal: **Terminal ▸ New Terminal** (it opens
   PowerShell by default).

Check Python is visible:

```powershell
> python --version
```

You should see `Python 3.10` or newer. If you see an error, your Python isn't on
PATH — reinstall Python and tick "Add Python to PATH".

---

## Step 1 — Create a virtual environment

A virtual environment keeps this project's packages separate from the rest of
your system. From inside the `aegis` folder:

```powershell
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`.

> **If you get a red error** about "running scripts is disabled", run this once,
> then retry the activate command:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

---

## Step 2 — Install the project

```powershell
> python -m pip install --upgrade pip
> pip install -e ".[dev]"
```

This installs AEGIS plus its scraping/testing tools. It may take a minute.

---

## Step 3 — Create your config file

```powershell
> Copy-Item .env.example .env
```

Open `.env` in VS Code. For the **free, offline** path, leave
`AEGIS_LLM_BACKEND=ollama`. Save the file.

---

## Step 4a — The free, offline brain (Ollama)

1. Download and install Ollama from <https://ollama.com> (Windows installer).
2. After it installs, open a **new** terminal and run:
   ```powershell
   > ollama pull llama3.1
   ```
   This downloads the model (a few GB — one time only).
3. Ollama runs in the background automatically. That's it.

## Step 4b — (Optional) Use Claude instead

If you'd rather use Anthropic's Claude API:

1. Get an API key at <https://console.anthropic.com>.
2. In `.env`, set:
   ```
   AEGIS_LLM_BACKEND=claude
   AEGIS_ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```
3. Install the Claude client:
   ```powershell
   > pip install -e ".[claude]"
   ```

> Keep your API key secret. `.env` is already in `.gitignore`, so it will not be
> committed to Git.

---

## Step 5 — Verify everything

```powershell
> aegis info
```

You should see your configuration printed. Then run the tests:

```powershell
> pytest -v
```

All tests should pass. (They don't need the internet or a running model.)

---

## Step 6 — Use it!

Scrape a page and have the AI pull out structured fields:

```powershell
> aegis scrape https://example.com --extract "Extract the page title and any heading" --name first-run
```

Look in `data\output\` — you'll find a timestamped folder with `.json`, `.csv`,
and `.xlsx` results.

Crawl a whole site and get an AI-written Markdown report:

```powershell
> aegis crawl https://example.com --depth 1 --summarize --name demo
```

Create a resumable job and run it in batches (resume any time — it skips what's
already done):

```powershell
> aegis job create demojob https://example.com https://example.org
> aegis job run demojob --batch-size 1
> aegis job status demojob
> aegis job run demojob
```

Start the assistant:

```powershell
> aegis assistant
```

Type things like:
- `what time is it?`
- `scrape https://example.com and tell me the title`
- `search the web for python tutorials` (needs internet)
- `what's the weather in Tokyo?` (needs internet)
- `add a task to finish my portfolio` / `show my to-do list`
- `add a note to review this later` / `list my notes`
- type `exit` to quit.

### (Optional) Voice mode

```powershell
> pip install -e ".[voice]"
> aegis assistant --voice
```

Speak after the "Listening..." prompt. If your mic isn't set up, it falls back
to text automatically.

---

## Step 7 — Put it on GitHub (for your resume)

```powershell
> git init
> git add .
> git commit -m "Initial commit: AEGIS agentic scraping + AI assistant"
```

Then create an empty repo on GitHub and follow its "push an existing repository"
instructions. Because `.env` is gitignored, your secrets stay local.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `aegis` not recognized | Make sure `(.venv)` is active; re-run `pip install -e .` |
| "Could not reach Ollama" | Is Ollama installed and the model pulled? Try `ollama list` |
| Claude error about API key | Check `AEGIS_ANTHROPIC_API_KEY` in `.env` |
| Scraper returns "blocked by robots.txt" | That site disallows bots; this is expected and correct behaviour |
| Voice mode errors | Voice is optional; it needs a working microphone and the `[voice]` extra |
