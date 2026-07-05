import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

'''
The always-on Windows piece (v1_design.md "computer" app design): starts the
monitoring tracker headless in a background thread and sits in the system tray
via pystray. Tray menu: Open Dashboard (spawns dashboard.py as its own
process, since pywebview needs its own main thread) / Quit.

Also polls GET /reminders/pending every few minutes and raises a Windows toast
for tasks with a time_of_day coming up ("exfoliate at 21:00" -> toast at 19:00
with the default 120-min window).

Run it via install_startup.ps1 (shell:startup shortcut using pythonw.exe so no
console window), or manually with:  python launcher.py
'''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
MONITORING_DIR = os.path.join(REPO_DIR, "monitoring_system")
CLIENT_CONFIG_PATH = os.path.join(REPO_DIR, "client_config.json")
LOG_PATH = os.path.join(BASE_DIR, "launcher.log")
REMINDER_POLL_SECONDS = 300

sys.path.insert(0, MONITORING_DIR)

# under pythonw.exe stdout/stderr are None and any print() would crash the
# tracker thread -- send everything to a log file instead
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(LOG_PATH, "a", buffering=1)


def load_client_config():
    try:
        with open(CLIENT_CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        return (cfg.get("server_url") or "").rstrip("/"), cfg.get("api_token", "")
    except (OSError, ValueError):
        return "", ""


def api_request(method, path, body=None):
    server_url, token = load_client_config()
    if not server_url:
        return None
    req = urllib.request.Request(
        server_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except OSError:
        return None


def run_tracker():
    os.chdir(MONITORING_DIR)  # tracker resolves data/ relative to its own dir, but be safe
    from Computer_Tracker import main as tracker_main
    tracker_main()


def run_reminder_poller(icon):
    while True:
        due = api_request("GET", "/reminders/pending")
        for r in due or []:
            try:
                icon.notify(f"{r['name']} at {r['time_of_day']}", "Coming up")
                api_request("POST", f"/task-instances/{r['id']}/reminded")
            except Exception as e:
                print(f"reminder toast failed: {e}")
        time.sleep(REMINDER_POLL_SECONDS)


def open_dashboard(icon=None, item=None):
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    subprocess.Popen([exe, os.path.join(BASE_DIR, "dashboard.py")], cwd=BASE_DIR)


def quit_app(icon, item):
    icon.stop()
    # tracker thread is a daemon and its CSV summarizer heals the missing
    # end-marker on next start, so a hard exit is safe here
    os._exit(0)


def make_icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (64, 64), (30, 30, 46))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=(137, 180, 250))
    d.line((22, 34, 30, 42), fill=(30, 30, 46), width=6)  # checkmark
    d.line((30, 42, 44, 22), fill=(30, 30, 46), width=6)
    return img


def main():
    import pystray

    threading.Thread(target=run_tracker, daemon=True).start()

    icon = pystray.Icon(
        "accountability",
        make_icon_image(),
        "Accountability",
        menu=pystray.Menu(
            pystray.MenuItem("Open Dashboard", open_dashboard, default=True),
            pystray.MenuItem("Quit", quit_app),
        ),
    )
    threading.Thread(target=run_reminder_poller, args=(icon,), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
