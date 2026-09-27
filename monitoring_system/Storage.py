import csv
import os
import shutil
import tempfile
from datetime import datetime, date, timedelta
from urllib.parse import urlparse

from Config import (
    DATA_DIR,
    DAILY_LOGS_DIR,
    SUMMARY_DIR,
    SUMMARY_IGNORED_APPS,
    WARNINGS_LOG,
)

'''
handles all CSV persistence: creating per-month data/monthly_summaries/Summarized_Activities_<MM>_<YYYY>.csv
and per-day data/daily_activity_logs/Daily_Activity_Logs-<date>.csv files, writing raw activity rows,
extracting hostnames from URLs, and summarizing/aggregating a finished day's raw rows into
that day's monthly summary file (total seconds per app/website). The daily log is kept, not deleted,
after being summarized.
'''



SUMMARY_COLUMNS = ["date", "app", "website", "duration", "url"]
DAILY_COLUMNS = ["timestamp", "app", "url"]
SUMMARY_PREFIX = "Summarized_Activities_"


def _log_warning(message):
    """Print a warning and append it to warnings.log. Used for edge cases that should never happen."""
    print(f"WARNING: {message}")
    with open(WARNINGS_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} {message}\n")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def ensure_summary_dir():
    os.makedirs(SUMMARY_DIR, exist_ok=True)


def get_summary_csv_path(d):
    """date(2026, 9, 27) -> data/monthly_summaries/Summarized_Activities_09_2026.csv"""
    return os.path.join(SUMMARY_DIR, f"{SUMMARY_PREFIX}{d.month:02d}_{d.year}.csv")


def ensure_summary_csv(d):
    """Create the monthly summary file for d's month (header only) if it doesn't exist yet."""
    ensure_summary_dir()
    path = get_summary_csv_path(d)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(SUMMARY_COLUMNS)
    return path


def list_summary_csvs():
    """Return every monthly summary file path in SUMMARY_DIR."""
    ensure_summary_dir()
    return [
        os.path.join(SUMMARY_DIR, name)
        for name in os.listdir(SUMMARY_DIR)
        if name.startswith(SUMMARY_PREFIX) and name.endswith(".csv")
    ]


def _append_rows_atomic(path, rows):
    """Append rows to an existing CSV as an all-or-nothing operation: copy the existing
    file plus the new rows into a temp file in the same directory, then
    os.replace() it into place (atomic on Windows within a volume). This keeps a
    crash mid-append from leaving a day partially summarized -- which would make
    that date look already-done to get_summarized_dates() and permanently drop
    the rest of the day."""
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as out:
            with open(path, "r", newline="") as src:
                shutil.copyfileobj(src, out)
            csv.writer(out).writerows(rows)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def ensure_daily_logs_dir():
    os.makedirs(DAILY_LOGS_DIR, exist_ok=True)


def get_daily_csv_path(d=None):
    if d is None:
        d = date.today()
    return os.path.join(DAILY_LOGS_DIR, f"Daily_Activity_Logs-{d.isoformat()}.csv")


def ensure_daily_csv(d=None):
    ensure_daily_logs_dir()
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


def _format_duration(seconds):
    """round(secs) -> 'H:MM:SS'"""
    seconds = round(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def find_old_daily_csvs():
    """Return [(date, path), ...] for daily CSVs that aren't today's and haven't been summarized yet."""
    ensure_daily_logs_dir()
    today = date.today()
    old = []
    prefix = "Daily_Activity_Logs-"
    for name in os.listdir(DAILY_LOGS_DIR):
        if name.startswith(prefix) and name.endswith(".csv"):
            date_str = name[len(prefix):-4]
            try:
                d = date.fromisoformat(date_str)
                if d != today:
                    old.append((d, os.path.join(DAILY_LOGS_DIR, name)))
            except ValueError:
                continue
    return old


def _read_dates(path):
    dates = set()
    with open(path, "r", newline="") as f:
        for row in csv.DictReader(f):
            try:
                dates.add(date.fromisoformat(row["date"]))
            except (KeyError, ValueError):
                continue
    return dates


def get_summarized_dates():
    """Return the set of dates already aggregated into any monthly summary file."""
    dates = set()
    for path in list_summary_csvs():
        dates |= _read_dates(path)
    return dates


def summarize_daily_csv(file_date, daily_path):
    """Aggregate a finished daily CSV into its month's summary file. The daily CSV is kept on disk as a raw log."""
    from Tracker import KNOWN_BROWSERS, NEW_TAB_LABEL

    rows = []
    with open(daily_path, "r", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    if not rows:
        return

    # If the last row is a real activity row (not an end-marker), the tracker was killed
    # uncleanly before it could write an end-marker for that session. Rather than silently
    # dropping it, synthesize an end-marker 1 second later so it still gets counted.
    last_app = rows[-1].get("app")
    dangling_session = bool(last_app) and last_app != NEW_TAB_LABEL
    if dangling_session:
        _log_warning(
            f"summarize_daily_csv: {daily_path} ends with an in-progress session "
            f"(app={last_app!r}) and no end-marker row -- the tracker was likely killed "
            f"uncleanly (not via Ctrl+C). Synthesizing an end-marker 1 second after the last "
            f"known activity so this session isn't dropped."
        )

    # (app, website) -> total seconds
    totals = {}

    row_count = len(rows)
    for i in range(row_count):
        app = rows[i].get("app")
        url = rows[i].get("url")
        is_last_row = i == row_count - 1

        if is_last_row and not dangling_session:
            # legitimate end-marker row -- nothing to pair it with
            break

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
            if is_last_row:
                next_ts = ts + timedelta(seconds=1)
            else:
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
            if app.lower() in SUMMARY_IGNORED_APPS:
                continue
            key = (app, "")

        totals[key] = totals.get(key, 0) + duration

    # Build every row for this day first, then append them in a single atomic
    # write so a crash can't half-summarize the date (see _append_rows_atomic).
    new_rows = [
        [file_date.isoformat(), app, website, _format_duration(secs), website or ""]
        for (app, website), secs in totals.items()
    ]
    if new_rows:
        _append_rows_atomic(ensure_summary_csv(file_date), new_rows)


def check_and_summarize_old_dailies():
    already_summarized = get_summarized_dates()
    for d, path in find_old_daily_csvs():
        if d in already_summarized:
            continue
        summarize_daily_csv(d, path)
