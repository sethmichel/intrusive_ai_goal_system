import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from Config import (
    CATEGORIZING_ITEMS_PATH,
    PUSH_SECRETS_PATH,
    BLOCKED_CATEGORY,
    BLOCKED_NOTIFICATION_MESSAGE,
    BLOCKED_NOTIFICATION_PRIORITY,
    BLOCKED_REPEAT_SECONDS,
    BLOCKED_MIN_GAP_SECONDS,
)

'''
sends a Pushover notification to the phone when the focused app/website is listed under the
"Blocked Content" category of data/Categorizing_Items.json. Notifies on entering a blocked item,
then again every BLOCKED_REPEAT_SECONDS while it stays focused. Sends run on a daemon thread so
a slow or offline network never stalls the polling loop.

Credentials are read from PUSH_SECRETS_PATH (outside the repo, "USER_KEY = ..." / "API_TOKEN = ..."
lines). If that file is missing or incomplete, notifications are disabled and the tracker runs as normal.

Pushover priority (-2 to 2):
    -2: no notification, just badge/history
    -1: no sound or vibration
     0: normal
     1: high, bypasses quiet hours
     2: emergency, requires acknowledgment (needs extra retry/expire params, not supported here)
'''

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def _load_credentials():
    """Parse the secrets file into (user_key, api_token), or None if unusable."""
    try:
        with open(PUSH_SECRETS_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    values = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    user_key = values.get("USER_KEY")
    api_token = values.get("API_TOKEN")
    if not user_key or not api_token:
        return None
    return user_key, api_token


def send_push_notification(message, priority=0):
    """POST one message to Pushover. Returns True on success. Never raises."""
    credentials = _load_credentials()
    if credentials is None:
        print("Push notification skipped: secrets file missing or incomplete.")
        return False
    user_key, api_token = credentials
    data = urllib.parse.urlencode({
        "token": api_token,
        "user": user_key,
        "message": message,
        "priority": priority,
    }).encode()
    try:
        with urllib.request.urlopen(PUSHOVER_URL, data=data, timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError) as e:
        # don't print the exception body: an HTTPError's URL/response could echo the token
        print(f"Push notification failed: {type(e).__name__}")
        return False


def _send_async(message, priority):
    threading.Thread(target=send_push_notification, args=(message, priority), daemon=True).start()


class BlockedContentNotifier:
    """Call check(app, website) every poll. Reloads the blocked list whenever the JSON file changes."""

    def __init__(self):
        self._blocked = set()
        self._mtime = None
        self._current_key = None  # blocked item currently focused, or None
        self._last_sent = None    # time.monotonic() of the last notification

    def _reload_if_changed(self):
        try:
            mtime = os.path.getmtime(CATEGORIZING_ITEMS_PATH)
        except OSError:
            self._blocked = set()
            self._mtime = None
            return
        if mtime == self._mtime:
            return
        self._mtime = mtime
        try:
            with open(CATEGORIZING_ITEMS_PATH, "r", encoding="utf-8") as f:
                items = json.load(f).get(BLOCKED_CATEGORY, {})
        except (OSError, ValueError, AttributeError):
            items = {}
        self._blocked = {name.lower() for name in items} if isinstance(items, dict) else set()

    def _match(self, app, website):
        """Return the blocked entry matching this activity, or None. Websites also match on
        subdomains (a blocked 'example.com' catches 'm.example.com')."""
        if website:
            site = website.lower()
            for blocked in self._blocked:
                if site == blocked or site.endswith("." + blocked):
                    return blocked
        if app and app.lower() in self._blocked:
            return app.lower()
        return None

    def check(self, app, website):
        self._reload_if_changed()
        key = self._match(app, website)
        if key is None:
            self._current_key = None
            return

        now = time.monotonic()
        entered = key != self._current_key
        self._current_key = key
        since_last = float("inf") if self._last_sent is None else now - self._last_sent
        if (entered and since_last >= BLOCKED_MIN_GAP_SECONDS) or since_last >= BLOCKED_REPEAT_SECONDS:
            self._last_sent = now
            _send_async(BLOCKED_NOTIFICATION_MESSAGE, BLOCKED_NOTIFICATION_PRIORITY)
