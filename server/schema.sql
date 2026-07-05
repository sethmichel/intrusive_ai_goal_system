-- v1 schema, copied from v1_design.md (see that file for the reasoning comments).
-- 6 tables: settings, tasks, task_instances, long_term_goals, goal_checkins, activity_daily.
-- All timestamps stored UTC; local dates derived from settings.timezone at query time.

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles',
    goal_checkin_interval_days INTEGER NOT NULL DEFAULT 14 CHECK (goal_checkin_interval_days BETWEEN 7 AND 21),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    task_type TEXT NOT NULL CHECK (task_type IN ('recurring', 'one_off')),
    name TEXT NOT NULL,
    importance TEXT NOT NULL CHECK (importance IN ('low', 'mid', 'high')),
    frequency_days INTEGER,      -- recurring only
    due_date TEXT,               -- one_off only
    time_of_day TEXT,            -- optional, for reminders, e.g. '19:00'
    reason TEXT,                 -- optional free text
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- soft delete: row never goes away so the ai can reference "you deleted this before"
    deleted_at TEXT,
    deletion_reason TEXT
    -- app-level rule (enforced in main.py, not sqlite): recurring rows set
    -- frequency_days/null due_date, one_off rows set due_date/null frequency_days.
);

CREATE TABLE IF NOT EXISTS task_instances (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    scheduled_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'missed', 'excused')),
    completed_at TEXT,
    missed_reason TEXT,
    reminded_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (task_id, scheduled_date)
);

CREATE TABLE IF NOT EXISTS long_term_goals (
    id INTEGER PRIMARY KEY,
    goal TEXT NOT NULL,
    blocking_reason TEXT,
    action_item_1 TEXT,
    action_item_1_updated_at TEXT,
    action_item_2 TEXT,
    action_item_2_updated_at TEXT,
    next_checkin_date TEXT NOT NULL,  -- editing an action item does NOT move this
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    deletion_reason TEXT
);

CREATE TABLE IF NOT EXISTS goal_checkins (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES long_term_goals(id),
    checkin_date TEXT NOT NULL,
    action_item_1_text TEXT,
    action_item_1_done INTEGER CHECK (action_item_1_done IN (0, 1)),
    action_item_2_text TEXT,
    action_item_2_done INTEGER CHECK (action_item_2_done IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_daily (
    id INTEGER PRIMARY KEY,
    activity_date TEXT NOT NULL,
    app TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER NOT NULL,
    url TEXT,
    UNIQUE (activity_date, app, website)
);

CREATE INDEX IF NOT EXISTS idx_task_instances_date ON task_instances(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_tasks_active ON tasks(deleted_at);
CREATE INDEX IF NOT EXISTS idx_activity_daily_date ON activity_daily(activity_date);

INSERT OR IGNORE INTO settings (id) VALUES (1);
