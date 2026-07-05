import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import get_config, BASE_DIR

'''
sqlite helpers. One connection per request (FastAPI dependency in main.py).
Convention: timestamps stored UTC ("utc_now_iso"), day-boundary logic uses
local_today() which converts through settings.timezone.
'''

SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_conn():
    conn = sqlite3.connect(get_config()["db_path"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    conn = get_conn()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_settings(conn):
    return conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()


def local_now(conn):
    tz = ZoneInfo(get_settings(conn)["timezone"])
    return datetime.now(timezone.utc).astimezone(tz)


def local_today(conn):
    return local_now(conn).date()
