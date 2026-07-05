from dataclasses import dataclass, field
from datetime import timedelta

import ai
from db import get_settings, local_today, utc_now_iso

'''
The "skills" architecture from Notes-structuring_ideas.md: every AI interaction
is a skill = {trigger condition, SQL query set that gathers context, prompt
template, conversation shape, annoyance-scaler hook}. The engine's only job:
gather context via SQL -> render prompt -> Gemma -> write the structured
outcome back to the DB. No conversation is ever persisted.

Conversation shapes:
  - "ai_only": AI speaks once, done (todo narration).
  - "one_shot": AI opens -> user replies once -> AI closes, then apply() writes
    the outcome (missed_reason, deletion_reason, goal_checkins row, ...).

The annoyance scaler is explicitly NOT in v1 (v1_design.md "features not
included") -- `uses_annoyance_scaler` is carried on each skill as the hook
point so wiring it in later is one function, not a redesign. For v1 the tone
is fixed: supportive, honest, never harsh.

Triggering is client-side in v1 (see V1_NOTES.md): the apps check conditions
like "missed items exist for yesterday" via normal endpoints and then call
POST /skills/{name}/open. No cron -- matches the "resolved decisions" section
of v1_design.md.
'''

HISTORY_CAP = 10  # max history rows injected into a prompt, to save tokens


@dataclass
class Skill:
    name: str
    shape: str                      # "ai_only" | "one_shot"
    uses_annoyance_scaler: bool     # v1: recorded but unused (no scaler yet)
    gather: callable                # (conn, params) -> context string for the prompt
    open_instructions: str          # what the AI should do with the context
    respond_instructions: str = ""  # how the AI should close after the user's reply
    apply: callable = None          # (conn, params, user_message, extra) -> writes outcome


# ── context gatherers ────────────────────────────────────────────────


def _task_line(row):
    bits = [f"- {row['name']} (importance: {row['importance']}"]
    if row["time_of_day"]:
        bits.append(f", around {row['time_of_day']}")
    bits.append(")")
    if row["reason"]:
        bits.append(f" -- user's stated reason for this task: {row['reason']}")
    return "".join(bits)


def gather_todo(conn, params):
    today = local_today(conn).isoformat()
    rows = conn.execute(
        """SELECT t.name, t.importance, t.time_of_day, t.reason, i.status
           FROM task_instances i JOIN tasks t ON t.id = i.task_id
           WHERE i.scheduled_date = ? ORDER BY t.importance DESC""",
        (today,),
    ).fetchall()
    if not rows:
        return "The user's todo list for today is empty."
    lines = "\n".join(_task_line(r) for r in rows)
    return f"The user's todo list for today ({today}):\n{lines}"


def gather_missed_yesterday(conn, params):
    today = local_today(conn)
    yesterday = (today - timedelta(days=1)).isoformat()
    missed = conn.execute(
        """SELECT i.id, t.id AS task_id, t.name, t.importance
           FROM task_instances i JOIN tasks t ON t.id = i.task_id
           WHERE i.scheduled_date = ? AND i.status = 'missed'""",
        (yesterday,),
    ).fetchall()
    if not missed:
        return "Nothing was missed yesterday."
    lines = []
    for m in missed:
        # per-task miss history: frequency, and recency (missed last week is
        # worse than last month -- Notes-structuring_ideas.md interaction #2)
        hist = conn.execute(
            """SELECT scheduled_date, missed_reason FROM task_instances
               WHERE task_id = ? AND status = 'missed' AND scheduled_date < ?
               ORDER BY scheduled_date DESC LIMIT ?""",
            (m["task_id"], yesterday, HISTORY_CAP),
        ).fetchall()
        line = f"- {m['name']} (importance: {m['importance']})"
        if hist:
            recent = hist[0]["scheduled_date"]
            line += f" -- missed {len(hist)} time(s) before, most recently {recent}"
            reasons = [h["missed_reason"] for h in hist if h["missed_reason"]]
            if reasons:
                line += f'; past excuses: "{"; ".join(reasons[:3])}"'
        else:
            line += " -- first time missing this one"
        lines.append(line)
    return f"Tasks the user missed yesterday ({yesterday}):\n" + "\n".join(lines)


def _deletion_history(conn, table, name_col, name_value):
    prior_same = conn.execute(
        f"""SELECT deleted_at, deletion_reason FROM {table}
            WHERE {name_col} = ? AND deleted_at IS NOT NULL
            ORDER BY deleted_at DESC LIMIT ?""",
        (name_value, HISTORY_CAP),
    ).fetchall()
    total = conn.execute(
        f"""SELECT COUNT(*) AS n FROM {table}
            WHERE deleted_at IS NOT NULL AND deleted_at >= datetime('now', '-90 days')"""
    ).fetchone()["n"]
    lines = [f"Deletions of anything in the last 90 days: {total}."]
    if prior_same:
        for p in prior_same:
            lines.append(
                f'They deleted this exact item before ({p["deleted_at"]}), saying: "{p["deletion_reason"]}"'
            )
    else:
        lines.append("They have never deleted this exact item before.")
    return "\n".join(lines)


def gather_delete_task(conn, params):
    t = conn.execute("SELECT * FROM tasks WHERE id = ?", (params["task_id"],)).fetchone()
    misses = conn.execute(
        "SELECT COUNT(*) AS n FROM task_instances WHERE task_id = ? AND status = 'missed'",
        (t["id"],),
    ).fetchone()["n"]
    completes = conn.execute(
        "SELECT COUNT(*) AS n FROM task_instances WHERE task_id = ? AND status = 'completed'",
        (t["id"],),
    ).fetchone()["n"]
    ctx = [
        f'The user wants to delete the {t["task_type"].replace("_", "-")} task "{t["name"]}" '
        f'(importance: {t["importance"]}).',
        f"Their record on it: completed {completes} time(s), missed {misses} time(s).",
    ]
    if t["reason"]:
        ctx.append(f'When they created it they said it mattered because: "{t["reason"]}"')
    ctx.append(_deletion_history(conn, "tasks", "name", t["name"]))
    return "\n".join(ctx)


def gather_delete_goal(conn, params):
    g = conn.execute("SELECT * FROM long_term_goals WHERE id = ?", (params["goal_id"],)).fetchone()
    checkins = conn.execute(
        """SELECT checkin_date, action_item_1_done, action_item_2_done FROM goal_checkins
           WHERE goal_id = ? ORDER BY checkin_date DESC LIMIT ?""",
        (g["id"], HISTORY_CAP),
    ).fetchall()
    ctx = [f'The user wants to delete their LONG-TERM goal: "{g["goal"]}".']
    if g["blocking_reason"]:
        ctx.append(f'They once said what blocks it: "{g["blocking_reason"]}"')
    if checkins:
        done = sum((c["action_item_1_done"] or 0) + (c["action_item_2_done"] or 0) for c in checkins)
        ctx.append(
            f"Across their last {len(checkins)} check-in(s) they completed {done} of "
            f"{len(checkins) * 2} action items."
        )
    else:
        ctx.append("They have never completed a check-in on this goal.")
    ctx.append(_deletion_history(conn, "long_term_goals", "goal", g["goal"]))
    ctx.append("Long-term goals matter more than chores -- be a bit harder to convince here.")
    return "\n".join(ctx)


def gather_goal_checkin(conn, params):
    g = conn.execute("SELECT * FROM long_term_goals WHERE id = ?", (params["goal_id"],)).fetchone()
    last = conn.execute(
        "SELECT * FROM goal_checkins WHERE goal_id = ? ORDER BY checkin_date DESC LIMIT 1",
        (g["id"],),
    ).fetchone()
    ctx = [f'Scheduled check-in on the user\'s long-term goal: "{g["goal"]}".']
    ctx.append(f'Current action item 1: "{g["action_item_1"] or "(not set)"}"')
    ctx.append(f'Current action item 2: "{g["action_item_2"] or "(not set)"}"')
    if last:
        ctx.append(
            f'At the last check-in ({last["checkin_date"]}) they reported: '
            f'item 1 done = {bool(last["action_item_1_done"])}, item 2 done = {bool(last["action_item_2_done"])}.'
        )
        # "you changed this recently" flag from v1_design.md: item edited since last checkin
        for n in (1, 2):
            upd = g[f"action_item_{n}_updated_at"]
            if upd and upd > last["created_at"]:
                ctx.append(f"Note: they changed action item {n} since the last check-in.")
    else:
        ctx.append("This is the first check-in on this goal.")
    return "\n".join(ctx)


def gather_midday(conn, params):
    # deliberately does NOT use today's monitoring data -- that variant is in
    # "Skills I don't want" (too intrusive)
    today = local_today(conn).isoformat()
    rows = conn.execute(
        """SELECT t.name, i.status FROM task_instances i JOIN tasks t ON t.id = i.task_id
           WHERE i.scheduled_date = ?""",
        (today,),
    ).fetchall()
    done = [r["name"] for r in rows if r["status"] == "completed"]
    left = [r["name"] for r in rows if r["status"] == "pending"]
    return (
        f"Mid-day check-in. Done so far today: {', '.join(done) or 'nothing yet'}. "
        f"Still on the list: {', '.join(left) or 'nothing -- list is clear'}."
    )


def gather_zero_goals(conn, params):
    last = conn.execute(
        "SELECT MAX(COALESCE(deleted_at, created_at)) AS d FROM long_term_goals"
    ).fetchone()["d"]
    if last:
        return f"The user has had zero active long-term goals since {last} (over a month)."
    return "The user has never entered a single long-term goal."


# ── apply (outcome writers) ──────────────────────────────────────────


def apply_missed_yesterday(conn, params, user_message, extra):
    yesterday = (local_today(conn) - timedelta(days=1)).isoformat()
    conn.execute(
        """UPDATE task_instances SET missed_reason = ?
           WHERE scheduled_date = ? AND status = 'missed' AND missed_reason IS NULL""",
        (user_message, yesterday),
    )


def apply_delete_task(conn, params, user_message, extra):
    # deleted regardless of what the AI thinks, per README
    conn.execute(
        "UPDATE tasks SET deleted_at = ?, deletion_reason = ? WHERE id = ?",
        (utc_now_iso(), user_message, params["task_id"]),
    )


def apply_delete_goal(conn, params, user_message, extra):
    conn.execute(
        "UPDATE long_term_goals SET deleted_at = ?, deletion_reason = ? WHERE id = ?",
        (utc_now_iso(), user_message, params["goal_id"]),
    )


def apply_goal_checkin(conn, params, user_message, extra):
    """extra: {action_item_1_done, action_item_2_done, new_action_item_1?, new_action_item_2?}.
    Snapshots the items as they were at this checkin, then applies any changes,
    then advances next_checkin_date by the configured interval."""
    extra = extra or {}
    goal_id = params["goal_id"]
    g = conn.execute("SELECT * FROM long_term_goals WHERE id = ?", (goal_id,)).fetchone()
    today = local_today(conn)
    conn.execute(
        """INSERT INTO goal_checkins
           (goal_id, checkin_date, action_item_1_text, action_item_1_done,
            action_item_2_text, action_item_2_done)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            goal_id,
            today.isoformat(),
            g["action_item_1"],
            1 if extra.get("action_item_1_done") else 0,
            g["action_item_2"],
            1 if extra.get("action_item_2_done") else 0,
        ),
    )
    now = utc_now_iso()
    for n in (1, 2):
        new_text = extra.get(f"new_action_item_{n}")
        if new_text and new_text != g[f"action_item_{n}"]:
            conn.execute(
                f"UPDATE long_term_goals SET action_item_{n} = ?, action_item_{n}_updated_at = ? WHERE id = ?",
                (new_text, now, goal_id),
            )
    interval = get_settings(conn)["goal_checkin_interval_days"]
    conn.execute(
        "UPDATE long_term_goals SET next_checkin_date = ? WHERE id = ?",
        ((today + timedelta(days=interval)).isoformat(), goal_id),
    )


# ── the registry ─────────────────────────────────────────────────────

SKILLS = {
    "todo_narration": Skill(
        name="todo_narration", shape="ai_only", uses_annoyance_scaler=False,
        gather=gather_todo,
        open_instructions=(
            "Read the todo list and write one short, purely encouraging message: a suggested "
            "order of attack (e.g. which quick wins to knock out first) and a bit of motivation. "
            "This message is only ever nice -- no criticism."
        ),
    ),
    "missed_yesterday": Skill(
        name="missed_yesterday", shape="one_shot", uses_annoyance_scaler=True,
        gather=gather_missed_yesterday,
        open_instructions=(
            "Ask the user why they didn't get to these yesterday. If an item has been missed "
            "recently or repeatedly, mention that specifically (recent misses are worse than "
            "old ones). One question, direct but kind."
        ),
        respond_instructions=(
            "React to their reason in 1-3 sentences: acknowledge legitimate reasons, gently "
            "push back on weak ones, and encourage them to get it done today. Then the "
            "conversation is over -- do not ask another question."
        ),
        apply=apply_missed_yesterday,
    ),
    "delete_task": Skill(
        name="delete_task", shape="one_shot", uses_annoyance_scaler=True,
        gather=gather_delete_task,
        open_instructions=(
            "Ask the user why they are deleting this task. If their record on it is bad or "
            "they've deleted it before, bring that up."
        ),
        respond_instructions=(
            "Give one reply: either agree the deletion makes sense, or say you're disappointed / "
            "don't understand and briefly why (reference their history). Either way the task "
            "will be deleted -- do not ask another question."
        ),
        apply=apply_delete_task,
    ),
    "delete_goal": Skill(
        name="delete_goal", shape="one_shot", uses_annoyance_scaler=True,
        gather=gather_delete_goal,
        open_instructions=(
            "Ask the user why they are abandoning this long-term goal. Be harder to convince "
            "than for an everyday task -- this is supposed to matter to them."
        ),
        respond_instructions=(
            "Give one reply weighing their reason against their history on this goal. If it's "
            "weak, say so plainly and remind them why they set it. The goal will be deleted "
            "regardless -- do not ask another question."
        ),
        apply=apply_delete_goal,
    ),
    "goal_checkin": Skill(
        name="goal_checkin", shape="one_shot", uses_annoyance_scaler=True,
        gather=gather_goal_checkin,
        open_instructions=(
            "Run the periodic check-in: present the two current action items, ask whether they "
            "did each of them, and whether they want to change either. One message."
        ),
        respond_instructions=(
            "The user has answered (their done/changed choices are recorded separately). React: "
            "congratulate real progress, note if they changed an item and whether that seems "
            "wise, nudge if nothing got done. One reply, then the check-in is over."
        ),
        apply=apply_goal_checkin,
    ),
    "midday_checkin": Skill(
        name="midday_checkin", shape="one_shot", uses_annoyance_scaler=False,
        gather=gather_midday,
        open_instructions="Ask one light question about how the day's list is going.",
        respond_instructions="One supportive reply, then done. Do not ask another question.",
    ),
    "zero_goals": Skill(
        name="zero_goals", shape="one_shot", uses_annoyance_scaler=False,
        gather=gather_zero_goals,
        open_instructions=(
            "Gently ask why they have no long-term goals set, and suggest adding even one small one."
        ),
        respond_instructions="One understanding reply, then done.",
    ),
}


def run_open(conn, skill_name, params):
    s = SKILLS[skill_name]
    ctx = s.gather(conn, params or {})
    prompt = f"Context:\n{ctx}\n\nYour job right now: {s.open_instructions}"
    return ai.generate(prompt)


def run_respond(conn, skill_name, params, transcript, user_message, extra):
    s = SKILLS[skill_name]
    ctx = s.gather(conn, params or {})
    extra_block = ""
    if extra:
        picks = ", ".join(f"{k} = {v}" for k, v in extra.items() if v is not None)
        if picks:
            extra_block = f"\nStructured choices the user made in the UI: {picks}\n"
    prompt = (
        f"Context:\n{ctx}\n\n"
        f"The conversation so far:\n{ai.render_transcript(transcript)}\n"
        f"User: {user_message}\n{extra_block}\n"
        f"Your job right now: {s.respond_instructions}"
    )
    reply = ai.generate(prompt)
    if s.apply:
        s.apply(conn, params or {}, user_message, extra)
        conn.commit()
    return reply
