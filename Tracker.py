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


def acquire_single_instance_lock(name="RescueTimeClone_Tracker_SingleInstance"):
    """Single-instance guard via a Windows named mutex. Returns an opaque handle
    if this is the only running instance (keep the returned value alive for the
    process lifetime), or None if another instance already holds the lock. The OS
    releases the mutex automatically when the process exits, so there is no stale
    lock file to clean up. Returns True if the mutex couldn't be created at all,
    so a failure here never blocks startup."""
    ERROR_ALREADY_EXISTS = 183
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return True
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return handle
