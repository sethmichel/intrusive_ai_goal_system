# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows-only, local RescueTime clone: tracks which app/website has focus and how long, storing results in CSV files. No GUI — this project is meant to be absorbed into a bigger project later that handles reporting/UI.

## Running it

```
python Computer_Tracker.py
```

Then run `python extension/build_extension.py` — this generates one loadable folder per browser under `extension/build/` (`chrome/`, `brave/`, `edge/`), each with `BROWSER_PROCESS` baked into `background.js` to match that browser. Load the matching `extension/build/<browser>/` folder unpacked in `brave://extensions` (or `chrome://extensions` / `edge://extensions`) with Developer Mode on, once per browser you want tracked. The extension POSTs the active tab's URL to `http://127.0.0.1:7834`; the tracker polls the OS every 3s for the foreground process.

Editing `extension/src/background.js` or `extension/src/manifest.json`? Rerun `build_extension.py`, then hit the reload icon on the extension's card in each browser's extensions page (no need to re-pick the folder).

No test suite or lint config exists in this repo; `extension/build_extension.py` is the only build step, and it's a plain string-substitution script.

## Architecture

Data flow: `extension/src/background.js` (built per-browser into `extension/build/<browser>/background.js`) → HTTP POST → `Server.py` (in-memory latest-URL store) → polled by `Computer_Tracker.py`'s main loop → written via `Storage.py` to CSV.

- **Computer_Tracker.py** — orchestrator/entry point. Polls the foreground window every `POLL_INTERVAL` (3s), compares against the previous app/site, and writes a new daily-CSV row only on change (not every poll). Also owns midnight rollover (closes out the previous day's session, summarizes the finished daily CSV, starts a new one) and a `winsound` beep alert if the browser extension hasn't POSTed a URL in 10 consecutive polls (extension likely not running/installed).
- **Tracker.py** — Win32 layer via `ctypes` (`GetForegroundWindow`, `QueryFullProcessImageNameW`, etc.), no external deps. Exposes `get_active_window()`, `is_browser()`, `is_new_tab_url()`, and the `KNOWN_BROWSERS` / `NEW_TAB_PATTERNS` constants. New-tab pages are filtered out so they don't get tracked as "activity."
- **Server.py** — minimal `http.server.HTTPServer` run on a background daemon thread. Only endpoint is `POST /` from the extension; holds just the single latest URL behind a lock, read via `get_latest_url()`.
- **Storage.py** — all CSV I/O, in `data/`:
  - `data/daily_activity_logs/Daily_Activity_Logs-<date>.csv` — raw event log for the current day (columns: `timestamp, app, url`). A row is written on every app/site change, plus an empty-app "end marker" row whenever tracking stops/pauses, so duration can be computed as `(next_row.timestamp - this_row.timestamp)`.
  - `data/Summarized_Activities.csv` — the aggregated result (columns: `date, app, website, duration, url`). `summarize_daily_csv()` walks a finished daily CSV pairwise, buckets by `(app, "")` for native apps or `("", website)` for browser tabs (using hostname only, so all YouTube videos collapse into one `youtube.com` bucket), sums durations per bucket, and appends one row per bucket to `Summarized_Activities.csv`. The daily CSV is kept on disk afterward (not deleted) as a raw log.
  - Old, not-today daily CSVs get swept into `Summarized_Activities.csv` on startup via `check_and_summarize_old_dailies()` (crash/restart recovery); it skips any date already present in `Summarized_Activities.csv` so kept daily logs aren't double-counted.
- **Api_Sync.py** — pushes each finished session's duration to the Pi API (`POST /activity`, an UPSERT that sums into that day's `(app, website)` bucket) with an on-disk jsonl queue for offline buffering. Config comes from `../client_config.json` (repo root, gitignored); if that's missing the tracker runs CSV-only exactly as before. urllib only — keeps this package's no-external-deps rule.
- **extension/** — Manifest V3 Chrome/Brave/Edge extension. `src/` holds the single source of truth (`background.js` has a `__BROWSER_PROCESS__` placeholder instead of a hardcoded value); `build_extension.py` stamps that placeholder into per-browser copies under `build/<browser>/` (gitignored). `background.js` posts the active tab URL on tab-switch, same-tab domain-changing navigation, and window-focus change (fire-and-forget fetch, errors swallowed). It does not record data itself — it's purely a URL reporter for `Server.py`.

## Known gotchas (see README.md TODO section for the full list)

- No idle detection yet — a tab/app left open accumulates duration indefinitely.
- Incognito/private windows: extensions are disabled there by default and this isn't handled or documented anywhere yet.
- No productive/unproductive category mapping — `main.csv` is raw uncategorized durations only.
- Hardcoded constants throughout (port `7834`, `POLL_INTERVAL = 3`) rather than a config file.
