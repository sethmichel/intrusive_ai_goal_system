# Design Review & Suggestions

A critical review of `README.md` and `Database/db_schema_er_diagram.html`, aimed at giving you **strong fundamentals to build on** before you polish this into an open-source / resume project. I'm being blunt on purpose — you asked for it.

The good news first: the *concept* is strong and the writing shows you've thought about edge cases most people skip (dedup of emails, honor-system vs machine-verifiable, the "justify deletion to the AI" mechanic, annoyance that decays). The *data model*, though, is only covering about half of what the README describes, and a couple of the modeling choices will actively fight you later. Details below.

---

## TL;DR — the 5 things I'd fix before writing any code

1. **Soft-delete is not optional — it's your signature feature.** The "you can't delete a task/goal without justifying it, and the AI remembers how you did" mechanic *requires* keeping deleted rows and the deletion conversation. The current schema hard-deletes (and `SCHEDULED_TASK_OPERATIONS.task_id` is a FK that would orphan). See [#1](#1-hard-delete-breaks-your-signature-feature).
2. **There's no unified "todo item / completion" model.** Scheduled tasks, one-off tasks, leetcode, goal action items, kanban, and git commits all feed one daily list, but each has (or lacks) its own bespoke completion table. Unify them. See [#2](#2-no-unified-todo--completion-model).
3. **Half the README has no tables at all:** settings, emails, activity/distraction data, phone unblock events, and AI interaction history are all missing. The distraction-monitoring pillar — arguably your real moat — has *zero* representation. See [#4](#4-entire-pillars-have-no-schema).
4. **Timezones are a "later feature" but they can't be.** Every "today", "missed yesterday", "9pm reminder", and streak depends on a day boundary. Store UTC + one `timezone` setting from day one. See [#5](#5-timezone--day-boundary-is-foundational-not-a-later-feature).
5. **The annoyance scaler is modeled inconsistently and in the wrong place.** It lives on `LONG_TERM_GOALS` / `GOAL_CHECKINS` only, but the README applies it everywhere. Decide: derived or stored — and centralize it. See [#3](#3-the-annoyance-scaler-is-ambiguous-and-misplaced).

---

## Critical design problems (fundamentals)

### #1 Hard-delete breaks your signature feature
The most original thing in this app is: *"the user can't delete a task without justifying it to the AI, and the AI knows how the user did on it and brings it up."* That mechanic is impossible if you actually delete the row:

- The AI can't reference history it no longer has.
- `SCHEDULED_TASK_OPERATIONS.task_id` and `GOAL_CHECKINS.goal_id` are FKs — deleting the parent either orphans children or cascades away the very history the feature depends on.
- One-off tasks explicitly need restore-from-history (README line 97), which is literally soft-delete.

**Fix:** never hard-delete accountability data. Add `deleted_at`, `deletion_reason` (the user's justification), and store the AI's response to that justification as an `ai_interactions` row. "Active" = `deleted_at IS NULL`. This one change makes deletion, restore, *and* "the AI remembers you quit this" all fall out of the same mechanism.

### #2 No unified todo / completion model
Right now:
- `SCHEDULED_TASK_OPERATIONS` logs recommend+complete for scheduled tasks.
- `LEETCODE_RECOMMENDATIONS` does the same idea, differently.
- One-off tasks have **no** operations table.
- Goal action items, kanban items, and git-commit checks have no completion representation.

Yet the README's core loop is "assemble one daily todo list from all of these, then track what got done/missed." With five different shapes, every query (today's list, streaks, "what did you miss yesterday", correlation with distractions) becomes five special cases.

**Fix:** introduce a `task_instances` table — the per-day materialization of a task ("dishwasher, due 2026-07-01, status=pending"). One row per (task, day-it-appears). This single table replaces `SCHEDULED_TASK_OPERATIONS`, subsumes `LEETCODE_RECOMMENDATIONS`, and finally gives one-off tasks a home. Daily list = "instances where scheduled_date = today". "Missed yesterday" = "instances where scheduled_date = yesterday AND status = missed". Streaks, analytics, and distraction-correlation all read from one place.

Also unify the parent: **`tasks` with a `task_type` (`recurring` | `one_off`)** instead of separate `SCHEDULED_TASKS` + a future one-off table. They share ~90% of their columns (name, importance, reason, appears-on-todo, soft-delete, justify-to-delete); the only real difference is `frequency_days` vs `due_date`. Merging kills a whole duplicate operations table.

### #3 The annoyance scaler is ambiguous and misplaced
- The README treats annoyance as a broadly **global** user state ("the AI gets more and more annoyed... resets back to near 0 pretty easily"), driven by *any* failure: missed todos, task deletions, ghosting the app.
- The schema puts `annoyance_scalar` **only** on `LONG_TERM_GOALS` and a snapshot `annoyance_scalar_after` on `GOAL_CHECKINS`. Scheduled-task misses and app-closing have nowhere to raise it.

You have a real decision to make, and README line 22 hints at the answer: *"we likely don't maintain a complex user model object... the info injected into the prompts can just be summarizations from a few SQL queries."*

**Recommendation:** treat annoyance as **derived**, computed at prompt-build time from recent behavior (misses, deletions, ghosts in the last N days), and log every AI touch in one `ai_interactions` table that records the annoyance level *used* at that moment (for reproducibility/debuggability). Optionally keep a tiny cached `ai_state(annoyance_level, last_reset_at)` if recomputing is expensive — but source of truth is the event log. This makes tone **explainable** ("annoyed because you missed 3 high-priority tasks and closed the app twice without answering") instead of a mystery integer, which is a much better story on a resume and much easier to debug.

Either way: get the scalar off `LONG_TERM_GOALS` as *the* home for it.

### #4 Entire pillars have no schema
These are described in detail in the README but have no tables. Several are core, not later:

| Missing | Why it matters | Priority |
|---|---|---|
| **`settings`** | Every feature is gated by a toggle (email, leetcode, github, job-hunting, checkin interval, leetcode count, timezone). Nothing works without persisted config. | v1 core |
| **`emails`** | Full requirements exist (dedup by sender+subject, read/unread, category tag, dismissed state, 2-month job-hunt window). | v1 core |
| **`ai_interactions`** | Powers tone history, "user ghosted the app" signal, deletion justifications, and derived annoyance. | v1 core |
| **activity / distraction data** | The *entire* distraction-monitoring pillar. Even if raw data lives in your rescue_time_clone DB, you must define the integration boundary (synced daily aggregates vs. read-through). | v1 core |
| **`phone_unblock_events`** | "Emergency unblock is recorded and the AI knows." Named feature, no table. | v1 (if phone block ships) |
| **`blocked_apps` (global)** | Per your own revised design (README 163): global app list + one chosen unblock task. | v1 |
| **`notifications` / reminders sent** | Idempotency for the 3-hour scan + the phone/widget feed (see #7). | v1 |
| **`consequence_events`** | The $5-donation stakes, even if v1 only *suggests*. An event log row is enough. | v1-lite |

### #5 Timezone / day boundary is foundational, not a "later feature"
README lists timezones under "planned later features," but the whole app is organized around *days*: "today's todo," "missed yesterday," "9pm reminder," leetcode streaks, "check every 3 hours," 2-week checkins. A bare `date` column is meaningless without knowing which timezone defines midnight. Retrofitting this later means reinterpreting every historical row.

**Fix (cheap now, painful later):** store all timestamps in **UTC**, store one `timezone` in `settings`, and compute "local date" for every rollover/streak/reminder. That's it. You don't need multi-timezone support — you need *one* well-defined day boundary.

### #6 Temporal model of goal action items loses information
- `bullet_1_done` / `bullet_2_done` as fixed columns on `GOAL_CHECKINS` hardcodes "exactly 2" into the schema and can't answer "*which* two bullets were active at checkin #3?" — the bullets change over time (README line 105), and `GOAL_BULLETS` has `date_added` but no `retired_at` and no link to the checkin period.
- So you can't reconstruct the history the AI is supposed to reason over ("last time you said you'd eat baked potatoes and you didn't").

**Fix:** keep `goal_action_items` (rename from bullets) with `created_at` + `retired_at`, and add a join `goal_checkin_items(checkin_id, action_item_id, was_done)`. Now each checkin records exactly which items were active and whether each was done — no hardcoded slots, full history preserved. Enforce "exactly 2 active" in app logic (or a partial-index/trigger), not by column count.

### #7 The 3-hour scan needs idempotency
"Scan every 3 hours," "don't reread emails," and "remind me 2h before 9pm" all imply operations that must not double-fire. Email dedup is called out (good); reminders are not. If the scan runs at 5pm and 8pm, does the 9pm-reminder logic fire twice?

**Fix:** a `notifications` table with `(type, ref_id, scheduled_for, sent_at, dismissed_at)`. "Send if no row with sent_at for this ref today." This doubles as the **event feed the phone + computer + future widget read from** (see high-value features).

### #8 Deployment topology is undefined, and it drives real schema choices
"Self-host SQLite," "phone reads from a server," "computer pushes info." SQLite is single-writer and a phone can't open a remote SQLite file directly — so there's an **API server** implied but never described. This isn't pedantic; it decides:
- **PK strategy:** UUIDs (current) only earn their keep if two clients write offline and later merge. If everything funnels through one server + one SQLite, integer PKs are simpler and faster. Pick based on the topology.
- **Who owns writes** (conflict handling, "phone did X while computer did Y").

**Fix:** add a short "Architecture" section to the README: `[computer app] + [phone app] → HTTP API → single SQLite`. Then either justify UUIDs (sync) or switch to integer PKs (central). Don't leave it implicit.

### #9 Status as a bool loses states you need
`completed BOOL` conflates "not done yet," "missed," and "excused." `missed_reason` implies missed, but there's no explicit state and **no `completed_at` timestamp** — which you need for time-of-day analytics and for correlating completion against distraction windows.

**Fix:** `status ENUM(pending, completed, missed, excused, skipped)` + `completed_at`. `excused` = you gave a valid reason the AI accepted; distinct from a plain miss.

### #10 Smaller schema nits
- `LEETCODE_PROBLEMS` has no problem **number/slug**, though the CSV includes it (README 63) and you'll want it for de-duping re-uploaded CSVs. Add `problem_number` and a stable key; add `is_active` so a re-uploaded CSV can retire old rows without breaking historical `leetcode_recommendations` FKs.
- No explicit **verification model**. README distinguishes honor-system vs machine-verifiable (git commits, with the AI judging commit *size*). Add `verification_type (honor | git_commit | ...)` on `tasks` and store the evidence (commit SHA, size, AI verdict) on the instance.
- No **streak-freeze** accounting for leetcode ("miss 1 day/week"). Derivable from instances, but write down the rule so it's not reinvented per screen.
- The ER diagram is **stale vs. the README's own latest decision** (#4 / app-blocking should be global, iOS deferred). Regenerate it (I did — see below).

---

## High-value features not in the README

1. **Distraction ↔ outcome correlation (this is your actual moat).** You collect app/website time *and* task completion. Nobody in your competitor list joins those two: *"You missed your git commit on all 3 days you spent >2h on YouTube."* That single insight is more compelling than any individual feature and is basically free once `task_instances` + `activity_daily` share a day key. Make it a first-class thing (an `insights` view/table), not an afterthought.
2. **A unified event / notification outbox.** With a computer app, a phone app, and a planned widget all reading state, one append-only `notifications`/events feed (reminders, AI messages, digest updates, consequence events) is the clean way to fan out to all clients — and it solves the idempotency problem from #7 at the same time.
3. **Explainable AI tone.** Store the *signals* behind each annoyance level (which misses/ghosts drove it). Turns a magic number into something you can show off, debug, and unit-test.
4. **"Ghost" as a first-class signal.** README says closing the app without responding matters. Model it explicitly: an `ai_interactions` row with `user_ghosted = true` when a prompt is shown but never answered. Otherwise it's invisible to every query.
5. **Weekly retrospective / trends.** Daily accountability is table-stakes; a weekly "here's your completion rate, your worst distraction, your best streak" is what keeps people (and recruiters reading your README) engaged.
6. **Data export / backup.** For an OSS self-host app that hoovers up this much personal data, a one-command export builds trust and is a nice portfolio detail. The schema supports it trivially if it's clean.

---

## Proposed revised schema

Grouped by concern. This is the *target*; the "v1 cut line" section below says what to build first.

**Config & AI state**
- `settings` — single row: `timezone`, `email_enabled`, `leetcode_enabled`, `leetcode_daily_count`, `github_tracking_enabled`, `job_hunting_mode`, `goal_checkin_interval_days`, `unblock_task_id` (the one todo item that lifts app blocks).
- `ai_interactions` — every AI touch: `type` (todo_summary | task_delete | goal_delete | goal_checkin | missed_followup | midday_checkin), `ref_type`, `ref_id`, `user_input`, `ai_response`, `annoyance_level`, `user_ghosted`, `created_at`. *Source of truth for tone + history.*
- `ai_state` *(optional cache)* — `annoyance_level`, `last_reset_at`.

**Tasks & todo (the unification)**
- `tasks` — `task_type` (recurring | one_off), `name`, `importance`, `frequency_days` (nullable), `due_date` (nullable), `time_of_day`, `reason`, `verification_type`, `source` (manual | leetcode | kanban | github), `external_ref`, `created_at`, `deleted_at`, `deletion_reason`.
- `task_instances` — `task_id`, `scheduled_date`, `status` (pending | completed | missed | excused | skipped), `completed_at`, `missed_reason`, `verification_evidence`. *Replaces SCHEDULED_TASK_OPERATIONS + LEETCODE_RECOMMENDATIONS' role, covers one-offs.*

**Long-term goals**
- `long_term_goals` — `goal`, `blocking_reason`, `next_checkin_date`, `created_at`, `deleted_at`, `deletion_reason`.
- `goal_action_items` — `goal_id`, `text`, `created_at`, `retired_at`.
- `goal_checkins` — `goal_id`, `checkin_date`, `user_response`, `ai_response`, `user_ghosted`, `created_at`.
- `goal_checkin_items` — `checkin_id`, `action_item_id`, `was_done`. *Kills bullet_1_done/bullet_2_done, preserves which items were active.*

**Leetcode**
- `leetcode_problems` — `problem_number`, `title`, `category`, `difficulty`, `is_active`.
- `leetcode_recommendations` — `instance_id` (the day's leetcode task instance), `problem_id`, `completed`. *Now tied into the unified instance model.*

**Email**
- `emails` — `dedup_key` (unique, sender+subject), `sender`, `subject`, `category`, `received_at`, `is_read`, `dismissed_at`, `created_at`.

**Distraction / activity**
- `activity_daily` — `date`, `app_or_site`, `kind` (app | website), `seconds`. *Daily aggregate synced from rescue_time_clone; enough for AI summaries, cheap to store.*
- `usage_limits` — `app_or_site`, `limit_seconds`.
- `blocked_apps` — `app_token`. *Global list (per README's revised design).*
- `phone_unblock_events` — `occurred_at`, `is_emergency`, `note`.

**Consequences & delivery**
- `consequence_events` — `occurred_at`, `trigger_reason`, `amount`, `status` (suggested | paid | skipped).
- `notifications` — `type`, `ref_id`, `scheduled_for`, `sent_at`, `dismissed_at`. *Reminder idempotency + multi-client feed.*

I regenerated the ER diagram in the same style you were using:
**`Database/db_schema_er_diagram_v2.html`**

---

## A pragmatic v1 cut line

Don't build all of the above at once. Strong-fundamentals order:

**Build first (the spine):** `settings`, `tasks`, `task_instances`, `ai_interactions`, `emails`. This alone gives you the daily todo, completion tracking, the digest, and AI tone/history — the core loop end to end.

**Then:** `long_term_goals` + action items + checkins; leetcode tables.

**Then (the moat):** `activity_daily` + the distraction↔outcome correlation.

**Then (once phone ships):** `blocked_apps`, `phone_unblock_events`, `notifications`.

**Lite / later:** `consequence_events` (v1 just suggests), weekly retrospective, export.

Getting soft-delete, the unified `task_instances`, UTC+timezone, and the `ai_interactions` log right *in the spine* is what lets everything else bolt on cleanly. Those four are the "strong fundamentals" you asked for.

---

## Open decisions I'd want your call on

1. **Annoyance: derived or stored?** I recommend derived-from-`ai_interactions` (see #3). Your README leans this way already.
2. **PK strategy: UUID or integer?** Depends on topology (#8). Central server + one SQLite → integers. Offline multi-client merge → UUIDs.
3. **Merge scheduled + one-off into one `tasks` table?** I recommend yes (#2). If you feel they're conceptually too different, we keep them split but *still* unify their completion via `task_instances`.
4. **Activity data: sync into this DB, or read-through to the rescue_time_clone DB?** I recommend syncing daily aggregates (decouples the two, enables correlation queries, survives the tracker being offline).
