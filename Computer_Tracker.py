import os
import time
import winsound
from datetime import datetime, date, timedelta

from Tracker import (
    get_active_window,
    is_browser,
    is_new_tab_url,
    NEW_TAB_LABEL,
    acquire_single_instance_lock,
)
from Server import start_server, get_latest_url
from Storage import (
    ensure_main_csv,
    ensure_daily_csv,
    get_daily_csv_path,
    write_daily_row,
    extract_website,
    summarize_daily_csv,
    check_and_summarize_old_dailies,
)
from Config import POLL_INTERVAL, SERVER_HOST, NO_EXTENSION_ALERT_THRESHOLD, SUSPEND_GAP_SECONDS

'''
main entry point/orchestrator. It runs the polling loop: checks the active window every 3s, detects app/browser switches,
writes activity rows to the daily CSV, handles midnight rollover, and starts the local server
'''


def _end_session(daily_csv, now, app_label=""):
    """Write an end-marker row so the previous activity gets a correct duration."""
    write_daily_row(daily_csv, now.isoformat(), app_label, "")


def main():
    lock = acquire_single_instance_lock()
    if lock is None:
        print("Another tracker instance is already running; exiting.")
        return

    ensure_main_csv()
    check_and_summarize_old_dailies()

    current_date = date.today()
    daily_csv = ensure_daily_csv(current_date)

    server, port = start_server()
    print(f"Tracking started. Extension server on {SERVER_HOST}:{port}")

    current_app = None
    current_url = ""
    no_ext_counter = 0
    last_poll_time = datetime.now()

    try:
        while True:
            now = datetime.now()

            # ── suspend/resume detection ──
            # If far more wall-clock time elapsed than our poll interval, the
            # machine was almost certainly suspended (sleep/hibernate) or the
            # process was frozen. Don't credit that whole gap to whatever had
            # focus -- close the prior session at the last time we know it was
            # actually active (~one interval past the last poll) instead. This
            # runs before the midnight check so a sleep across midnight closes
            # out into the correct (old) day's CSV.
            if (now - last_poll_time).total_seconds() > SUSPEND_GAP_SECONDS:
                if current_app is not None:
                    _end_session(daily_csv, last_poll_time + timedelta(seconds=POLL_INTERVAL))
                    current_app = None
                    current_url = ""
            last_poll_time = now

            # ── midnight rollover ──
            if now.date() != current_date:
                if current_app is not None:
                    _end_session(daily_csv, now)
                old_path = daily_csv
                old_date = current_date
                if os.path.exists(old_path):
                    summarize_daily_csv(old_date, old_path)
                current_date = now.date()
                daily_csv = ensure_daily_csv(current_date)
                current_app = None
                current_url = ""

            # ── poll active window ──
            process_name, _ = get_active_window()

            if not process_name:
                if current_app is not None:
                    _end_session(daily_csv, now)
                    current_app = None
                    current_url = ""
                time.sleep(POLL_INTERVAL)
                continue

            # ── browser handling ──
            if is_browser(process_name):
                url = get_latest_url(process_name)

                if url is None:
                    no_ext_counter += 1
                    if no_ext_counter >= NO_EXTENSION_ALERT_THRESHOLD:
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                        no_ext_counter = 0
                    if current_app is not None:
                        _end_session(daily_csv, now)
                        current_app = None
                        current_url = ""
                    time.sleep(POLL_INTERVAL)
                    continue

                if is_new_tab_url(url):
                    no_ext_counter = 0
                    if current_app is not None:
                        _end_session(daily_csv, now, app_label=NEW_TAB_LABEL)
                        current_app = None
                        current_url = ""
                    time.sleep(POLL_INTERVAL)
                    continue

                no_ext_counter = 0
                new_app = process_name
                new_url = url
            else:
                no_ext_counter = 0
                new_app = process_name
                new_url = ""

            # ── detect activity change (compare by domain for browsers) ──
            new_site = extract_website(new_url)
            cur_site = extract_website(current_url)
            if new_app == current_app and new_site == cur_site:
                time.sleep(POLL_INTERVAL)
                continue

            # ── record new activity ──
            write_daily_row(daily_csv, now.isoformat(), new_app, new_url)
            label = new_site if new_site else new_app
            #print(f"[{now.strftime('%H:%M:%S')}] {label}") # prints each activity to the terminal for debugging
            current_app = new_app
            current_url = new_url

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        if current_app is not None:
            _end_session(daily_csv, datetime.now())
        print("\nTracking stopped.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
