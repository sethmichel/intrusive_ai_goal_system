### summary
The Computer Tracker
- Tracks users active window: polls win32 foreground window every x seconds, gets the process name.
- if the process is a browser: we need to ask the browser extension for the tab name. We treat websites as actual websites, not urls. so youtube includes all variations of the youtube url
- we only write a row when teh app or domain (website) change

The browser extension
- I think it POSTS the active tabs url every time there's a tab switch, same tab navigation (domain change only), and window focus change. posts to a http server
- this gives info to the computer tracker, it doesn't record data itself

Storage
- store data in csv files
    - daily-{date}.csv is the raw event log
    - main.csv: storage.summarize_daily_csv summarizes the daily csv such that each unique process and website only has 1 line. so it adds duplicates up


# exactly how computer apps are tracked
- Every 3s (`POLL_INTERVAL`), `Tracker.get_active_window()` calls `GetForegroundWindow()` -> `GetWindowThreadProcessId()` -> `OpenProcess()` -> `QueryFullProcessImageNameW()` (pure ctypes, no libs) to get the .exe name of whatever window has focus (e.g. `notepad.exe`).
- If that process is NOT in `KNOWN_BROWSERS`, it's treated as a native app: `new_app = process_name`, `new_url = ""`. new_url isn't for tracking in this case, it's a required variable
- The loop compares `(new_app, new_site)` to `(current_app, cur_site)` from the last poll (if it's not a browser this comparison is just new_app vs current_app). Only on a change does it call `write_daily_row()` to append a row to `data/daily-<date>.csv` (so "Notepad" open for an hour is one row, not 1200 rows).
- If the foreground window can't be read at all (`process_name` is None — e.g. screen locked), it writes an end-marker row (empty app/url) so the prior app's duration closes out, then keeps polling.
- Later, `Storage.summarize_daily_csv()` buckets every native-app row by `(app, "")` and sums durations — so "Notepad" is one bucket regardless of which file was open, matching the Target behavior section.
- URL for a computer app is just blank in storage. 

# exactly how browser websites are tracked
- The extension (`extension/src/background.js`) is what actually knows the URL — the tracker never reads browser internals directly, only the OS-level foreground process (which just says "chrome.exe", not what tab is open).
- `BROWSER_PROCESS` in `extension/src/background.js` is a `__BROWSER_PROCESS__` placeholder, not a real value — `extension/build_extension.py` stamps in the real value (`"chrome.exe"` / `"msedge.exe"` / `"brave.exe"`, matching `Tracker.py`'s `KNOWN_BROWSERS`) per browser when it generates `extension/build/<browser>/`. It can't be detected reliably at runtime because Brave's user agent deliberately mimics Chrome's.
- The extension POSTs `{url, browser}` to `http://127.0.0.1:7834` (fire-and-forget `fetch`, errors swallowed) on 3 triggers: `chrome.tabs.onActivated` (tab switch), `chrome.tabs.onUpdated` (same-tab navigation, but only if `extractDomain()` of the new URL differs from the tracked domain for that tab — so YouTube video-to-video within the same tab doesn't spam POSTs), and `chrome.windows.onFocusChanged` (switching back to a browser window).
- `Server.py`'s `_ExtensionHandler.do_POST` is the only endpoint. It parses the JSON body and stores the latest `(url, browser)` pair in lock-protected globals (`_latest_url`, `_latest_browser`) — no history, no per-tab tracking server-side, it's overwritten on every POST.
- Every poll (3s), if `Tracker.is_browser(process_name)` is true, `Computer_Tracker.py` calls `Server.get_latest_url(process_name)`, passing in the currently-foregrounded browser's process name. The server only returns the stored URL if `_latest_browser` matches `process_name` — otherwise it returns `None`, so a stale URL from a different browser never gets attributed to the one you just switched to. Note this is still decoupled from the poll otherwise: if the matching browser posted 2 seconds ago and hasn't posted since, the tracker just keeps reading that same value (expected — you're still on that tab).
- If `get_latest_url()` returns `None` (extension never posted anything, e.g. not installed/loaded, *or* you just switched to a browser whose extension hasn't posted its own URL yet), the tracker ends the current session and increments `no_ext_counter`; after 10 consecutive misses (30s) it fires a `winsound` beep to alert you the extension isn't running. In the browser-switch case this self-resolves within a poll or two once that browser's extension posts.
- `Tracker.is_new_tab_url()` filters out new-tab/blank pages (`chrome://newtab`, `about:blank`, etc.) so opening a new tab doesn't get logged as a "website."
- The URL gets stored as-is in `daily-<date>.csv`, but for aggregation `Storage.extract_website()` reduces it to just the hostname (stripping `www.`) via `urlparse` — that's what collapses every YouTube video URL into one `youtube.com` bucket in `main.csv`.

# exactly how the extension gets on the browser
- There's still no packaging or store listing — no `.crx`, no `update_url`/`key`. But there is now a build step: `extension/src/` is the single source of truth (`background.js` there has a `__BROWSER_PROCESS__` placeholder, not a real value), and `python extension/build_extension.py` generates `extension/build/chrome/`, `extension/build/brave/`, `extension/build/edge/` — each a self-contained, loadable folder with the placeholder replaced by the right value for that browser.
- Install is still manual per browser: open `brave://extensions` (or `chrome://extensions` / `edge://extensions`), enable Developer Mode, "Load unpacked", and point it at `extension/build/<browser>/`. You do this once per browser you want tracked (Chrome/Brave/Edge, per the stated Target behavior).
- Updating logic is now one command instead of hand-editing 3 files: change `extension/src/background.js`, rerun `build_extension.py`, then click the reload icon on the extension's card in each browser's extensions page (no need to remove/re-add or re-pick the folder).
- `extension/build/` is gitignored — it's generated output, not something to hand-edit or commit.
- supposidly the user has to turn on allow access to file urls in chromium browsers so the extension can read file url's opened in browser. however I didn't have to do this in brave (didn't see the toggle at all) — see `extension/HOW_TO_INSTALL.md`, this may be version/browser-dependent


## issues found (mostly resolved by the build script; residual gaps below)
- **Drift risk mostly eliminated**: the 3 build folders can no longer diverge by hand-edit, since they're regenerated from one source file. The remaining manual step is running the build script and clicking reload 3 times — still 3 touches, just no longer 3 places for a typo.
- **No incognito handling**, per the existing TODO — unpacked extensions are disabled in Incognito/private windows by default and the manifest doesn't set the `incognito` key or document the manual "Allow in Incognito" toggle.
- **Dev-mode nag**: since this will only ever be an unpacked, unsigned extension, Brave/Chrome/Edge show a "disable developer mode extensions" warning banner on every browser restart. Not a functional bug, but worth knowing since this is meant to run continuously in the background.
- **Install doc now exists**: `extension/HOW_TO_INSTALL.md` covers building, loading per-browser, the (maybe-not-needed) file URL toggle, and verifying it worked.

# how we'll continue tracking if the user enters private browsing mode

# exactly how storage works
daily csv is:       timestamp,app,url
- computer process: 2026-04-16T14:38:23.625197,cursor.exe,
- website:          2026-04-16T14:38:23.625197,chrome.exe,YouTube.com

let's say this is your usage data. how is it summarized?
timestamp,app,url
2026-07-02T15:20:27.980428,cursor.exe,
2026-07-02T15:20:33.982629,blank browser tab,
2026-07-02T15:20:36.985125,brave.exe,https://www.youtube.com/
2026-07-02T15:20:42.987959,blank browser tab,
2026-07-02T15:20:45.989209,brave.exe,https://www.youtube.com/
2026-07-02T15:21:06.991947,cursor.exe,
2026-07-02T15:22:22.010657,explorer.exe,
2026-07-02T15:22:25.011711,searchhost.exe,
2026-07-02T15:22:28.013218,steam.exe,
2026-07-02T15:22:34.014906,cursor.exe,
2026-07-02T15:22:40.016634,steamwebhelper.exe,
2026-07-02T15:22:52.019143,windowsterminal.exe,
2026-07-02T15:22:55.020843,steamwebhelper.exe,
2026-07-02T15:23:07.025152,slay the spire 2.exe,
2026-07-02T15:23:13.027245,cursor.exe,
2026-07-02T15:23:16.028223,slay the spire 2.exe,
2026-07-02T15:23:19.030031,steamwebhelper.exe,
2026-07-02T15:23:22.036403,windowsterminal.exe,
2026-07-02T15:23:28.043396,cursor.exe,
2026-07-02T15:23:46.047717,brave.exe,https://www.youtube.com/watch?v=7RqD2ClRUEc
2026-07-02T15:23:55.049792,cursor.exe,

the summarizing function is only called on a day that's already over. so if the user opens the app the next day it would summarize this example data. it looks at seconds between rows timestamps and makes main.csv. if a session crosses midnight then that day's csv ends and a new days csv starts. It would write this to main.csv: date,app,website,duration,url.
NOTE: browser new tabs are dropped. in the daily csv they appear as 2026-07-02T15:31:56.827087,blank browser tab, (labeled that way instead of a blank app so it's not confused with a crash/no-activity row; still dropped during summarization same as before)

# little details about how things really track
- what if you're swapping between 2 computer apps like cursor and the cmd?
    - each poll (every `POLL_INTERVAL` = 3s) just asks Windows which process currently has the foreground and compares it to the last recorded app. any time that differs, it writes a new daily-csv row (ending cursor's session, starting cmd's), so alt-tabbing between two native apps is tracked correctly and duration falls out of the gap between consecutive timestamps in `summarize_daily_csv()`.
    - the catch is granularity: since detection only happens on the 3s poll, not on the actual OS focus-change event, swaps faster than ~3s can be missed or misattributed — if you bounce between cursor and cmd twice within one 3s window, the tracker only sees whichever one happened to have focus at the moment it polled, and the row it writes will over/undercount accordingly.

- what if you have a long youtube video playing in a browser and you minimize that for an hour while you work on a computer app like cursor?
    - tldr: it only tracks the in focus app. so youtube would count until you change to cursor, then it's all cursor.
    - this is already handled correctly, and for the same reason as the cursor/cmd case above: the tracker only cares about which process has the *foreground*, not what's playing in the background. the moment you minimize the browser (or alt-tab to cursor), the next poll sees cursor.exe as the foreground process, that's a change from chrome.exe, so it writes a row for cursor and that row's timestamp is also what closes out the youtube.com session in `summarize_daily_csv()` (duration = gap between the youtube row and the next row).

- what if you have 2 browsers side by side and you're doing stuff in both?
    - when you swap browsers (alt tab or change focus) the tracker won't reuse browser A's last url for browser B. it'll treat browser B as "no signal yet" until browser B's extension posts its own url. that's a few seconds delay which is fine.

- what if you don't do anything for 1 hour?
    - it still polls what you're doing every x seconds like normal. we only record if the app/website changes (focus change). and only 1 row get's written to the daily csv for each change. the resource cost of this wasted effort is negligible, microseconds. we could correct this by tracking if the user does mouse or keyboard inputs, but that's a privacy breach. so we leave it as is.

- new blank tabs
    - these are logged in the daily csv files but ignored in the summary in main.csv. so it's dropped data in the end

- pdf/html... misc files
    - these get treated the same as websites
    - claude comment about this: extensions don't get file:// tab visibility just because `manifest.json` declares `"file:///*"` in `host_permissions` — Chrome/Brave/Edge still require you to flip "Allow access to file URLs" on the extension's card in `brave://extensions` (or `chrome://` / `edge://extensions`) with Developer Mode on. Without that toggle, `tab.url` is empty for local files and none of this fires. Untested end-to-end until that toggle is flipped and verified.

- what if it crashes?
    - the last known activity won't get an ending line written after it, but the summary feature will correct that and write a warning to the logs

- what happens across midnight if the user is using it?
    - it ends the activity for that day and starts it for the next day

- in v1 how do you enable private browsing tracking?
    - you have to give the extension permission in settings for that extension

# TODO
- this almost certinaly needs to be moved to a sql database. I'm just not sure if that's sqlite or pg

# done
- changed duration to hour:minute:second

### changes for V2
- security issue: right now the program doesn't authenticate incoming extension info
- add firefox support
- make the extension on the extension stores
- Productive vs. unproductive classification. The entire "wasted time" framing depends on categorizing apps/sites (work vs. distraction). There's no category mapping anywhere — main.csv just has raw uncategorized durations.
- Auto-start / background service. No Task Scheduler entry, no startup shortcut, no tray icon. You have to manually run python computer_tracker.py in a terminal every time.
- is there anyway to stream line the private mode browsing enabling? it's a pain to turn on right now
- disable the beep, it's only for debugging. probably shouldn't print warnings either
- Timestamps are naive local time. datetime.now() / date.today() throughout. Fine on one machine today, but for a data agent feeding a bigger system it's worth either (a) documenting "all times are machine-local, no tz" as part of the schema contract, or (b) storing UTC. DST fall-back can also produce a negative-duration session — currently silently dropped by the duration <= 0 guard (Storage.py:188), which is acceptable but undocumented.
- when making the summary file, right now it makes a temp file and builds the changes all once before writing to the actual file so it does all or nothing in case it crashes part way through. but if a truly unclean kill (e.g., power loss) happens during the write, the except block won't run and a stray .tmp file could be left in the data dir — harmless, but worth knowing since it's not cleaned up on next startup.
- the extension never stops: right now every postUrl call fires blind and just swallows the error via .catch(() => {}), so there's no state tracking whether the server is reachable. The clean fix is a small circuit-breaker: track consecutive failures in a module-level counter, and once it crosses a threshold (e.g. 2-3), skip firing POSTs entirely and instead probe periodically (via chrome.alarms, since MV3 service workers can't rely on setInterval surviving suspension) until one succeeds, then resume normal posting.
The tradeoff: since fetches to 127.0.0.1 fail near-instantly on connection-refused, the current "just eat the error" approach costs almost nothing performance-wise — the main win from adding this would be cutting console noise/failed network calls in dev tools, not fixing a real bug. Want me to implement the circuit-breaker, or is this more about confirming there's no side effect from posting to a dead server?