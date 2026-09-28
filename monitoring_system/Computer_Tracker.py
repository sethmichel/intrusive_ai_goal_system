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
    ensure_summary_dir,
    ensure_daily_csv,
    get_daily_csv_path,
    write_daily_row,
    extract_website,
    summarize_daily_csv,
    check_and_summarize_old_dailies,
)
from Config import (
    POLL_INTERVAL,
    SERVER_HOST,
    NO_EXTENSION_ALERT_THRESHOLD,
    SUSPEND_GAP_SECONDS,
    SUMMARY_IGNORED_APPS,
)
from Api_Sync import ApiSync
from Push_Notifier import BlockedContentNotifier

'''
main entry point/orchestrator. It runs the polling loop: checks the active window every 3s, detects app/browser switches,
writes activity rows to the daily CSV, handles midnight rollover, and starts the local server.

Every time a session ends (focus change, suspend, midnight, lock, quit) the finished duration is
also pushed to the Pi API via Api_Sync (offline-queued if the Pi is unreachable). The CSVs remain
the local raw log; the server's activity_daily table is the canonical shared copy.
'''


def _end_session(daily_csv, now, app_label=""):
    """Write an end-marker row so the previous activity gets a correct duration."""
    write_daily_row(daily_csv, now.isoformat(), app_label, "")


def main():
    lock = acquire_single_instance_lock()
    if lock is None:
        print("Another tracker instance is already running; exiting.")
        return

    ensure_summary_dir()
    check_and_summarize_old_dailies()

    current_date = date.today()
    daily_csv = ensure_daily_csv(current_date)

    server, port = start_server()
    print(f"Tracking started. Extension server on {SERVER_HOST}:{port}")

    current_app = None
    current_url = ""
    no_ext_counter = 0
    last_poll_time = datetime.now()
    session_start = None
    sync = ApiSync()
    blocked = BlockedContentNotifier()

    def sync_session_end(end_time):
        """Push the just-finished session's duration to the Pi API. Mirrors the
        summarizer's bucketing exactly: browsers -> ('', website), native apps
        -> (app, ''), OS chrome and blank tabs skipped. Bucketed under the day
        the session STARTED (midnight rollover closes sessions within seconds
        of 00:00, so spillover is negligible)."""
        if current_app is None or session_start is None:
            return
        duration = (end_time - session_start).total_seconds()
        if duration <= 0:
            return
        day = session_start.date().isoformat()
        if is_browser(current_app):
            website = extract_website(current_url)
            if website:
                sync.enqueue(day, "", website, duration, current_url)
        elif current_app.lower() not in SUMMARY_IGNORED_APPS:
            sync.enqueue(day, current_app, "", duration, None)

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
                    end_time = last_poll_time + timedelta(seconds=POLL_INTERVAL)
                    sync_session_end(end_time)
                    _end_session(daily_csv, end_time)
                    current_app = None
                    current_url = ""
                    session_start = None
            last_poll_time = now

            # ── midnight rollover ──
            if now.date() != current_date:
                if current_app is not None:
                    sync_session_end(now)
                    _end_session(daily_csv, now)
                old_path = daily_csv
                old_date = current_date
                if os.path.exists(old_path):
                    summarize_daily_csv(old_date, old_path)
                current_date = now.date()
                daily_csv = ensure_daily_csv(current_date)
                current_app = None
                current_url = ""
                session_start = None

            # ── poll active window ──
            process_name, _ = get_active_window()

            if not process_name:
                blocked.check("", "")
                if current_app is not None:
                    sync_session_end(now)
                    _end_session(daily_csv, now)
                    current_app = None
                    current_url = ""
                    session_start = None
                time.sleep(POLL_INTERVAL)
                continue

            # ── browser handling ──
            if is_browser(process_name):
                url = get_latest_url(process_name)

                if url is None:
                    blocked.check("", "")
                    no_ext_counter += 1
                    if no_ext_counter >= NO_EXTENSION_ALERT_THRESHOLD:
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                        no_ext_counter = 0
                    if current_app is not None:
                        sync_session_end(now)
                        _end_session(daily_csv, now)
                        current_app = None
                        current_url = ""
                        session_start = None
                    time.sleep(POLL_INTERVAL)
                    continue

                if is_new_tab_url(url):
                    no_ext_counter = 0
                    blocked.check("", "")
                    if current_app is not None:
                        sync_session_end(now)
                        _end_session(daily_csv, now, app_label=NEW_TAB_LABEL)
                        current_app = None
                        current_url = ""
                        session_start = None
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
            blocked.check(new_app, new_site)  # every poll, so it can re-notify while you stay on it
            cur_site = extract_website(current_url)
            if new_app == current_app and new_site == cur_site:
                time.sleep(POLL_INTERVAL)
                continue

            # ── record new activity ──
            sync_session_end(now)  # the new row is what ends the previous session
            write_daily_row(daily_csv, now.isoformat(), new_app, new_url)
            label = new_site if new_site else new_app
            #print(f"[{now.strftime('%H:%M:%S')}] {label}") # prints each activity to the terminal for debugging
            current_app = new_app
            current_url = new_url
            session_start = now

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        if current_app is not None:
            end_time = datetime.now()
            sync_session_end(end_time)
            _end_session(daily_csv, end_time)
        print("\nTracking stopped.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
