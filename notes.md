run with agent.py


Optimization
	• If the user hasn't touched mouse or keyboard for X seconds (you pick the threshold, 60s is common), pause the duration counter. We'd need to update the duration of the old activity along with the changing to a enw activity. This still doesn't prevent a YouTube tab racking up 8 hours because you left it open
	• I don't really care about minor logic gaps around the edge case of having the app open across midnight. Unless it crashes the app
	• Regarding daily-{date}.csv. We're writing each event as a new row to this file. So we'll figure out durations when we summarize by using all the timestamps.
