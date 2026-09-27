import json
import os
import tempfile
from datetime import date, datetime

'''
local goal storage + the rules for where a goal shows up. Goals live in
goal_system/data/goals.json (gitignored) as a list of
{"id", "name", "due_date", "done", "completed_on", "created_at"}, dates as ISO strings.

Lifecycle (all dates are local calendar days):
  - active:  shown on the home screen. Not-done goals first (soonest due at the top), then
             done goals at the bottom greyed out. A not-done goal whose due date has passed
             (today > due_date) is overdue and shown red.
  - history: a done goal whose due date has passed. It was on time if completed_on <= due_date,
             so checking off an overdue (red) goal sends it straight to history as late.
Unchecking a done goal that's still active clears completed_on and puts it back on top.
'''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GOALS_PATH = os.path.join(DATA_DIR, "goals.json")


def load_goals():
    if not os.path.exists(GOALS_PATH):
        return []
    with open(GOALS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_goals(goals):
    """Write to a temp file then os.replace() it into place, so a crash mid-write can't
    leave a half-written goals.json (same approach as monitoring_system/Storage.py)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(goals, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, GOALS_PATH)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def add_goal(name, due_date):
    goals = load_goals()
    goal = {
        "id": max((g["id"] for g in goals), default=0) + 1,
        "name": name,
        "due_date": due_date.isoformat(),
        "done": False,
        "completed_on": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    goals.append(goal)
    _save_goals(goals)
    return goal


def delete_goal(goal_id):
    _save_goals([g for g in load_goals() if g["id"] != goal_id])


def set_done(goal_id, done, today=None):
    if today is None:
        today = date.today()
    goals = load_goals()
    for g in goals:
        if g["id"] == goal_id:
            g["done"] = done
            g["completed_on"] = today.isoformat() if done else None
            break
    _save_goals(goals)


def due_date_of(goal):
    return date.fromisoformat(goal["due_date"])


def is_overdue(goal, today=None):
    if today is None:
        today = date.today()
    return not goal["done"] and today > due_date_of(goal)


def is_history(goal, today=None):
    if today is None:
        today = date.today()
    return goal["done"] and today > due_date_of(goal)


def was_on_time(goal):
    return goal["completed_on"] is not None and date.fromisoformat(goal["completed_on"]) <= due_date_of(goal)


def get_active_goals(today=None):
    """Home screen order: not-done by due date (overdue ones naturally first), then done by due date."""
    active = [g for g in load_goals() if not is_history(g, today)]
    active.sort(key=lambda g: (g["done"], g["due_date"], g["id"]))
    return active


def get_history_goals(today=None):
    """Most recently due first."""
    history = [g for g in load_goals() if is_history(g, today)]
    history.sort(key=lambda g: (g["due_date"], g["id"]), reverse=True)
    return history
