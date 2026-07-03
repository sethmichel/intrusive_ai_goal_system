import ctypes
from ctypes import wintypes

'''
low-level Windows window-tracking logic: it uses ctypes to call Win32 APIs (GetForegroundWindow, QueryFullProcessImageNameW, etc.) 
to get the current foreground process name/title, and has helpers is_browser() / is_new_tab_url() to classify browsers and filter 
out new-tab pages
'''


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

KNOWN_BROWSERS = frozenset({
    "chrome.exe",
    "firefox.exe",
    "msedge.exe",
    "brave.exe",
})

NEW_TAB_PATTERNS = frozenset({
    "chrome://newtab",
    "chrome://new-tab-page",
    "edge://newtab",
    "brave://newtab",
    "about:newtab",
    "about:blank",
    "about:home",
})

# Label written to the daily CSV's "app" column for the end-marker row that
# closes out a session when the user switches to a new (blank) browser tab.
# Kept distinct from "" so the daily CSV isn't confusing, but still dropped
# during summarize_daily_csv() same as a truly blank app.
NEW_TAB_LABEL = "blank browser tab"


def get_active_window():
    """Return (process_name, window_title) for the foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None, None

    h_process = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
    )
    if not h_process:
        return None, None

    try:
        buf = ctypes.create_unicode_buffer(512)
        buf_size = wintypes.DWORD(512)
        ok = kernel32.QueryFullProcessImageNameW(
            h_process, 0, buf, ctypes.byref(buf_size)
        )
        if not ok:
            return None, None
        process_name = buf.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(h_process)

    title_buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buf, 512)

    return process_name, title_buf.value


def is_browser(process_name):
    return process_name in KNOWN_BROWSERS if process_name else False


def is_new_tab_url(url):
    if not url:
        return False
    cleaned = url.lower().split("?")[0].split("#")[0].rstrip("/")
    return cleaned in NEW_TAB_PATTERNS
