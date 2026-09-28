# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal accountability system on Windows: tracks app/website usage, tracks goals, and shows both in a local GUI. Each subfolder has its own README; `monitoring_system/` also has its own CLAUDE.md.

- `monitoring_system/` — the activity tracker (foreground app + browser-extension URL → CSVs). See `monitoring_system/CLAUDE.md`.
- `goal_system/` — goal tracking (`goals.py`).
- `gui/app.py` — local GUI (goals home, goal history, monitoring summaries). Run via `RUN_GUI.py`.
- `computer_app/` — tray app (`launcher.py`) that runs the tracker in the background at login and opens the GUI.
- `RUN_ME.py` — runs the tracker in a terminal for testing (exits if the tray already runs it).
- `server/` (Pi API) and `phone_app/` (Expo) — **paused, see below**.

## Current scope: everything is local

The Pi server (`server/`) and phone app (`phone_app/`) are **paused**. Don't build on, fix, or wire new features into them unless asked. `monitoring_system/Api_Sync.py` still exists but stays inert without `client_config.json`; new features should work fully locally on Windows.

The phone is still reached one way: **Pushover push notifications** (`monitoring_system/Push_Notifier.py`), not the phone app.

## Secrets — never expose

1. **Pushover credentials** (API token / user key) live in `ALL_CODE/secrets/Push_Notification_SECRETS.txt`, outside the repo. Never copy them into code, comments, docs, logs, commit messages, or chat output. Code must read them from that file at runtime and degrade silently if it's missing.
2. **The `"Blocked Content"` section of `monitoring_system/data/Categorizing_Items.json` is treated like an API key.** Never write any app or website from that section into code, comments, docs, commit messages, test data, or chat output. When an example is needed, use an entry that is *not* blocked (e.g. a game or work app from another category). Code must only ever reference the category by its key (`Config.BLOCKED_CATEGORY`) and load the entries at runtime.
   - **Exception:** the GUI may *display* blocked entries at runtime (e.g. monitoring rows highlighted with `COLOR_BLOCKED_BG` in `gui/app.py`) — that's data shown on screen, not text written into source.
   - `monitoring_system/data/` is gitignored; keep it that way.
