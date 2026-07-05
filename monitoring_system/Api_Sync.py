import json
import os
import threading
import urllib.error
import urllib.request

from Config import BASE_DIR, DATA_DIR

'''
Pushes session-end durations to the Pi API (POST /activity, an UPSERT that adds
seconds onto that day's (app, website) bucket) so the server's activity_daily
table stays near-real-time -- resolved decision #2 in v1_design.md. The CSV
files stay exactly as they were: the local raw log / crash-recovery record.

Offline-first: every event is appended to a jsonl queue file on disk FIRST,
then a background thread drains the queue oldest-first. If the Pi is
unreachable (laptop offline, tailscale down), events just accumulate and get
flushed next time a send succeeds. No new dependencies -- urllib only, matching
this package's no-external-deps rule.

Config comes from client_config.json at the repo root (shared with
computer_app/). If that file is missing or has no server_url, syncing is
silently disabled and the tracker is CSV-only, exactly like before.
'''

CLIENT_CONFIG_PATH = os.path.join(os.path.dirname(BASE_DIR), "client_config.json")
QUEUE_PATH = os.path.join(DATA_DIR, "pending_api_events.jsonl")
REQUEST_TIMEOUT = 5  # seconds


class ApiSync:
    def __init__(self):
        self.server_url = None
        self.api_token = None
        self._lock = threading.Lock()
        self._flushing = False
        if os.path.exists(CLIENT_CONFIG_PATH):
            try:
                with open(CLIENT_CONFIG_PATH, "r") as f:
                    cfg = json.load(f)
                self.server_url = (cfg.get("server_url") or "").rstrip("/") or None
                self.api_token = cfg.get("api_token", "")
            except (OSError, ValueError) as e:
                print(f"Api_Sync: could not read {CLIENT_CONFIG_PATH} ({e}); API sync disabled.")
        if self.server_url:
            print(f"Api_Sync: syncing activity to {self.server_url}")
        else:
            print("Api_Sync: no client_config.json with a server_url; running CSV-only.")

    @property
    def enabled(self):
        return self.server_url is not None

    def enqueue(self, activity_date, app, website, duration_seconds, url):
        """Queue one finished session's duration. Safe to call from the poll
        loop -- disk append is instant and the network happens off-thread."""
        if not self.enabled:
            return
        event = {
            "activity_date": activity_date,
            "app": app,
            "website": website,
            "duration_seconds": int(round(duration_seconds)),
            "url": url or None,
        }
        with self._lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(QUEUE_PATH, "a") as f:
                f.write(json.dumps(event) + "\n")
        self._kick_flush()

    def _kick_flush(self):
        with self._lock:
            if self._flushing:
                return
            self._flushing = True
        threading.Thread(target=self._flush, daemon=True).start()

    def _flush(self):
        try:
            while True:
                with self._lock:
                    if not os.path.exists(QUEUE_PATH):
                        return
                    with open(QUEUE_PATH, "r") as f:
                        lines = [ln for ln in f.read().splitlines() if ln.strip()]
                if not lines:
                    return
                if not self._post(json.loads(lines[0])):
                    return  # server unreachable; leave queue for next time
                with self._lock:
                    # rewrite minus the sent line (queue is small; simplicity > perf here)
                    with open(QUEUE_PATH, "r") as f:
                        current = [ln for ln in f.read().splitlines() if ln.strip()]
                    with open(QUEUE_PATH, "w") as f:
                        f.write("\n".join(current[1:]) + ("\n" if len(current) > 1 else ""))
        finally:
            with self._lock:
                self._flushing = False

    def _post(self, event):
        req = urllib.request.Request(
            f"{self.server_url}/activity",
            data=json.dumps(event).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                # bad event or bad token -- retrying won't fix it; drop it so the
                # queue can't jam forever, but say so
                print(f"Api_Sync: server rejected event ({e.code}); dropping it. Check api_token.")
                return True
            return False
        except OSError:
            return False
