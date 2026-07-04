const AGENT_URL = "http://127.0.0.1:7834";

// Which browser process this extension instance is running in. Filled in by
// build_extension.py at build time to match Tracker.py's KNOWN_BROWSERS
// (e.g. "chrome.exe", "msedge.exe", "brave.exe"). Can't be detected reliably
// at runtime because Brave's user agent deliberately mimics Chrome's.
const BROWSER_PROCESS = "__BROWSER_PROCESS__";

// Per-tab domain tracking so same-domain navigations don't fire extra POSTs
const tabDomains = {};

function extractDomain(url) {
  try {
    const u = new URL(url);
    // file:// URLs have no hostname (would all collapse to ""), so use the path
    // instead -- otherwise navigating from one local file to another in the same
    // tab would look like "no change" and get silently dropped.
    if (u.protocol === "file:") return u.pathname;
    const h = u.hostname;
    return h.startsWith("www.") ? h.slice(4) : h;
  } catch {
    return "";
  }
}

function postUrl(url) {
  fetch(AGENT_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, browser: BROWSER_PROCESS }),
  }).catch(() => {}); // fire-and-forget
}

// 1. Tab becomes active (user switches tabs)
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab.url) {
      tabDomains[tab.id] = extractDomain(tab.url);
      postUrl(tab.url);
    }
  } catch {}
});

// 2. Tab URL changes (navigation within the same tab)
//    Only fires a POST when the *domain* changes, so
//    youtube.com/watch?v=abc -> youtube.com/watch?v=xyz is ignored.
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!changeInfo.url) return;
  if (!tab.active) return;

  const newDomain = extractDomain(changeInfo.url);
  const oldDomain = tabDomains[tabId] || "";

  tabDomains[tabId] = newDomain;
  if (newDomain === oldDomain) return;

  postUrl(changeInfo.url);
});

// 3. Window focus changes (user switches browser windows)
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) return;
  try {
    const [tab] = await chrome.tabs.query({ active: true, windowId });
    if (tab && tab.url) {
      tabDomains[tab.id] = extractDomain(tab.url);
      postUrl(tab.url);
    }
  } catch {}
});

// Housekeeping: drop domain entry when a tab closes
chrome.tabs.onRemoved.addListener((tabId) => {
  delete tabDomains[tabId];
});
