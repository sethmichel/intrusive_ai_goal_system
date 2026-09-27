import ctypes
import os
import subprocess
import sys
import threading
import traceback
from datetime import datetime

'''
The always-on Windows piece: starts at logon (install_startup.ps1 puts a pythonw.exe shortcut in
shell:startup, so there's no console window), runs the monitoring tracker in a background thread,
and sits in the system tray (the ^ overflow area on the taskbar) via pystray.

Tray: left-click opens the GUI (gui/app.py via RUN_GUI.py). Right-click menu: Open / Quit.
The GUI is its own process, so closing its window only ends the GUI -- the tracker and tray keep
running. Only "Quit" stops monitoring. The GUI refuses to open a second window and focuses the
existing one instead, so clicking the tray icon repeatedly never stacks windows.

Start menu: install_startup.ps1 also adds an "Activity Tracker" Start menu shortcut (searchable)
that runs this with --open: starts the tray if it isn't running, and opens the GUI either way.

Crashes: if the tracker thread or the tray dies, fatal_crash() logs the traceback, shows an
error popup, and the process exits once the user clicks OK. Nothing restarts it until next logon.

Manual run:  python launcher.py [--open]   (running it again while it's already up just opens the GUI)
'''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
MONITORING_DIR = os.path.join(REPO_DIR, "monitoring_system")
RUN_GUI_PATH = os.path.join(REPO_DIR, "RUN_GUI.py")
LOG_PATH = os.path.join(BASE_DIR, "launcher.log")
APP_NAME = "Activity Tracker"
TRAY_LOCK_NAME = "ActivityTracker_Tray_SingleInstance"

MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONERROR = 0x10
MB_ICONQUESTION = 0x20
MB_DEFBUTTON2 = 0x100
MB_SETFOREGROUND = 0x10000
MB_TOPMOST = 0x40000
IDYES = 6

sys.path.insert(0, MONITORING_DIR)

# under pythonw.exe stdout/stderr are None and any print() would crash the
# tracker thread -- send everything to a log file instead
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(LOG_PATH, "a", buffering=1)

_crash_lock = threading.Lock()


def log(message):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)  # flush: fatal paths os._exit right after


def message_box(text, flags):
    """Native Windows popup. Blocks the calling thread until dismissed; works from any thread
    and without a GUI toolkit, so it still works when the thing that broke is the tray."""
    return ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, flags | MB_SETFOREGROUND | MB_TOPMOST)


def fatal_crash(what, details="", headline=f"{APP_NAME} crashed and monitoring has stopped."):
    """Last stop for anything that means this process can't keep monitoring: log it, show a popup,
    and exit once the user clicks OK. The lock makes a second failure (e.g. the tray dying while
    the first popup is up) wait here instead of stacking popups; os._exit then takes it down too."""
    with _crash_lock:
        log(f"FATAL: {what}\n{details}")
        if details.strip():
            what += "\n" + details.strip().splitlines()[-1]  # the exception line, e.g. "ValueError: ..."
        message_box(
            f"{headline}\n\n{what}\n\n"
            f"Full details are in:\n{LOG_PATH}\n\n"
            f"Click OK to close it. It starts again at your next login, or open it from the Start menu.",
            MB_OK | MB_ICONERROR,
        )
        os._exit(1)


def run_tracker():
    try:
        from Computer_Tracker import main as tracker_main
        tracker_main()
    except Exception:
        fatal_crash("The monitoring tracker crashed.", traceback.format_exc())
    # tracker_main() only returns on its own when another tracker already holds its single-instance lock
    fatal_crash("Another copy of the tracker is already running (RUN_ME.py in a terminal?), so this one "
                "is closing. Monitoring continues in that copy.", headline=f"{APP_NAME} can't start its tracker.")


def open_gui(icon=None, item=None):
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    subprocess.Popen([exe, RUN_GUI_PATH], cwd=REPO_DIR)


def quit_app(icon, item):
    # pystray runs menu actions inside the tray window's message handler, right after the popup
    # menu closes, and a dialog opened from there never receives mouse clicks (Yes/No are dead).
    # So ask from a fresh thread and hand control straight back to pystray. The lock ignores
    # repeat Quit clicks while the question is already up.
    if _quit_prompt_lock.acquire(blocking=False):
        threading.Thread(target=_confirm_quit, args=(icon,), name="quit-prompt", daemon=True).start()


def _confirm_quit(icon):
    try:
        answer = message_box("Quit and stop monitoring?\n\nIt won't track anything again until your next login "
                             "(or until you open it from the Start menu).", MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2)
        if answer != IDYES:
            return
        log("quit from tray")
        icon.visible = False  # remove it now; a hard exit can leave a dead icon in the tray until hovered
        icon.stop()
        # tracker thread is a daemon and its CSV summarizer heals the missing
        # end-marker on next start, so a hard exit is safe here
        os._exit(0)
    finally:
        _quit_prompt_lock.release()


_quit_prompt_lock = threading.Lock()


def make_icon_image(size=64):
    from PIL import Image, ImageDraw
    s = size / 64  # drawn on a 64px grid, scaled so install_startup.ps1 can make a sharp 256px .ico
    img = Image.new("RGB", (size, size), (30, 30, 46))
    d = ImageDraw.Draw(img)
    d.ellipse((8 * s, 8 * s, 56 * s, 56 * s), fill=(137, 180, 250))
    d.line((22 * s, 34 * s, 30 * s, 42 * s), fill=(30, 30, 46), width=round(6 * s))  # checkmark
    d.line((30 * s, 42 * s, 44 * s, 22 * s), fill=(30, 30, 46), width=round(6 * s))
    return img


def write_icon_file(path):
    """The .ico the Start menu / startup shortcuts show (same drawing as the tray icon)."""
    make_icon_image(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])


def main(open_on_start=False):
    from Tracker import acquire_single_instance_lock

    tray_lock = acquire_single_instance_lock(TRAY_LOCK_NAME)
    if tray_lock is None:
        # already running in the tray: treat launching it again as "open the app"
        open_gui()
        return
    if open_on_start:
        open_gui()

    # any other thread dying uncaught also means something is broken
    threading.excepthook = lambda args: fatal_crash(
        f"Unexpected error in thread {args.thread.name if args.thread else '?'}.",
        "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
    )

    import pystray
    # pystray converts the icon to .ico to show it; ICO isn't one of Pillow's preloaded formats, so
    # without this it imports all ~45 image plugins to find it (~2 MB for nothing)
    from PIL import IcoImagePlugin  # noqa: F401

    log("starting tracker + tray")
    threading.Thread(target=run_tracker, name="tracker", daemon=True).start()

    icon = pystray.Icon(
        "activity_tracker",
        make_icon_image(),
        f"{APP_NAME} (monitoring)",
        menu=pystray.Menu(
            pystray.MenuItem("Open", open_gui, default=True),  # default = left-click action
            pystray.MenuItem("Quit", quit_app),
        ),
    )
    icon.run()
    # icon.run() only returns if the tray loop ended without going through quit_app
    fatal_crash("The system tray icon stopped unexpectedly.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--write-icon"]:
        write_icon_file(sys.argv[2])
        sys.exit(0)
    try:
        main(open_on_start="--open" in sys.argv[1:])
    except Exception:
        fatal_crash("Couldn't start.", traceback.format_exc())
