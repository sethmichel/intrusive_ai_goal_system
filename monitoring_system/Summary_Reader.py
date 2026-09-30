import csv
import json
import os
from datetime import date, timedelta

from Config import CATEGORIZING_ITEMS_PATH, BLOCKED_CATEGORY
from Storage import get_summary_csv_path

'''
read-only side of the monthly summaries, for the GUI: builds the time-range choices
(this week, this month, and each of the last 14 days) and totals up
data/monthly_summaries/Summarized_Activities_<MM>_<YYYY>.csv rows over a date range,
reading every month file the range touches (e.g. Jan 8 looking back 14 days also reads
last December's file). Only already-summarized days are shown -- today's live daily log
isn't summarized until the day ends, so it never appears here.
App and website names are relabeled here using data/Categorizing_Items.json (e.g.
"risk of rain 2.exe" shows as "Risk of Rain 2" of kind "Game", "instagram.com" as "Instagram" of
kind "Social Media"); the summary files themselves keep the raw names.
'''

DAY_ABBREVIATIONS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RECENT_DAYS = 14
UNCATEGORIZED = "Uncategorized"  # category-totals bucket for plain "App" / "Website" entries


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


def category_kind(category):
    """'Games' -> 'Game', 'Work' -> 'Work': the kind a category's entries show up as."""
    return category[:-1] if category.endswith("s") else category


def _load_categories():
    """Categorizing_Items.json as a dict, or {} if the file is missing or malformed."""
    try:
        with open(CATEGORIZING_ITEMS_PATH, "r", encoding="utf-8") as f:
            categories = json.load(f)
    except (OSError, ValueError):
        return {}
    return categories if isinstance(categories, dict) else {}


def load_categorized_items():
    """Read Categorizing_Items.json into {"risk of rain 2.exe": ("Game", "Risk of Rain 2"),
    "instagram.com": ("Social Media", "Instagram"), ...}. Keys can be process names or websites.
    Top-level keys are categories; "Games" becomes the kind "Game". Returns {} if the file
    is missing or malformed so the GUI falls back to raw names."""
    lookup = {}
    for category, items in _load_categories().items():
        if not isinstance(items, dict):
            continue
        kind = category_kind(category)
        for raw_name, display_name in items.items():
            key = raw_name.lower()
            # an item in several categories takes the last one, except the blocked category always
            # wins so the GUI can flag it however the JSON is ordered
            if lookup.get(key, ("",))[0] == BLOCKED_CATEGORY:
                continue
            lookup[key] = (kind, display_name)
    return lookup


def load_summary(start, end):
    """Total every summarized app/website between start and end (inclusive).
    Returns (entries, days_with_data) where entries is
    [{"name": str, "kind": "App" | "Website" | <category>, "seconds": int}, ...] sorted longest first."""
    categorized = load_categorized_items()
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
                if website:
                    key = categorized.get(website.lower(), ("Website", website))
                else:
                    key = categorized.get(app.lower(), ("App", app))
                totals[key] = totals.get(key, 0) + seconds
                days_with_data.add(row_date)

    entries = [
        {"name": name, "kind": kind, "seconds": seconds}
        for (kind, name), seconds in totals.items()
    ]
    entries.sort(key=lambda e: e["seconds"], reverse=True)
    return entries, days_with_data


def category_totals(entries):
    """Sum load_summary() entries per Categorizing_Items.json category, in the JSON's order, with
    UNCATEGORIZED (plain apps/websites) last: [("Games", 11520), ("Work", 0), ..., ("Uncategorized", 900)].
    Every category is listed, even at 0 seconds."""
    categories = [c for c, items in _load_categories().items() if isinstance(items, dict)]
    by_kind = {}
    for entry in entries:
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + entry["seconds"]
    totals = [(category, by_kind.pop(category_kind(category), 0)) for category in categories]
    # whatever's left is "App" / "Website", or a kind from a category removed since loading
    totals.append((UNCATEGORIZED, sum(by_kind.values())))
    return totals
