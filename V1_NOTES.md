### post build, things to test, bugs, v2 notes

# notes
- ai key only lives in the pi
- all 7 ai interactions are "skills"
- todo list generation is NOT a cron job, either app opening triggers it
- monitoring system
    - pushes every session end duration to the server as a live upsert. still writes to csv files as a local raw log
- computer app
    - (2026-09-27, scope is now goal system + monitoring system only, no Pi/phone) tray launcher (`computer_app/launcher.py`) starts at login, runs the tracker, left-click opens the tkinter gui (`gui/app.py`). one gui window max, closing it doesn't stop monitoring, crashes show a popup. the old reminder polling + pywebview dashboard were Pi-only and are no longer used
- phone app
    - expo react native app with idental gui 

# todo
- move secrets to a more secure system. right now if the files are accidently removed from gitignore then they'd be pushed to the public github. api key, token, unicorn server (x.x.x.x). this is clicnet_config and server/config.
- minimize resource usage
- pick a host id, it's just x.x.x.x right now
- get a gemma key
- test loading teh expo app on phone
- untested: the tray/pywebview apps with their deps actually installed, the phone app on a device, and real Gemma calls (no key present — everything runs with a visible "[AI disabled]" placeholder until you add one).
    - does the app appear in windows tray
    - does it start at startup
    - hows the app and computer dashboard look?
- for the phone and computer common things I can probably make like an error class, maybe a transition class (for between screens or something)... like what did tmobile do for this?
- hows the database schema holding up?
- lower the write load from monitoring system. right now I think it pushes every session end to the pi, that means every update goes to the pi since only session ends are logged. let's change that to every few minutes to reduce write load (check if this actually matters). if I did that I'd have to have some way to know what didn't get written if the computer suddenly shuts down and restarts
    - rename csv files to backups since that's what they are now

# v2
- phone and desktop notifications if you haven't opened the app that day


======================================================================================================



# V1 — what got built, every decision I made, and what's on you

> **Historical (2026-09-27):** this report was written when the Pi server and phone app were in
> scope. They're parked now; the tray app runs the tracker and opens the local tkinter gui instead
> of the pywebview dashboard, and there are no reminder toasts. See `computer_app/README.md`.

V1 is complete and functional: the Pi API server, the tracker→server activity sync, the
Windows tray + dashboard app, and the Expo iPhone app. This file is the "tell me
everything" report you asked for.

## the 30-second map

```
phone_app/      Expo React Native app (Home, Chat, Tasks, Goals, Settings)
computer_app/   Windows tray (runs the tracker) + pywebview dashboard (same 5 areas)
server/         FastAPI + sqlite + the Gemma key. Runs on the Pi. The ONLY thing that touches the DB.
monitoring_system/  unchanged except: session-ends now also POST to the server (CSV stays as the local raw log)
```

Order of first-time setup: `server/README.md` → `computer_app/README.md` → `phone_app/README.md`. ================================================>>>>>>>>> here
Every piece degrades gracefully: no Gemma key → visible "[AI disabled]" placeholder replies;
no client_config.json → tracker runs CSV-only like before; Pi unreachable → tracker events
queue on disk and flush later.

## what was verified vs. what wasn't

**Tested end-to-end (all passing):**
- 28-check API test: auth rejection, task CRUD + validation, todo generation +
  idempotency, completing items, goal creation/edit rules (edit bumps `_updated_at`,
  doesn't move checkin date), checkin snapshots + item replacement + date advance,
  soft-delete with reason via the delete skill, one-off restore, activity upsert
  summing, chat, reminders.
- Tracker sync round-trip against a live uvicorn server: offline events buffer to
  `data/pending_api_events.jsonl`, drain when the server is up, and UPSERT-sum into
  the right (app, website) day buckets.
- All python compiles; dashboard JS and all 11 phone-app files parse.

**Not tested live (no way to here):**
- `launcher.py`/`dashboard.py` with real pystray/pywebview installed (code compiles; deps aren't on this machine).
- The phone app on a device / Expo Go.
- Real Gemma calls (no API key configured). The full request path runs; only the actual model call is stubbed.

## decisions I made (things you didn't specify, or I changed)

1. **Gemma model id discrepancy — you should check this one.** Your prose says
   "gemma 4 31b-it" but the code snippet you pasted uses `gemma-4-26b-a4b-it`. I used
   the snippet's id as the default; it's one line in `server/config.json` to change.
2. **AI-disabled placeholder mode.** With no key configured, every AI reply is a visible
   `[AI disabled ...]` string instead of an error, so you can exercise every flow before
   touching Google AI Studio.
3. **Fixed AI tone for v1.** No annoyance scaler (per your "features not included"), so the
   persona is fixed: warm, concise, honest. Each skill carries a `uses_annoyance_scaler`
   flag as the wiring point for later — adding the scaler is one prompt-prefix function,
   not a redesign (`server/skills.py`).
4. **Skills implemented:** todo_narration, missed_yesterday, delete_task, delete_goal,
   goal_checkin, midday_checkin, zero_goals. All the v1-scoped ones from your notes.
5. **Server port 8734** (tracker's local extension server keeps 7834 — unrelated, unchanged).
6. **Goal check-in answers are structured + free-text.** The UI collects did-item-1/2
   toggles and optional replacement text alongside your reply; the server snapshots the
   *old* item text into `goal_checkins`, applies changes, advances `next_checkin_date`.
   The AI sees the structured choices in its closing-reply prompt.
7. **missed_yesterday only fires while `missed_reason IS NULL`**, so you're asked once per
   miss, not every time you open the app.
8. **One-off restore also deletes its old 'completed' instances** — otherwise a restored
   task would never reappear on the todo list (the generator skips one-offs that have
   ever been completed).
9. **Tracker sessions are bucketed under the day the session started.** Midnight rollover
   closes sessions within seconds of 00:00, so spillover is negligible.
10. **Tracker keeps writing CSVs exactly as before.** The API push is additive. This means
    a hard crash (power loss) loses that one dangling session on the server but the CSV
    summarizer still recovers it locally — known v1 asymmetry, see roadmap.
11. **Plain CSS instead of Tailwind** for the dashboard. Tailwind without a build step
    means a CDN `<script>`, i.e. the dashboard breaks offline. One handwritten dark theme
    (~90 lines) matches the phone app's colors. Say the word if you want Tailwind back
    with a proper build step.
12. **Tray "Quit" hard-exits** without closing the tracker session cleanly — safe because
    the CSV summarizer already heals missing end-markers on next start (that's your
    existing crash-recovery path doing its job).
13. **Reminders are Windows-only in v1.** The tray polls `/reminders/pending` every 5 min
    and toasts anything with a `time_of_day` inside the next 2 hours (matches your
    "remind at 7pm for a 9pm task" example). iOS push needs real push infra — roadmap.
14. **Auth exactly as your design doc:** one static bearer token, checked with
    `secrets.compare_digest`; the Gemma key exists only on the Pi.
15. **Dashboard opens as a separate process** from the tray (pywebview and pystray both
    demand the main thread; two processes is the clean fix).
16. **Expo SDK 53 pinned** in package.json. Version drift is normal in RN land — the
    README says to run `npx expo install --fix` after `npm install`, which fixes any
    mismatch automatically.
17. **`excused` instance status exists in the schema but no UI sets it yet** — kept from
    your schema for the future "legitimate reason, don't count it as a miss" flow.
18. **Prompt history caps at 10 rows** (`HISTORY_CAP` in skills.py) per your
    "only up to x goals to save tokens."

## creative liberty worth flagging

Your notes asked how "continue in chat" carries context over. Implemented as: the client
keeps the 1-shot transcript in memory, and the Chat screen just sends the whole transcript
to `/chat` on every message (the server is 100% stateless about conversations). This
matches your answer — close the app and the conversation is gone forever, nothing stored.

## TODO list that depends on YOUR decisions

- [ ] **Confirm the Gemma model id** (31b vs 26b, decision #1).
- [ ] **Buy/choose the Pi hardware setup.** Your notes say Pi 3 B+ with "1GB storage" —
      the 3 B+ has no onboard storage, so that's presumably the SD card. Strong
      recommendation from your own notes: put the DB on a USB stick (`db_path` in
      server/config.json) and keep the nightly `.backup` cron (both in server/README.md).
- [ ] **Set up tailscale** on Pi + PC + iPhone (nothing in the code assumes it, any
      reachable IP works, but tailscale is the security story).
- [ ] **Weekly re-sign vs $99/year** for the iPhone install (phone_app/README.md lays out both).
- [ ] **zero_goals trigger policy:** the skill exists but nothing auto-fires it yet.
      Options: apps check "no active goals for 30 days" on open (client-side like
      everything else), or drop it from v1. Your call.
- [ ] **"You haven't opened the app today" notification** (from v1_design decisions):
      needs a pusher. The tray app could poll and toast it on Windows; phone needs push
      infra. Didn't build either — decide where you want it first.

## suggested next steps (no decisions needed, just work)

1. Real-device pass: install server deps on the Pi, run `install_startup.ps1` on the PC,
   do one full day with real data.
2. Get a Gemma key and tune the skill prompts against real replies (they're all in one
   place, `server/skills.py`).
3. Roadmap candidates in rough order of leverage: annoyance scaler (the hook is ready),
   server-side crash recovery for the one-dangling-session gap (have the tracker sweep
   unsynced CSV summaries into `/activity` on startup), iOS reminders, then the
   receipts/app-avoidance skills from your notes.



# me: getting the pi working
- raspberry pi 3 b+
- download raspberry pi imager (this can get the os)
- from the imager, download the raspberry pi os lite (64 bit)
- put the database on a usb drive (sd cards wear out too fast under sustiained small writes)

right now I cant' write the os to my sd card because it errors out at like 70% and says the card might be damgaed
- haven't tried nathans card

pressure plate system
