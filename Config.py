import os

'''
central place for constants shared across the tracker: server port/host, poll interval,
data directory layout, and the extension-missing alert threshold.
'''

# ── server ──
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7834

# ── polling ──
POLL_INTERVAL = 3  # seconds between foreground-window checks
NO_EXTENSION_ALERT_THRESHOLD = 10  # consecutive polls with no extension POST before beeping
SUSPEND_GAP_SECONDS = 30  # wall-clock gap between polls above this => machine was suspended/frozen

# ── paths ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_LOGS_DIR = os.path.join(DATA_DIR, "daily_activity_logs")
MAIN_CSV = os.path.join(DATA_DIR, "Summarized_Activities.csv")
WARNINGS_LOG = os.path.join(BASE_DIR, "warnings.log")
