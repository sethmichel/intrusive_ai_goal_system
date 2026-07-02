import csv
import os
from datetime import datetime, date
from urllib.parse import urlparse

'''
handles all CSV persistence: creating data/main.csv and per-day data/daily-<date>.csv files, writing raw activity rows, 
extracting hostnames from URLs, and summarizing/aggregating a finished day's raw rows into main.csv (total seconds per 
app/website) before deleting the daily file
'''



DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAIN_CSV = os.path.join(DATA_DIR, "main.csv")
WARNINGS_LOG = os.path.join(DATA_DIR, "warnings.log")

MAIN_COLUMNS = ["date", "app", "website", "duration", "url"]
DAILY_COLUMNS = ["timestamp", "app", "url"]


def _log_warning(message):
    """Print a warning and append it to data/warnings.log. Used for edge cases that should never happen."""
    print(f"WARNING: {message}")
    ensure_data_dir()
    with open(WARNINGS_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} {message}\n")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def ensure_main_csv():
    ensure_data_dir()
    if not os.path.exists(MAIN_CSV):
        with open(MAIN_CSV, "w", newline="") as f:
            csv.writer(f).writerow(MAIN_COLUMNS)


def get_daily_csv_path(d=None):
    if d is None:
        d = date.today()
    return os.path.join(DATA_DIR, f"daily-{d.isoformat()}.csv")


def ensure_daily_csv(d=None):
    ensure_data_dir()
    path = get_daily_csv_path(d)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(DAILY_COLUMNS)
    return path


def write_daily_row(daily_path, timestamp, app, url):
    with open(daily_path, "a", newline="") as f:
        csv.writer(f).writerow([timestamp, app, url])


def extract_website(url):
    """'https://www.youtube.com/watch?v=abc' -> 'youtube.com'
    'file:///C:/foo/report.pdf' -> 'pdf file' (all local files of one type share a bucket,
    same as every YouTube video collapsing into 'youtube.com')"""
    if not url:
        return ""
    try:
        if url.lower().startswith("file://"):
            ext = os.path.splitext(urlparse(url).path)[1].lstrip(".").lower()
            if ext in ("htm", "html"):
                return "html file"
            if ext == "pdf":
                return "pdf file"
            return f"{ext} file" if ext else "local file"

        parsed = urlparse(url if "://" in url else f"https://{url}")
        hostname = parsed.hostname or ""
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return ""


def find_old_daily_csvs():
    """Return [(date, path), ...] for daily CSVs that aren't today's."""
    ensure_data_dir()
    today = date.today()
    old = []
    for name in os.listdir(DATA_DIR):
        if name.startswith("daily-") and name.endswith(".csv"):
            date_str = name[6:-4]
            try:
                d = date.fromisoformat(date_str)
                if d != today:
                    old.append((d, os.path.join(DATA_DIR, name)))
            except ValueError:
                continue
    return old


def summarize_daily_csv(file_date, daily_path):
    """Aggregate a finished daily CSV into main.csv, then delete it."""
    from Tracker import KNOWN_BROWSERS, NEW_TAB_LABEL

    rows = []
    with open(daily_path, "r", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    if not rows:
        os.remove(daily_path)
        return

    # (app, website) -> total seconds
    totals = {}

    for i in range(len(rows) - 1):
        app = rows[i].get("app")
        url = rows[i].get("url")

        if app is None or url is None:
            _log_warning(
                f"summarize_daily_csv: row {i} in {daily_path} is missing an 'app' or 'url' "
                f"column ({rows[i]!r}); skipping row."
            )
            continue

        if not app or app == NEW_TAB_LABEL:
            # expected end-marker row (written by _end_session with an empty url) -- unless
            # it somehow has a url attached, which should never happen
            if app != NEW_TAB_LABEL and url:
                _log_warning(
                    f"summarize_daily_csv: row {i} in {daily_path} has no app name but has a "
                    f"url ({url!r}); skipping row. This should never happen."
                )
            continue

        try:
            ts = datetime.fromisoformat(rows[i]["timestamp"])
            next_ts = datetime.fromisoformat(rows[i + 1]["timestamp"])
        except (ValueError, KeyError) as e:
            _log_warning(
                f"summarize_daily_csv: row {i} in {daily_path} has an unparseable timestamp "
                f"({e}); skipping row."
            )
            continue

        duration = (next_ts - ts).total_seconds()
        if duration <= 0:
            continue

        if app.lower() in KNOWN_BROWSERS:
            website = extract_website(url)
            if not website:
                continue
            key = ("", website)
        else:
            key = (app, "")

        totals[key] = totals.get(key, 0) + duration

    ensure_main_csv()
    with open(MAIN_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        for (app, website), secs in totals.items():
            writer.writerow([
                file_date.isoformat(),
                app,
                website,
                round(secs),
                website or "",
            ])

    os.remove(daily_path)


def check_and_summarize_old_dailies():
    ensure_main_csv()
    for d, path in find_old_daily_csvs():
        summarize_daily_csv(d, path)
