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

# ── summary filtering ──
# Windows processes that still get logged to the daily CSV like any other app, but are
# excluded from the monthly Summarized_Activities_*.csv files because they're OS chrome, not real activity.
SUMMARY_IGNORED_APPS = frozenset({
    "lockapp.exe",
    "searchhost.exe",
    "explorer.exe",
})

# ── paths ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_LOGS_DIR = os.path.join(DATA_DIR, "daily_activity_logs")
# one summary file per calendar month: Summarized_Activities_<MM>_<YYYY>.csv
SUMMARY_DIR = os.path.join(DATA_DIR, "monthly_summaries")
# display names + categories for raw process names, applied only when the GUI reads summaries
CATEGORIZING_ITEMS_PATH = os.path.join(DATA_DIR, "Categorizing_Items.json")
WARNINGS_LOG = os.path.join(BASE_DIR, "warnings.log")
