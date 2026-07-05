# server (runs on the Raspberry Pi)

The single backend everything talks to: FastAPI + one SQLite file + the Gemma key.
The phone app, the Windows dashboard, and the computer tracker are all just HTTP
clients of this. Nothing else ever touches the DB file.

## setup (Pi 3 B+ running Raspberry Pi OS Lite, or any Linux box — also runs on Windows for dev)

```bash
cd server
python3 -m venv venv
source venv/bin/activate          # windows: venv\Scripts\activate
pip install -r requirements.txt

cp config.example.json config.json
python -c "import secrets; print(secrets.token_urlsafe(32))"   # -> paste as api_token
# paste your Gemma/Gemini key from https://aistudio.google.com as gemma_api_key
# (leave gemma_api_key empty to run with a visible "[AI disabled]" placeholder)

uvicorn main:app --host x.x.x.x --port 8734
```

Smoke test from another machine on the tailnet:

```
curl -H "Authorization: Bearer <api_token>" http://<pi-tailscale-ip>:8734/health
```

## run at boot (systemd)

`/etc/systemd/system/accountability.service`:

```ini
[Unit]
Description=accountability api
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/activity_tracker/server
ExecStart=/home/pi/activity_tracker/server/venv/bin/uvicorn main:app --host x.x.x.x --port 8734
Restart=always

[Install]
WantedBy=multi-user.target
```

Then `sudo systemctl enable --now accountability`.

## tailscale

Install tailscale on the Pi, your PC, and your phone; log all three into the same
tailnet. Clients use `http://<pi-tailscale-ip>:8734` as their server_url. No ports
are opened to the internet — the API is only reachable from your own devices.

## backups

Per the note in v1_design.md: SD cards die under sustained writes. Nightly cron on the Pi:

```
0 3 * * * sqlite3 /home/pi/activity_tracker/server/accountability.db ".backup /mnt/usb/accountability-backup.db"
```

(point it at a USB stick; even better, keep the live DB itself on a USB drive via
`db_path` in config.json.)

## endpoints (all require `Authorization: Bearer <api_token>`)

- `GET /todo/today` — generates today's instances if needed; returns todo +
  missed-yesterday + 3-day upcoming + goal check-ins due
- `PATCH /task-instances/{id}` `{status}` — complete/uncomplete an item
- `GET/POST/PATCH /tasks`, `POST /tasks/{id}/restore` — task CRUD (no DELETE:
  deletion goes through the `delete_task` skill)
- `GET/POST/PATCH /goals`, `GET /goals/{id}/checkins`
- `POST /activity` — session-end duration UPSERT from the tracker; `GET /activity/today`
- `POST /skills/{name}/open`, `POST /skills/{name}/respond` — the 1-shot AI
  conversations (missed_yesterday, delete_task, delete_goal, goal_checkin,
  todo_narration, midday_checkin, zero_goals)
- `POST /chat` — free-form chat; client sends the full transcript each call
- `GET/PUT /settings`, `GET /reminders/pending`, `GET /health`
