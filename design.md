Files
	• Main.csv
	• Daily-{date}.csv

Tech
	• Python
	• Avoid: flask, fastapi, psutil

	• Agent
		○ Goal: collect data like this: (timestamp, app name, window title)
		○ Poll active window every 3 seconds
			§ Get active window process name and window title
			§ Check if that process is a known browser (chrome.exe, firefox.exe, msedge.exe, brave.exe). just hardcode this
			§ If browser, we need the url from the extension
			§ Compare to the prior poll, if it's the same app/url as last time,  just increment the running duration counter rather than writing a new row
			§ When the app or URL changes, write the completed session (timestamp, app, url) to daily-{date}.csv and start a new counter
			§ The agent runs a tiny local HTTP server (one endpoint) that the extension POSTs to. The agent reads from that whenever it detects a browser is the active window
		○ What gets written to daily-{date}.csv
			§ A row is only written when a session ends (app/url changes)
		○ If a browser is detected/focused but the extension hasn't reported a url, we skip that data point and increment a global counter variable. Play a sound if the variable reaches 10 to alert the user

	• The extension
		○ Goal: We need to monitor time spent on websites in a browser. We'll use a browser extension for this
		○ I use brave which is chromium
		○ A website is defined as the actual website name, not the url. For example, Youtube is the website for both youtube.com/watch?v=abc and youtube.com/watch?v=xyz
		○ Listen for 3 events
			§ Tab becomes active (you switch tabs)
			§ Tab website name changes (you navigate within the same tab)
				□ Again, youtube.com/watch?v=abc and youtube.com/watch?v=xyz should NOT trigger this since it's the same website
			§ Window focus changes (you switch browser windows)
		○ On any of these events, grab the current active tab's URL and POST it to localhost:27182 (or whatever port you pick)
		○ This is fire and forget
		○ So it'll have permission to read the active tabs url and access the current tab

The tricky part of this design is switching websites/apps and recording the correct times on the old website/app. If the extension sees I got to youtube in a browser tab then that's recorded since it's a url change. But then I sit on youtube watching a video for 10 minutes, then I change url's. we need to assume I was on youtube that whole time and the csv storage should reflect that. So, I assume the backend will be able to logically figure that out (not the extension)

	• Storage
		○ To make it as lightweight as possible, we'll use a csv file as a database
		○ We'll have a main csv file as the database
			§ Columns: date, app, website, duration, url
			§ Url is the complete url, website is the url up to '.com' or '.net' or whatever and with the http:// removed, so just the main website name.
		○ We'll have a different csv file which is for the current day. Each day will overwrite the prior day. All new data coming in is written to this csv file, so if the app crashes we still have our data, and we can do basic javascript or python to summarize it into the main storage csv file instead of constantly updating the main csv file
			§ Daily csv columns: timestamp, app, url

Use case examples
	• On open, check if the main csv and the daily csv exist, create them if they don't. 
	• Note that we do not track browsers as apps. If the user is using a browser, we only care about the websites. if app is a browser, skip the app-level entry and only record the websites. chrome.exe, firefox.exe, msedge.exe, brave.exe
	• if the daily csv exists, check its date. If the date is not the current date, then we need to summarize its contents into the main csv as entries for that date. For example, if the daily csv has 6 different apps used, and 12 websites (and note that browser websites count as different activities despite being under the same "app", like facebook and youtube are different but both accessed by "chrome"), that should be 18 entries for that date in the main csv (remember, browsers do not get their own entry, we only care about browser websites)
	• If the user doesn't open it for 2 days, it doesn't matter, we would do the same process.
	• What if the app is open across midnight? If this happens (user starts at 11pm and uses it until 1am), we'll need to make the summary at midnight while the app is running and rename the daily file to be the correct date. For simplicity, during this time of summarizing, we ignore all incoming data. This is data loss but it's very small and won't matter.

Notes
	• A user who launches a browser and hasn't loaded a tab yet, or uses a PDF viewer built into the browser can cause problems with the tracking logic. We'll need to whitelist the 'new tab' url like chrome://newtab, etc. so we don't increment that global counter variable I mentioned in the agent

