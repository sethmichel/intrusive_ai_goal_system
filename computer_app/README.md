# computer_app (Windows)

The Windows side of v1: a tray app that runs the activity tracker in the
background, shows task-time reminders as toasts, and opens a dashboard window
on demand. The dashboard is local HTML rendered by pywebview (Edge WebView2 —
preinstalled on Win 10/11); everything it shows comes from the Pi's REST API,
the exact same contract the phone app uses.

## setup

```powershell
pip install -r requirements.txt

# repo root: copy the client config and fill in your Pi's tailscale IP + the api_token
copy ..\client_config.example.json ..\client_config.json

python launcher.py          # tray icon appears; tracker starts in the background
```

Tray menu: **Open Dashboard** (also the default double-click action) / **Quit**.

Dashboard tabs: Today (todo + missed-yesterday AI conversation + goal
check-ins), Tasks (add/delete — deleting means justifying it to the AI),
Goals, Activity (live screen time from the tracker), Chat.

The browser extension for website tracking is unchanged — see
`../monitoring_system/extension/HOW_TO_INSTALL.md`.

## run at startup

```powershell
.\install_startup.ps1
```

Creates a shell:startup shortcut running `pythonw launcher.py` (no console
window). Logs go to `computer_app/launcher.log` when running windowless.

## dev notes

- `ui/index.html` also works in a plain browser (it will prompt for server
  url/token and stash them in localStorage) — handy for UI work without pywebview.
- If `client_config.json` is missing, the tracker still runs CSV-only and the
  dashboard will show a "can't reach server" card.
