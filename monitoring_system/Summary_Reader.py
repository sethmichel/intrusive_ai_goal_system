import csv
import os
from datetime import date, timedelta

from Storage import get_summary_csv_path

'''
read-only side of the monthly summaries, for the GUI: builds the time-range choices
(this week, this month, and each of the last 14 days) and totals up
data/monthly_summaries/Summarized_Activities_<MM>_<YYYY>.csv rows over a date range,
reading every month file the range touches (e.g. Jan 8 looking back 14 days also reads
last December's file). Only already-summarized days are shown -- today's live daily log
isn't summarized until the day ends, so it never appears here.
'''

DAY_ABBREVIATIONS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RECENT_DAYS = 14


def format_day_label(d):
    """date(2026, 9, 13) -> '9/13 Sun' (no zero padding; %-m isn't supported on Windows)"""
    return f"{d.month}/{d.day} {DAY_ABBREVIATIONS[d.weekday()]}"


def get_range_options(today=None):
    """Return [(label, start_date, end_date), ...] for the monitoring dropdown, both ends inclusive.
    'This week' is Monday..today, 'This month' is the 1st..today, then yesterday back through
    RECENT_DAYS days ago (today is skipped since it has no summary yet)."""
    if today is None:
        today = date.today()
    options = [
        ("This week", today - timedelta(days=today.weekday()), today),
        ("This month", today.replace(day=1), today),
    ]
    for offset in range(1, RECENT_DAYS + 1):
        d = today - timedelta(days=offset)
        options.append((format_day_label(d), d, d))
    return options


def _months_in_range(start, end):
    """date(2025, 12, 28), date(2026, 1, 8) -> [date(2025, 12, 1), date(2026, 1, 1)]"""
    months = []
    current = start.replace(day=1)
    while current <= end:
        months.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return months


def _parse_duration(text):
    """'1:05:30' -> 3930 (inverse of Storage._format_duration). Returns None if unparseable."""
    try:
        hours, minutes, seconds = (int(part) for part in text.split(":"))
    except (AttributeError, ValueError):
        return None
    return hours * 3600 + minutes * 60 + seconds


def load_summary(start, end):
    """Total every summarized app/website between start and end (inclusive).
    Returns (entries, days_with_data) where entries is
    [{"name": str, "kind": "App" | "Website", "seconds": int}, ...] sorted longest first."""
    totals = {}
    days_with_data = set()

    for month in _months_in_range(start, end):
        path = get_summary_csv_path(month)
        if not os.path.exists(path):
            continue
        with open(path, "r", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    row_date = date.fromisoformat(row["date"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not start <= row_date <= end:
                    continue
                seconds = _parse_duration(row.get("duration"))
                if seconds is None:
                    continue
                app = row.get("app") or ""
                website = row.get("website") or ""
                if not app and not website:
                    continue
                key = ("Website", website) if website else ("App", app)
                totals[key] = totals.get(key, 0) + seconds
                days_with_data.add(row_date)

    entries = [
        {"name": name, "kind": kind, "seconds": seconds}
        for (kind, name), seconds in totals.items()
    ]
    entries.sort(key=lambda e: e["seconds"], reverse=True)
    return entries, days_with_data
