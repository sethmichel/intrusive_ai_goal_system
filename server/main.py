from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai
import skills
from auth import require_token
from db import get_conn, get_settings, init_db, local_now, local_today, utc_now_iso

'''
The one API in front of the one sqlite file (v1_design.md "rest + tailscale +
pi"). Runs on the Pi; the Windows dashboard, the tracker, and the phone app
are all just HTTP clients of this. Start with:  uvicorn main:app --host x.x.x.x --port 8734
'''

app = FastAPI(title="accountability api", dependencies=[Depends(require_token)])
app.add_middleware(  # dashboard html is loaded from file:// inside pywebview, so allow all origins
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
def _startup():
    init_db()


def conn_dep():
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def _rows(rows):
    return [dict(r) for r in rows]


# ── settings ─────────────────────────────────────────────────────────


class SettingsBody(BaseModel):
    timezone: Optional[str] = None
    goal_checkin_interval_days: Optional[int] = None


@app.get("/settings")
def read_settings(conn=Depends(conn_dep)):
    return dict(get_settings(conn))


@app.put("/settings")
def update_settings(body: SettingsBody, conn=Depends(conn_dep)):
    s = get_settings(conn)
    conn.execute(
        "UPDATE settings SET timezone = ?, goal_checkin_interval_days = ?, updated_at = ? WHERE id = 1",
        (
            body.timezone or s["timezone"],
            body.goal_checkin_interval_days or s["goal_checkin_interval_days"],
            utc_now_iso(),
        ),
    )
    conn.commit()
    return dict(get_settings(conn))


# ── tasks ────────────────────────────────────────────────────────────


class TaskBody(BaseModel):
    task_type: str
    name: str
    importance: str
    frequency_days: Optional[int] = None
    due_date: Optional[str] = None
    time_of_day: Optional[str] = None
    reason: Optional[str] = None


def _validate_task(body: TaskBody):
    # app-level rule from the schema comments
    if body.task_type == "recurring" and (not body.frequency_days or body.due_date):
        raise HTTPException(422, "recurring tasks need frequency_days and no due_date")
    if body.task_type == "one_off" and (not body.due_date or body.frequency_days):
        raise HTTPException(422, "one_off tasks need due_date and no frequency_days")


@app.get("/tasks")
def list_tasks(include_deleted: bool = False, conn=Depends(conn_dep)):
    q = "SELECT * FROM tasks" + ("" if include_deleted else " WHERE deleted_at IS NULL")
    return _rows(conn.execute(q + " ORDER BY created_at DESC").fetchall())


@app.post("/tasks")
def create_task(body: TaskBody, conn=Depends(conn_dep)):
    _validate_task(body)
    cur = conn.execute(
        """INSERT INTO tasks (task_type, name, importance, frequency_days, due_date, time_of_day, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (body.task_type, body.name, body.importance, body.frequency_days,
         body.due_date, body.time_of_day, body.reason),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.patch("/tasks/{task_id}")
def edit_task(task_id: int, body: TaskBody, conn=Depends(conn_dep)):
    _validate_task(body)
    if not conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone():
        raise HTTPException(404, "no such task")
    conn.execute(
        """UPDATE tasks SET task_type = ?, name = ?, importance = ?, frequency_days = ?,
           due_date = ?, time_of_day = ?, reason = ? WHERE id = ?""",
        (body.task_type, body.name, body.importance, body.frequency_days,
         body.due_date, body.time_of_day, body.reason, task_id),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


class RestoreBody(BaseModel):
    due_date: str


@app.post("/tasks/{task_id}/restore")
def restore_task(task_id: int, body: RestoreBody, conn=Depends(conn_dep)):
    """One-off restore: clear the soft delete, take a new due date. No AI
    justification for restores, per README."""
    t = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not t or t["task_type"] != "one_off":
        raise HTTPException(404, "no such one_off task")
    conn.execute(
        "UPDATE tasks SET deleted_at = NULL, deletion_reason = NULL, due_date = ? WHERE id = ?",
        (body.due_date, task_id),
    )
    # forget prior completion so it can land on the todo list again
    conn.execute("DELETE FROM task_instances WHERE task_id = ? AND status = 'completed'", (task_id,))
    conn.commit()
    return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


# ── todo list / instances ────────────────────────────────────────────


def _generate_today(conn):
    """Materialize task_instances for local-today. Idempotent -- both apps call
    this on open (the no-cron decision from v1_design.md)."""
    today = local_today(conn)
    today_s = today.isoformat()
    # anything still pending from a past day is now missed
    conn.execute(
        "UPDATE task_instances SET status = 'missed' WHERE status = 'pending' AND scheduled_date < ?",
        (today_s,),
    )
    for t in conn.execute(
        "SELECT * FROM tasks WHERE deleted_at IS NULL AND task_type = 'recurring'"
    ).fetchall():
        last = conn.execute(
            "SELECT MAX(scheduled_date) AS d FROM task_instances WHERE task_id = ?", (t["id"],)
        ).fetchone()["d"]
        # anchor = last instance regardless of completed/missed (user decision, v1_design.md misc Q2)
        due = last is None or (today - date.fromisoformat(last)).days >= t["frequency_days"]
        if due:
            conn.execute(
                "INSERT OR IGNORE INTO task_instances (task_id, scheduled_date) VALUES (?, ?)",
                (t["id"], today_s),
            )
    for t in conn.execute(
        "SELECT * FROM tasks WHERE deleted_at IS NULL AND task_type = 'one_off' AND due_date <= ?",
        (today_s,),
    ).fetchall():
        done = conn.execute(
            "SELECT 1 FROM task_instances WHERE task_id = ? AND status = 'completed'", (t["id"],)
        ).fetchone()
        if not done:  # overdue one-offs reappear daily until completed
            conn.execute(
                "INSERT OR IGNORE INTO task_instances (task_id, scheduled_date) VALUES (?, ?)",
                (t["id"], today_s),
            )
    conn.commit()


@app.get("/todo/today")
def todo_today(conn=Depends(conn_dep)):
    _generate_today(conn)
    today = local_today(conn)
    today_s = today.isoformat()
    yesterday_s = (today - timedelta(days=1)).isoformat()
    instances = _rows(conn.execute(
        """SELECT i.id, i.status, i.scheduled_date, i.completed_at,
                  t.id AS task_id, t.name, t.importance, t.task_type, t.time_of_day, t.reason
           FROM task_instances i JOIN tasks t ON t.id = i.task_id
           WHERE i.scheduled_date = ?
           ORDER BY CASE t.importance WHEN 'high' THEN 0 WHEN 'mid' THEN 1 ELSE 2 END""",
        (today_s,),
    ).fetchall())
    # missed yesterday and not yet explained -> the apps trigger the missed_yesterday skill off this
    missed_yesterday = _rows(conn.execute(
        """SELECT i.id, t.name, t.importance FROM task_instances i JOIN tasks t ON t.id = i.task_id
           WHERE i.scheduled_date = ? AND i.status = 'missed' AND i.missed_reason IS NULL""",
        (yesterday_s,),
    ).fetchall())
    # due in the next 3 days but not today: one-offs by due_date, recurring projected
    # from last instance without materializing early (v1_design.md)
    horizon = (today + timedelta(days=3)).isoformat()
    upcoming = _rows(conn.execute(
        """SELECT id AS task_id, name, importance, due_date AS due FROM tasks
           WHERE deleted_at IS NULL AND task_type = 'one_off' AND due_date > ? AND due_date <= ?""",
        (today_s, horizon),
    ).fetchall())
    for t in conn.execute(
        "SELECT * FROM tasks WHERE deleted_at IS NULL AND task_type = 'recurring'"
    ).fetchall():
        last = conn.execute(
            "SELECT MAX(scheduled_date) AS d FROM task_instances WHERE task_id = ?", (t["id"],)
        ).fetchone()["d"]
        if last:
            nxt = date.fromisoformat(last) + timedelta(days=t["frequency_days"])
            if today < nxt <= today + timedelta(days=3):
                upcoming.append({"task_id": t["id"], "name": t["name"],
                                 "importance": t["importance"], "due": nxt.isoformat()})
    upcoming.sort(key=lambda u: u["due"])
    # goal check-ins due -> apps trigger the goal_checkin skill off this
    checkins_due = _rows(conn.execute(
        "SELECT id, goal FROM long_term_goals WHERE deleted_at IS NULL AND next_checkin_date <= ?",
        (today_s,),
    ).fetchall())
    return {
        "date": today_s,
        "instances": instances,
        "missed_yesterday": missed_yesterday,
        "upcoming": upcoming,
        "goal_checkins_due": checkins_due,
    }


class InstanceStatusBody(BaseModel):
    status: str  # pending | completed | missed | excused


@app.patch("/task-instances/{instance_id}")
def set_instance_status(instance_id: int, body: InstanceStatusBody, conn=Depends(conn_dep)):
    if body.status not in ("pending", "completed", "missed", "excused"):
        raise HTTPException(422, "bad status")
    completed_at = utc_now_iso() if body.status == "completed" else None
    cur = conn.execute(
        "UPDATE task_instances SET status = ?, completed_at = ? WHERE id = ?",
        (body.status, completed_at, instance_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "no such instance")
    conn.commit()
    return {"ok": True}


@app.get("/reminders/pending")
def reminders_pending(window_minutes: int = 120, conn=Depends(conn_dep)):
    """Today's not-done instances whose task has a time_of_day within the next
    window and no reminder sent yet. The tray app polls this and shows a toast."""
    now = local_now(conn)
    rows = conn.execute(
        """SELECT i.id, t.name, t.time_of_day FROM task_instances i JOIN tasks t ON t.id = i.task_id
           WHERE i.scheduled_date = ? AND i.status = 'pending' AND i.reminded_at IS NULL
             AND t.time_of_day IS NOT NULL""",
        (now.date().isoformat(),),
    ).fetchall()
    due = []
    for r in rows:
        try:
            h, m = map(int, r["time_of_day"].split(":"))
        except ValueError:
            continue
        task_dt = now.replace(hour=h, minute=m, second=0)
        if timedelta(0) <= task_dt - now <= timedelta(minutes=window_minutes):
            due.append(dict(r))
    return due


@app.post("/task-instances/{instance_id}/reminded")
def mark_reminded(instance_id: int, conn=Depends(conn_dep)):
    conn.execute("UPDATE task_instances SET reminded_at = ? WHERE id = ?", (utc_now_iso(), instance_id))
    conn.commit()
    return {"ok": True}


# ── long term goals ──────────────────────────────────────────────────


class GoalBody(BaseModel):
    goal: str
    blocking_reason: Optional[str] = None
    action_item_1: Optional[str] = None
    action_item_2: Optional[str] = None


@app.get("/goals")
def list_goals(include_deleted: bool = False, conn=Depends(conn_dep)):
    q = "SELECT * FROM long_term_goals" + ("" if include_deleted else " WHERE deleted_at IS NULL")
    return _rows(conn.execute(q + " ORDER BY created_at DESC").fetchall())


@app.post("/goals")
def create_goal(body: GoalBody, conn=Depends(conn_dep)):
    interval = get_settings(conn)["goal_checkin_interval_days"]
    first_checkin = (local_today(conn) + timedelta(days=interval)).isoformat()
    now = utc_now_iso()
    cur = conn.execute(
        """INSERT INTO long_term_goals
           (goal, blocking_reason, action_item_1, action_item_1_updated_at,
            action_item_2, action_item_2_updated_at, next_checkin_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (body.goal, body.blocking_reason, body.action_item_1, now if body.action_item_1 else None,
         body.action_item_2, now if body.action_item_2 else None, first_checkin),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM long_term_goals WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.patch("/goals/{goal_id}")
def edit_goal(goal_id: int, body: GoalBody, conn=Depends(conn_dep)):
    """Action-item edits allowed anytime; bump the per-item updated_at but do
    NOT move next_checkin_date (resolved decision #3 in v1_design.md)."""
    g = conn.execute("SELECT * FROM long_term_goals WHERE id = ?", (goal_id,)).fetchone()
    if not g:
        raise HTTPException(404, "no such goal")
    now = utc_now_iso()
    conn.execute(
        "UPDATE long_term_goals SET goal = ?, blocking_reason = ? WHERE id = ?",
        (body.goal, body.blocking_reason, goal_id),
    )
    for n, new_text in ((1, body.action_item_1), (2, body.action_item_2)):
        if new_text != g[f"action_item_{n}"]:
            conn.execute(
                f"UPDATE long_term_goals SET action_item_{n} = ?, action_item_{n}_updated_at = ? WHERE id = ?",
                (new_text, now, goal_id),
            )
    conn.commit()
    return dict(conn.execute("SELECT * FROM long_term_goals WHERE id = ?", (goal_id,)).fetchone())


@app.get("/goals/{goal_id}/checkins")
def goal_checkins(goal_id: int, conn=Depends(conn_dep)):
    return _rows(conn.execute(
        "SELECT * FROM goal_checkins WHERE goal_id = ? ORDER BY checkin_date DESC", (goal_id,)
    ).fetchall())


# ── activity (written by the computer tracker) ───────────────────────


class ActivityBody(BaseModel):
    activity_date: str
    app: str = ""
    website: str = ""
    duration_seconds: int
    url: Optional[str] = None


@app.post("/activity")
def upsert_activity(body: ActivityBody, conn=Depends(conn_dep)):
    """Session-end UPSERT from the tracker: adds this session's seconds onto
    today's (app, website) bucket so today's totals stay near-real-time
    (resolved decision #2 in v1_design.md)."""
    conn.execute(
        """INSERT INTO activity_daily (activity_date, app, website, duration_seconds, url)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (activity_date, app, website)
           DO UPDATE SET duration_seconds = duration_seconds + excluded.duration_seconds,
                         url = COALESCE(excluded.url, url)""",
        (body.activity_date, body.app, body.website, body.duration_seconds, body.url),
    )
    conn.commit()
    return {"ok": True}


@app.get("/activity/{activity_date}")
def read_activity(activity_date: str, conn=Depends(conn_dep)):
    if activity_date == "today":
        activity_date = local_today(conn).isoformat()
    return _rows(conn.execute(
        "SELECT * FROM activity_daily WHERE activity_date = ? ORDER BY duration_seconds DESC",
        (activity_date,),
    ).fetchall())


# ── ai: skills + free chat ───────────────────────────────────────────


class SkillOpenBody(BaseModel):
    params: dict = {}


class SkillRespondBody(BaseModel):
    params: dict = {}
    transcript: list = []          # [{role: 'ai'|'user', text}]
    user_message: str
    extra: Optional[dict] = None   # structured choices (goal checkin dones/changes)


@app.post("/skills/{skill_name}/open")
def skill_open(skill_name: str, body: SkillOpenBody, conn=Depends(conn_dep)):
    if skill_name not in skills.SKILLS:
        raise HTTPException(404, "no such skill")
    return {"message": skills.run_open(conn, skill_name, body.params)}


@app.post("/skills/{skill_name}/respond")
def skill_respond(skill_name: str, body: SkillRespondBody, conn=Depends(conn_dep)):
    if skill_name not in skills.SKILLS:
        raise HTTPException(404, "no such skill")
    s = skills.SKILLS[skill_name]
    if s.shape != "one_shot":
        raise HTTPException(422, f"skill {skill_name} takes no user reply")
    reply = skills.run_respond(conn, skill_name, body.params, body.transcript,
                               body.user_message, body.extra)
    return {"message": reply}


class ChatBody(BaseModel):
    messages: list  # [{role: 'ai'|'user', text}] -- full transcript every call


@app.post("/chat")
def chat(body: ChatBody):
    """Free-form chat screen. Also where 'continue in chat' lands: the client
    carries the 1-shot transcript over as the opening messages. Nothing is
    persisted server-side."""
    if not body.messages:
        raise HTTPException(422, "empty transcript")
    return {"message": ai.chat_reply(body.messages)}


@app.get("/health")
def health():
    return {"ok": True}
