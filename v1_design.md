notes-structuring_ideas.md has accurate info
readme.md also has accurate info but is more dated than notes-structuring_ideas

# feature list
- monitoring system
    - always on tracking system that monitors all exe file in focus on the computer and their durations. if it's a web browser then it uses the browser extension to get the website name. this creates a log of exactly how long the user spends on apps and websites and that data can be used throughout the app.

- phone app
    - screens
        - home
            - shows todays todo list
        
        - ai chat
            - a normal chat window that connects to your chosen ai that you provided the api key for. In 1 shot ai conversations, the user can select to move to this chat and the context should carry over (TODO: how does it carry over? do we have the ai summarize the chat and give it to itself, or can the system move the conversation over to this screen?)
        
        - scheduled tasks
            - routines, 1 off todo items. set name, due date, frequenct... I think it's described in the other docs
        
        - long term goals
            - described in other docs


# features not included
- annoyance scaler  
    - we'll do this after everything is setup since it's pretty precise
- email monitoring
- smart plugs
- kanban integration
- github tracking
- leetcode tracking
- ios app blocking
- Pi as sole data store, no backup story. Writing to SQLite on every focus-change event is a lot of small writes — fine for a Pi CPU-wise, but SD cards wear out under sustained write load, and if it dies you lose the whole tracker + tasks + goals history. Worth at least a nightly sqlite3 .backup to another disk/cloud, or using a USB SSD instead of the SD card for the DB file itself.
- browser extension is done and tested. but right now the user has to load it in the browser themselves. I'll investigate this more in a future update
- I've only said 5 rounds of iterations as a random number, I'll improve this over time is what I mean. I'll design the roadmap after I have a working v1 so I can understand that state of things better


# how do the phone app and computer app talk to each other?
- option 1: rest + tailscale + pi
    - Run a lightweight REST API (FastAPI, since your monitoring system is already Python) as a background service on whichever machine holds the SQLite file — a Raspberry Pi/NAS if you want it always-on independent of your daily driver sleeping. Both apps talk only to this API, never the raw file. Put that machine on a Tailscale (or plain WireGuard) network so your phone reaches it from anywhere with zero open ports and zero public attack surface — nothing internet-facing exists for someone to attack, since the API is only reachable from devices you've explicitly joined to your own private mesh. This directly satisfies the "very secure" requirement almost for free, and it's a well-trodden pattern for exactly this kind of personal-data self-hosted project.
    - components and design
        - raspberry pi zero 2 w ($30). runs linux, sqlite, tailscale, doesn't need soldering. you can also look at orange pi zero 2/3, radxa zero, banana pi. or dell wyse 3040/5060, these are made to always run in offices for stuff. or an old phone running termux (android)
        - really I need a always on linux box to host a db, api, tailscale. the phone and computer are clients to it


# database design (v1, sqlite)
NOT BUILT YET - for review only.

Scope = only what's in the v1 feature list above: monitoring system, home/todo, ai chat, scheduled + one-off tasks, long term goals.
Explicitly no tables for: annoyance scaler, email, smart plugs, kanban, github tracking, leetcode, ios app blocking. Those get their own tables when they're actually built, not reserved space now.

Two decisions this design leans on:
1. **Single writer.** Per the "rest + tailscale + pi" architecture above, the phone and computer are both just HTTP clients of one API in front of one sqlite file. No offline multi-writer merge to support, so plain `INTEGER PRIMARY KEY` (sqlite rowid) is enough — no UUIDs.
2. **UTC in, local date out.** Every timestamp column is stored UTC. "Today", "missed yesterday", and the goal checkin cadence all depend on a day boundary, so `settings.timezone` is the one place that gets defined, and the app computes local dates from it at query time. This was called out as a "later feature" in the original README but it's cheap to do now and painful to retrofit.

```sql
-- single-row config. no email/leetcode/github toggles in v1 since those features don't exist yet.
CREATE TABLE settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles',
    goal_checkin_interval_days INTEGER NOT NULL DEFAULT 14 CHECK (goal_checkin_interval_days BETWEEN 7 AND 21),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- one row per recurring scheduled task OR one-off task. same soft-delete/justify mechanic applies to both,
-- so they share a table instead of two near-duplicate ones.
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    task_type TEXT NOT NULL CHECK (task_type IN ('recurring', 'one_off')),
    name TEXT NOT NULL,
    importance TEXT NOT NULL CHECK (importance IN ('low', 'mid', 'high')),
    frequency_days INTEGER,      -- recurring only
    due_date TEXT,               -- one_off only
    time_of_day TEXT,            -- optional, for reminders, e.g. '19:00'
    reason TEXT,                 -- optional free text, e.g. "building key project for my resume"
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- soft delete: the row never goes away so the ai can reference "you deleted this before".
    -- no conversation is persisted -- deletion_reason is the only trace of that exchange, and
    -- it's enough for the ai to bring it up next time ("you deleted this before, saying: ...").
    deleted_at TEXT,
    deletion_reason TEXT
    -- app-level rule, not enforced by sqlite: recurring rows set frequency_days/null due_date,
    -- one_off rows set due_date/null frequency_days.
);

-- the per-day materialization of a task: "this task appeared on the todo list for this date."
-- this is what the daily todo, "missed yesterday", and streak/miss-frequency queries all read from.
CREATE TABLE task_instances (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    scheduled_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'missed', 'excused')),
    completed_at TEXT,
    missed_reason TEXT,          -- user's answer when the ai asks about a missed item
    reminded_at TEXT,            -- set once the time_of_day reminder fires, so it can't double-send
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (task_id, scheduled_date)
);

-- the 2 action items live directly on the goal, since "exactly 2, not 1, not 3" is already a
-- hardcoded product rule -- normalizing them into their own table would just be preserving
-- history nothing else reads. history of what the items *were* lives in goal_checkins below
-- (snapshotted at each checkin), not here -- these 2 columns are always "current."
CREATE TABLE long_term_goals (
    id INTEGER PRIMARY KEY,
    goal TEXT NOT NULL,
    blocking_reason TEXT,
    action_item_1 TEXT,
    action_item_1_updated_at TEXT,  -- set whenever action_item_1 changes; edits don't wait for a
                                    -- checkin, so the next checkin's ai prompt can say "you changed
                                    -- this recently" instead of treating it as unbroken continuity
    action_item_2 TEXT,
    action_item_2_updated_at TEXT,
    next_checkin_date TEXT NOT NULL,  -- editing an action item does NOT move this
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    deletion_reason TEXT
);

-- one row per 2-week checkin. snapshots the item text as it was *at that checkin* (action_item_1/2
-- on long_term_goals may have since changed) alongside whether the user says they did it. no
-- conversation transcript stored -- just the structured outcome the ai and later checkins need.
CREATE TABLE goal_checkins (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES long_term_goals(id),
    checkin_date TEXT NOT NULL,
    action_item_1_text TEXT,
    action_item_1_done INTEGER CHECK (action_item_1_done IN (0, 1)),
    action_item_2_text TEXT,
    action_item_2_done INTEGER CHECK (action_item_2_done IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- written directly by the computer tracker (via the pi API) instead of monitoring_system's current
-- CSV-then-batch-summarize approach -- one row per (date, app-or-website) bucket, same bucketing
-- as today: native apps key on (app, ''), browser tabs key on ('', hostname). but instead of
-- appending once at day's end, every session-end event (the same app/site-focus-change the tracker
-- already detects every ~3s) does an UPSERT that adds that session's seconds onto the existing
-- bucket for today. this keeps today's totals close to real time, which matters once app/site
-- blocking is built -- that decision needs "how long today," not "how long as of last night."
-- the tracker can keep its local raw per-event log as a crash-recovery/offline-buffer detail;
-- that's internal to the tracker and doesn't change this shared table.
CREATE TABLE activity_daily (
    id INTEGER PRIMARY KEY,
    activity_date TEXT NOT NULL,
    app TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER NOT NULL,
    url TEXT,
    UNIQUE (activity_date, app, website)
);

CREATE INDEX idx_task_instances_date ON task_instances(scheduled_date);
CREATE INDEX idx_tasks_active ON tasks(deleted_at);
CREATE INDEX idx_activity_daily_date ON activity_daily(activity_date);
```

6 tables total: `settings`, `tasks`, `task_instances`, `long_term_goals`, `goal_checkins`, `activity_daily`. No conversation/message tables — nothing about the ai chat itself is persisted, only the structured outcomes (a reason, a bool, a status) that later prompts and history queries actually need.

## how the pieces answer the v1 features
- **daily todo list**: `task_instances` where `scheduled_date` = local-today (derived from `settings.timezone`). Materialized once per day (cron/first-open) from `tasks`: recurring tasks due by `frequency_days` since their last instance, one-off tasks whose `due_date` is today or past-and-not-done.
- **missed yesterday / "why didn't you"**: `task_instances` where `scheduled_date` = local-yesterday and `status = 'missed'`; the ai asks about it in a 1-shot conversation that is not persisted, but the user's answer gets written straight to `missed_reason` on that instance so future prompts/history queries can still see it.
- **due in next 3 days**: one-off `tasks.due_date` in range; recurring tasks projected from `frequency_days` without materializing instances early (avoids stale rows if the task gets edited before it's actually due).
- **deleting a scheduled task / goal**: the ai asks why, the exchange itself isn't stored, but `tasks.deleted_at`/`deletion_reason` (or the `long_term_goals` equivalent) get set once the ai responds. Nothing is ever hard-deleted, so "have they deleted this exact task before, and why" is just a query.
- **one-off task restore**: clear `deleted_at`, ask the user for a new `due_date`. No justification exchange for one-offs — only recurring tasks and long-term goals require that, per the README.
- **long term goal checkins**: every 2 weeks (interval configurable via `settings.goal_checkin_interval_days`), a `goal_checkins` row snapshots the 2 current action items' text plus whether the user says each was done; changing an item just overwrites `action_item_1`/`action_item_2` (and its `_updated_at`) on `long_term_goals` immediately, doesn't move `next_checkin_date`, and past checkin rows keep the old text. The next checkin's prompt checks `action_item_N_updated_at` against the prior checkin's `created_at` to flag "you changed this recently."
- **ai chat**: stateless — "continue in chat" just hands the same in-memory context to a free-form screen for that session. Nothing new to persist beyond what the 1-shot outcome already wrote to `missed_reason` / `deletion_reason` / `goal_checkins`.
- **monitoring system numbers on home screen**: read straight off `activity_daily`, which is now current to the last session-end event rather than last night.

## decisions (resolved)
1. **Todo generation trigger**: no cron. Either app (phone foreground, or the computer tracker at startup) checks on open whether `task_instances` exist for local-today; if not, it generates them via SQL against `tasks` and runs the ai narration. Midnight rollover while a device is actively in use is handled the same way — detect the local date changed, generate then, or on next open if that's not caught live. Both apps push a "you haven't opened this today" notification, itself just derived from "no task_instances row yet for today" past some time threshold, not a stored flag.
2. **monitoring_system migration**: moves off CSV entirely for the shared data — the tracker writes straight to `activity_daily` on the pi (via the API) on every session-end event, UPSERTing the running total, so blocking decisions later can read "today's total" near-real-time instead of from last night's batch. This finally resolves the "needs to move to a sql database" TODO in `monitoring_system/README.md`.
3. **Action item edits**: allowed anytime, don't move `next_checkin_date`. Tracked via the two `_updated_at` columns above so the next checkin's ai conversation can call out a recent change.



### app designs
- we should assume these phone/computer apps will go through 5 versions of updates. so the tools used to make them need to be picked such that i can improve it 5 times (a high ceiling) instead of simpler but limited tools.

# computer
- windows app that starts at startup and is a background process but has a gui if opened.
    - option: a shortcut in shell:startup (or a Task Scheduler entry set to run at logon) launches a small launcher script that starts the tracker headless and creates a system tray icon via pystray (menu: "Open Dashboard" / "Quit").

- GUI: pywebview — it opens a native window that renders local HTML/CSS/JS (no Electron bloat, no separate runtime), and that HTML just calls the Pi's REST API with fetch/requests. This means the computer GUI, the future phone GUI, and the API are all speaking the exact same contract from day one, and you're writing HTML instead of learning a widget toolkit (Tkinter/Qt) for basic screens like "today's todo.". however, pywebview still needs a bundled webview runtime (uses Edge WebView2 on Windows, which is preinstalled on Win10/11). we can use tailwind css for styling. 
    - can't use tkinter. it can't be made to look nice, you'd need something else. most modern looking apps are just html, css, js running ina  windows shell. css makes the modern look

# ios app
- the real constraint isn't design, it's Apple's code-signing: any native app on a real iPhone must be signed by Xcode, which only runs on macOS. Options without owning a Mac:

- apple is obnoxius with getting apps running on ios. I can't just load the app over usb, it still needs a xcode signature. 
- we'll use this expo workaround and just refresh the signature weekly
    1. Build the app with Expo (React Native) — write it on Windows like any JS project.
    2. Run eas build --platform ios — Expo's cloud service (EAS Build) compiles and signs it on their macOS build farm. You register as a free Apple ID ("personal team"), no paid Developer Program needed.
    3. Install the resulting .ipa with Sideloadly (a Windows app) — plug your iPhone in over USB, point it at the .ipa, it signs with your free Apple ID and installs directly. No App Store, no review process.
    4. The catch: a free Apple ID's signature expires every 7 days, so you'd reconnect via USB and resign weekly (or use AltStore/SideStore, which can auto-refresh over your home wifi without a PC). Paying the $99/year Developer Program removes that expiry entirely and is genuinely worth it if this becomes your daily-driver phone app — it's not "Apple's annoying rules," it's the one legitimate way to make the 7-day nag disappear.


# misc questions
1. Authentication issues
    - If you reused the AI key as the credential for calling your own Pi's REST API, you'd be spreading a billable, provider-side secret across every client (phone + computer) for a job it wasn't meant for — and if any client got compromised or that credential leaked some other way, someone could rack up charges on your AI account, not just poke at your task list.
        - solution: 
            - the AI key should live only on the Pi, never sent to or stored on phone/computer. Since the Pi is already the single backend all clients talk to, have it be the one that calls out to the LLM provider — phone/computer just hit the Pi's /chat endpoint, and the Pi holds the provider key server-side. That also means if you ever swap providers or rotate the key, it's a one-place change.
            - Then, separately, the Pi's REST API itself needs some credential so that anyone who reaches it over the tailnet (or by mistake, if you ever misconfigure Tailscale ACLs or add another device) can't freely read/write your tasks and goals. Lightweight options, roughly in order of effort: Static bearer token — generate one random token yourself, put it in each client's config, check Authorization: Bearer <token> in FastAPI via a dependency. ~10 lines of code, zero moving parts, totally adequate for a single-user personal system.

2. Recurring task anchor ambiguity. frequency_days computes the next instance from "since their last instance" — but if a task is marked missed instead of completed, does the next occurrence count from the missed date or wait for eventual completion? Undefined today, and it'll either double-schedule or silently drift depending on which you pick.
    - ansewr: it computes the next instance from the from the last instance. marking it missed or completed doesn't change when the next occurance is

3. AI chat continuity is still an open TODO, but your "resolved decisions" section treats it as solved by "stateless, hand in-memory context over." That only works if the 1-shot and the chat screen are in the same running session. If the user closes the app and comes back later wanting to continue, there's nothing to continue from since no conversation is persisted. Worth deciding now whether you want short-lived (session-only, not permanent) conversation caching, or if "no carryover after close" is an acceptable v1 limitation.
    - answer: hmm, so we have misc ai 1 shot conversations around teh app (in different screens of the app), and we have a ai chat screen. a major purpose of the chat screen is that the user can push a button and move the conversation to the chat screen for a longer conversation (since 1 shot conversations are always ai -> user -> ai -> ends). if the user closes the app or cuts out of the conversation then consider that conversation done, there's no saving them so we can't load them in the chat screen. as for the user if they exit the 1 shot chat or end it, they must not want to continue it in the chat screen.



