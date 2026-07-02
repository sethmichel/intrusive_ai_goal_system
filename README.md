### Description

- I'd benifit a huge amount from having someone constantly hold me accountable, I've tried this many times and everyone just stops doing it after a few days. So I need to make something utalizing ai for this task. 
- the system will have a computer and iphone app. they link to github, whatever single ai we choose, and sqlite.
- The system goal is to be an accounability helper for scheduled tasks (basic goals, chores), long term goals, handle distractions and monitor progress towards these. 
    - When a user is on their computer there's a monitoring system noting how long they're using each program websites they're on. this is used to talk to them about distractions and time wasting
    - The users phone has selected apps blocked in the morning until they do a verifiable task. like a git commit. the user can emergency unblock the apps but the database records this and the ai will know about it
    - the ai knows the metrics about these distractions
- some tasks are the honor system on if the user did them, others like git commits are machine verifiable. a unique angle of this is the user can't delete a task without justifying it to the ai (limited to a short conversation and regardless of what the ai thinks, the task can be deleeted). the ai knows how the user did on this and will bring it up to try to stop them from deleting the habit if it thinks it's unjustified. tasks have importance values, freuquency values, user progress values...
- long term goals can be tracked. the ai will ask the user about them every 2 weeks, the user should give 2 action items they can do to get closer to their goal, the ai will ask if they did the prior check up action items, and if they want to change their action items. again, these are recorded and the ai can see how the user has been doing. this has the same long term goal deletion system with justifying it to an ai as the other tasks.
- it makes a todo list every morning based on your tasks (not long term goals), and asks why you didn't complete any missed tasks from yesterday. 
- monitors your email: the home page has various metrics, and you can turn on job hunting mode where it'll display your metrics about getting interviews and offers based on your emails. this is so common for ai's now I can probably find code online for hwo to do it or collect email info and have a stronger ai classifiy it. it's not sentiment analysis, it's classification
- in all interactions with the ai, it's limited to a short conversation, and the ai's tone will change based on if the user keeps failing/ missing goals or doesn't self report (closes the app). the ai will get more and more annoyed with the user, but also it's as encouraging as possible wherever it can be. like the todo list everyday comes with a bit of encouragment and maybe a strategy for how to knock off a bunch of the items early. it also weighs in how distracted you've been based on that activity tracker on the computer and if you energecy enter your phone apps all the time.
- it'll remind the user of tasks at needed times of day, like skin care exfoliation at 7 pm.
- it links to a kanban board the user makes which acts as a todo list (other options besides a kanban board will be made later) that gets included into the daily todo list the system makes.
- the user uploads a csv of leetcode problems and the system reccomends x number of leetcode problems you have to do each day. these are honor system on if you do them. it keeps a streak on the home page. leetcode can be toggled on and off in settings.
- I currently have projects in the works to brutally force me to go to bed (high consequence, and multi stage systems using arduinos), and an aggressive alarm clock (also arduino system). these will likely get linked to the project as an add on last.

# misc clarifications
- I already have the computer monitoring system from a while ago.
- the ios app blocking can use an open source system I found. however it might be you need a special permission from apple to do it, not sure how that works, but we can set that aside.
- the llm conversation thing is basically hard coded prompts with annoyance scalers, relevant info, and user input injected in. it'll be a cheap model like gemma. the user doesn't chat with the ai often, maybe once a day and it's always limited to the system asks a question (not the ai) the user responses, the ai responds to that, then that's it. so I'm not worried about ai costs. we likely don't maintain a complex user model object in sqlite, the info injected into the prompts can just be summarizations from a few sql queries about the relevant tasks. because user progress on those tasks and user dismissiveness / laziness is recorded in the database as it happens.
- it'll check your email, tasks, kanban every 3 hours, and the kanban can just be whatever, I'm not going to make my own. ai's reading emails and doing sentiment analysis on them is so common in projects that it probably can be copied from somewhere or there's an open source project for it. a lot of the todo system is hardcoded, not llm inference on what to do when. tasks have priority, and frequency, the todo list has what needs to be done that day. version 1 will just tell the user to donate $5 instead of automating it.
- idk how the annoyance scaler actually lessens, I assume it'll get reset if you're good about the tasks for a day or two. it should reset back to near 0 pretty easily.

# system has access to
- user emails
- user github repos (if they want to do git commit tracking)
- my rescuetime system has access to exactly what you're doing on your computer and for long long. (can only see app names and browser tab names)
- BLOCKED: phone app restrictions (not screen time)
- TODO: a kanban board

# in terms of relevance. 
"accountabilty app" has been done tons of times. I have a new story to tell in a old worn down category. because I combine all these and have solid ai personality / tracking for free
brick and opal already do app blocking

- lifeos, while not the same thing at all, might overshadow it
- beeminder and stickk already do financial consequences to stuff you hate
- habitica gamifies todo's
- focusmate does human accountability body doubleing
- rescue time does activity monitoring (however it costs money and isn't as good)

# If I wanted scaling / attention
- self host, docker, one command up
- pluggable llm backend
- pluggable task source abstraction: like the kanban sourceing. that aspect of it needs to be really clean with a lot of options
- priavacy: lol I have no idea how I'd get someone to use this with all the tracking it does.
- a nice app with a good dashboard

----------------------------------------------------------------------------------------------------------

### habit and email components
# 1st time use
- this has a computer part and a phone part. both can be used to enter key info. nothing happens if we don't have those 2 things
- database: sqlite, the user has to self host it and provide their connection to their own database
- ai api: again, user needs to give their own api key

# Leetcode tracking
- toggle in settings to turn on and off leetcode tracking
- sub toggle of how many problems the system should give the user each day
- user metrics are shown on the home screen. shows a leetcode streak that counts up by 1 each day you do all problems. the user is allowed to miss 1 day a week (called a streak freeze).
- solving problems are honor system by the user. not machine trackable
- on the leetcode page, the user clicks a upload csv button. above the button it says what the csv columns should be. this is a csv of leetcode problems (just problem names, numbers, difficultly, not the actual problems text). It'll be structured enough for the ai to reccommend daily questions. the csv is rejected if it's in the wrong format.
- turning on the leetcode toggle adds leetcode as a high priroty daily task to the scheduled tasks system (database entry)

# Email digest
- Emails need to be classified somehow, we'll do this by give the email subject, sender, and raw text content to a light weight ai like gemma. We only care about high priority categories like banks email (not monthly bank statements), loan emails, job related info, email about a subscription.
`TODO` - we need to not reread emails, so we'll save their sender and subject as their id in the database. before we use ai tokens on them we'll dismiss everything we've already read, and THEN categorize the unread emails. also helpful if we can actually see they're unread.
- since these are high priority, they're shown on the home screen as [tag, sender, subject]. it doesn't show the email itself.
- user can swipe these away. they exist on the home screen until they're swiped away. 
- email reading can be toggled on and off in settings.

# Metrics screen (home)
- if a leetcode csv exists, and the leetcode settings toggle is turned on: there's a leetcode streak metric
- users email digest is here
- there's a switch in settings called "job hunting mode". this shows job hunting metrics on the home screen. mostly about your emails over the last 2 months.
    - metrics: number of interview or call/chat requests (includeing linkedin messages which the user should get linkedin emails about that), number of interview advancments, number of offers

# Scheduled Tasks
- this is a screen in the app.
- These are simpler chores or tasks that are ideally machine trackable, but mostly the honor system.
- user enters (required) task, (required) frequency, (required) importance, (optional) time of day, (optional) reason. 
    - ex 1: run dishwasher, every 5 days, low, [blank], [blank].
    - ex 2: github commit, every 1 day, high, [blank], building key project for my resume
    - ex 3: exfoliate skin, every 3 days, high, 9 pm, very important to maintain
- covers stuff like dishwasher (every 5 days), laundry (every 5 days), grocery store trips (every friday afternoon), leetcode problems (daily), github commits (1 per day), night time routines (skincare, remind user at 7pm every two days)
- importance: low, mid, high. high would be like daily contributions toward an important goal, like github commits if you're trying to build a resume, or leetcode problems.
    - note that leetcode task is auto added as high priority daily if you turn on the leetcode toggle. you can edit it like any other task
- time of day: so the cron jobs can give reminders x hours before. and it could be used as info for the ai in some later cases. 
- scheduled tasks has it's own screen where we can edit our tasks.
- on this scheduled tasks screen, we should clarify that it's not long term goals, that's a different screen.
- the user can remove scheduled tasks on the scheduled task screen, but they'll have to tell the ai why. The ai will only give 1 response (so 1 user prompt, 1 ai response, then the conversation ends) - it either agrees that the task should be removed, or is dissapointed or doesn't understand why it's being removed. then it's removed. See the ai section to see how the ai actually handles this

# 1 off tasks
- this is a screen
- it's ransom personal life things the user has to do once. like pay person x with a due date.
- if these are completed then they're removed, but you can see the history of them and restore them from the history. if you restore them it'll ask you for a new due date.

# long term goals
- this is a screen
- ex: task: start going to the gym. blocking reason: I don't eat enough calories even without the gym. I need to bulk and get used to cooking before I start otherwise I'll lose weight quickly.
- how do I design this?
    - idea:
        - every 2 weeks the ai asks you about your status on this when it gives you your daily todo. it asks you what you did about this since last time. when the ai asks the user this, it'll pull up their 2 progress goals it previously asked them and ask if they did them.
        - after the ai interaction, the system will present the user with their prior 2 action items to progress toward the goal and ask if they want to change or replace them. we can only have 2 values at a time (not 1, not 0, not 3). after that, the ai will see what change was made (if any) and weigh that user choice against their goal. like it'll suggest making a change if they didn't, or it'll say that's fine if they're doing well. These action items would be like: "1) every 2 days I eat a baked potatoe because it's fast and bulky. 2) I commit to spending money on avacados for calories and healthy fat for my smoothies.". 
- the user can remove a long term goal on the long term goal screen, but they'll have to tell the ai why. 

# how the daily todo works
- database is queried to make the todo list of scheduled tasks, and 1 off tasks for that day
- also separatetly shows tasks due in the next 3 days but not due today
- it asks the database if there were any missed tasks from yesterday. if so then the ai will ask the user about them and put their response in the database.
- The ai will ask user about a long term goal if the checkup is needed that day
- the ai will give a little message about the todo list

----------------------------------------------------------------------------------------------------------

### Misc components

# `TODO` activity tracker
- this is mostly made, however I don't seem to have a readme file describing how it works. Thus, I need to figure out how it works to integrate it into my system
- based on memory: it maintains an sqlite database while tracking what apps you're using on windows, what websites you're on (I think in private tabs too), and for how long.
- you can set limits on usage.
- so the ai would have access to this info and would message the user if they're distraction prone
- https://github.com/sethmichel/rescue_time_clone

# `TODO` kanban integration
- how does the kanban board come into play? I guess it's more of a optional thing users can do. kanban board stuff would get put in 1 off tasks with their due date
- option: Self-host one that already has a REST/JSON-RPC API and talk to it from your agent. Kanboard is self-hosted, free, and runs on 80 MB of RAM, has a full JSON-RPC API for automation, webhook support for event notifications, and a plugin system — light enough to run on a Pi alongside everything else. If you want something closer to Trello's UX, WeKan is actively maintained, packed with kanban features like swimlanes, WIP limits, and custom fields, though it needs a MongoDB container alongside it

----------------------------------------------------------------------------------------------------------

# how the ai works
- user provides 1 api key for a weaker model like Gemma
- we'll maintain prompts for each ai action, that prompt will have relevant info injected into it. and various sql queries will fire first to gather that info like how often the user has slacked off on this task. this will act as a annoyance scaler for the ai. the ai will be more and more annoyed but never too annoyed or unfreidnly. it needs to push you but not be a jerk.
- conversations are 1 ai question, 1 user response, 1 ai response, unless otherwise specificed.

- user tries to remove a scheduled task
    - uses annoyance scaler
- user tries to remove a long term goal
    - uses annoyance scaler
    - the ai is a bit harder to convince here since this should be important to the user
- user has unfinished todo items from yesterday
    - uses annoyance scaler
- ai asks user about their long term goal status every 2 weeks
    - uses annoyance scaler
    - the ai is a bit harder to convince here since this should be important to the user
- it has to make the daily todo, and a message about it
    - the ai will read the todo list and offer a little encouragement, and maybe a suggestion about the order to do things. like "spend 1 hour doing these 4 tasks and your list is basically gone". example: you should cook and store the baked potatoe right now, and run the dishwasher. get those annoying things out of the way. You can try to get the grok backup api working today just as an easy win for your git commits.

# Settings
- email toggle
- leetcode toggle
- github commit tracking toggle
    - on: will create a daily high priority scheduled task that you must do 1 github commit of notable value (can't do a commit that's basically nothing). so the system will find your commit and have an ai scan it just looking at size of the commit.
    - off: deletes that scheduled task if it's there
- how often should the ai check in on your long term goals? default 2 weeks, must be between 1 and 3 weeks.
- number of leetcode problems toggle (disabled if leetcode toggle is turned off)
- job hunting mode (should tell the user to enable linkedin to email you so it knows when you get a recruiter message)

# database
ai suggested design:
See the [Entity-Relationship Diagram](Database/db_schema_er_diagram.html) for the schema layout.
- `TODO`: this digram likely includes planned later updates, like ios app blocking which I can't do right now. I should focus on version 1 and just have a basic database design for other stuff. let's remake this diagram but tasks do not block apps, the user selects which apps get blocked in the app and that's global. they also select what goal unblocks the apps (must be something on their todo list)
- `TODO`: also we'd need to look at my computer activity repo and note what it stores and include that in this database. because I don't remember off the top of the head.

# important feauture not yet worked out
- Later on, the user will put some amount of money ($20) into an isolated fund. if they fail their tasks (I don't know what decides this) it'll donate $5 from that fund to something the user really hates, something that would keep them up at night. 
- version 1 will just suggest the user donate the $5 since automating the payment has many fail points.


### planned later features

- BLOCKED ios app blocking. like brick or opal
    - this needs special permission to do.
    - the app would unblock when we meet our goal
    - we can emergency unblock an app but this is recorded in teh database and the ai will know you did that
    - what's this? https://www.foqos.app/ https://github.com/awaseem/foqos if it's open source then can I use it?

- kanban alternatives. so you aren't limited to just kanban

- ios widget

- 7pm, reminds you about anything you need to do before bed. like move chicken from freezer to fridge so it thaws or something. idk how to maintain this without more user intervention.

- timezones


----------------------------------------------------------------------------------------------------------------

### example usage
- user wakes up

- they either open their phone app or log onto their computer -> 

- system updates what it needs to and scans emails. makes a scheudle for that day. the ai writes a brief summary saying how I should tackle it and how it's not actually that hard. maybe a bit of motivation too. 
example: 
    - run dishwasher
    - do leetcode 125, 85, 24
    - make a decent github commit
    - dinner has a baked potatoe
    - cook veggies
    - exfoliate
    - summary: you should cook and store the baked potatoe right now, and run the dishwasher. get those annoying things out of the way. You can try to get the grok backup api working today just as an easy win for you commits. 

- this is viewable as a widget (planned later feature)

- Throughout the day -> Scanning
    -  every 3 hours after that it scans my stuff (computer only). and pushes the info to the server that my phone can read. scan emails, kanban board...

- at some down time in the day, like 2 or 3 pm, an ai will ask how the tasks are going. the user responds, the ai responds, that's it.

- throughout the day, before due times for items (if an item has a due time), the system (not the ai) will remind you about it. like if you need to exfoliate your skin at 9pm it'll remind you at 7pm.




---------------------------------------------------------------------------------
### old stuff

my old rough draft database design:
- table: leetcode problems list
- table: leetcode operations
    - columns: problems (list), date, problems user did (list)
    - problems user did is a list of bools for if they did that problem. indexes map to teh problems column list

- table: scheduled tasks list
    - columns: task, frequency, importance, time of day, reason, date added
- table: scheduled tasks operations
    - purpose: tacks user scheduled tasks results. every time a task goes on the todo list, a row is made in this table
    - columns: task, datetime of last time of reccommendation, user result (bool), missed goal user reason

- table: long term goals list
    - columns: goal, blocking reason, date added, next reminder date
- table: long term goals operations
    - purpose: each time the system asks the user about a goal, a new row is made. this tracks if the user is being dismissive/lazy about a goal long term
    - columns: goal, 2 bullet points about how user will reach goal, did you do prior goals [list of bools, 1 for each time gemma asks if user did their bullet toward their goal]

