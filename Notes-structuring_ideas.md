### this file should be loose thoughts in development

# skills
- due to how fragmented this project's goals are, we should make it's abilities just be "skills" which interact with the ai in different ways
    - {trigger condition, SQL query set that gathers context, prompt template, conversation shape (1-shot vs bounded), annoyance-scaler hook (on/off)}
    - all ai interactions are skills. The core engine's only job becomes: cron fires → check which skill's trigger matches → run its queries → render its prompt → get the user's reply → write the result back to the DB

list of skills
* means required / you can't turn this off
I might need to have some way to categorize apps/websites, or link them to goals. some skills can't be done without that. the system has to do that, the user won't do it.


- *todo list
- long term goals
- *scheudled tasks
- *deletion of long term goals or scheduled tasks justification
- mid day check in on todo list
    - does not use monitoring data for that day
- leetcode monitoring
    - user provides a structured csv of leetcode problems, sets a setting of number of problems per day and which days to do the problems -> problems are chosen for the days todo list
    - a leetocde streak is maintained on the home screen (user has a weekly streak freeze if they miss a day).
- github monitoring
    - requires the user make a github commit 6 days a week (changable in settings)
    - has access to your repo(s)
    - checks for commits and reads them to make sure it's not a dumb commit just to trick the system
- cs job hunting
    - activates leetcode and github skills
- email monitoring (maybe, might remove)
- activity monitoring - time limits / blocking of websites / apps (via the monitoring system data)
- *activity monitoring - daily / weekly / monthly summary of time in apps / websites
    - most wasted app
- smart plug hits. 
    - turn off smart plugs based on the activity monitoring data. for example, after 4 hours of computer time, the computer monitor smart plug turns off and a 1 shot ai converstaion happens in the phone app
- *Receipts skill — when the user marks a task done or dismisses a missed item, pull that day's activity log for any app/site tied to the task (e.g. task mentions "resume," check for Word/Docs/Overleaf time) and let the AI reference it directly: "you marked this done but I show 0 minutes in anything resume-related today." Doesn't block anything (still honor system per your design), just makes it much harder to lie casually. issue is I can't track your phone usage.
- *app avoidance (shared between computer and phone)
    - if the accountability app itself hasn't been opened in x days while the computer tracker shows normal daily usage, that's not "busy," that's avoidance specifically of the app. This should hit the annoyance scaler harder than a normal missed task
    - sends you a phone notification, and computer notification
- Rolling baseline / deviation nudge
    - track a trailing 7-30 day average of distraction time per app/category, flag days that spike above it. Lets the AI say "worse than usual" instead of just "bad," which reads as it actually knowing you rather than running a canned script


Skills I don't want
- mid day check in using monitoring data
    - like it checks in with you like normal but mentions that you spent 2 hours on youtube already. that's going to feel like it's looking over your shoulder, it's too intrusive.


# ai interactions
Structurally: the AI is a thin, stateless conversational layer bolted onto a system that's almost entirely deterministic (cron jobs, SQL, toggles) — its only real jobs are judging deletions, narrating the todo list, running the two recurring check-ins, and carrying the annoyance tone across all of those.

*anytime a conversation with the ai ends, the user has a button they can click to extend the conversation to the ai chat screen

*1 shot converstaion: the ai prompts the user, user responds, ai responds, conversation ends.

*Tone control via the "annoyance scaler": a DB-tracked value that makes the AI progressively more (but never too) annoyed based on missed tasks / app avoidance, always balanced with encouragement.

*No persistent "user model" object — everything injected into prompts is fresh SQL summarization at call time.

1) todo list: when the system makes the todo list, the ai reads the list, gives suggestions/order to do them and encouragement for it. the ai will be called when the user first looks at the todo list, not when the todo list is first made (it's possible we'll make it and store it before the user looks at it, in that case we'd have to store the ai response which we don't want to do). this doesn't use the annoyance scaler, it is only nice to the user.

2) todo list - failed item: if the user missed 1+ items on yesterdays todo list: 1 shot converstaion. the ai will ask why the user didn't get those goals. uses annoyance scaler
    - we'd need to store their missed goal history with dates so we can give the ai the frequency of missed goals and if they've missed that goal before (only up to x goals to save tokens).
    - the ai would note if they've missed this goal recently too. if the user missed this same goal last week, that's worse than if they missed that same goal last month.
    - reacts more harshly if the user has a habit of missing tasks

3) long term goal check-in: if it's a check in day for a long term goal. 1 shot conversation. ask if the 2 prior action items were done, present them, ask if the user wants to change them, react to that choice. annoyance scaler
    - only store the 2 active action items, not the history of action items

4) 0 long term goals: if it's been a month with 0 long term goals in the system, the ai will ask why. 1 shot conversation.

5) delete scheduled task: user tries to delete a scheduled task. 1 shot converstaion. uses annoyance scaler.
    - we'd need to store their deletion history with dates so give the ai the frequency of goal deletions and if they've deleted that goal before (only up to x goals to save tokens).

6) Mid-day check-in: one question about how things are going, one user reply, one AI reply.


# relevant data the system locally stores
this is the data the ai pulls into conversation prompts (via sql) and/or feeds the annoyance scaler. grouped by the feature it belongs to.

- scheduled tasks (chores/daily tasks)
    - task, frequency, importance, optional time of day, optional reason, date added
    - per-day operation history: datetime last recommended, did the user complete it (bool), user's reason if missed
    - frequency of misses on that specific task, and whether it's been missed recently (last week worse than last month) - capped to x goals of history to save tokens
    - deletion attempts: the reason the user gave the ai, frequency of deletions overall, whether this exact task has been deleted before

- todo list (daily assembly, not its own table, just queries over the above)
    - which scheduled + 1-off tasks landed on a given day's list
    - missed items from yesterday (pulled from scheduled task operation history above)
    - items due in the next 3 days but not today

- 1-off tasks
    - task, due date, completion state
    - history of completed/removed ones, restorable (restoring asks for a new due date)

- long term goals
    - goal, blocking reason, date added, next reminder date
    - only the current 2 active action items are stored, not past ones
    - per check-in: bool history of whether the prior 2 action items were done
    - deletion attempts: reason given to ai, frequency of deletions, whether this exact goal has been deleted before

- leetcode
    - uploaded csv of problems (name, number, difficulty)
    - per day: which problems were recommended, which the user reports doing (honor system, not machine tracked)
    - streak count, streak freeze usage (1 allowed miss/week)

- email digest (may remove this feature)
    - sender + subject stored as a dedup id so we don't re-spend ai tokens re-classifying read email
    - classification tag (bank, loan, job-related, subscription, etc.), not the email body itself
    - swiped-away/dismissed state
    - job-hunting-mode metrics derived from email over a trailing 2 months (interview/call requests, interview advancements, offers)

- github commit tracking
    - whether a qualifying commit happened that day, sized/valued by an ai scan (tied into a scheduled task's completion bool)

- computer activity monitoring (already built, see monitoring_system/)
    - per app/website: date, app, website (hostname only), duration, url
    - raw pre-summarized daily event log (timestamp, app, url)
    - this is the one data source the user can't lie to on the honor system - it's what lets the ai reference specifics ("47 min on youtube, 0 min on the task") instead of nagging generically

- phone app blocking (blocked/planned feature)
    - which apps are blocked, which goal unblocks them
    - emergency-unblock events (timestamp), recorded regardless of justification

- annoyance scaler
    - single db-tracked numeric value (current state)
    - inputs: missed tasks, app avoidance (not opening the accountability app / dismissing an ai check-in without responding), unjustified task/goal deletions, distraction time from the activity tracker, emergency phone unblocks
    - resets back toward 0 after a day or two of good behavior

