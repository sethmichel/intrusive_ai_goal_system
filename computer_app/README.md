# computer_app (Windows)

The always-on piece: a tray app that starts at login, runs the monitoring
tracker in the background, and opens the GUI (`gui/app.py`, goals + monitoring
data) when you click its tray icon. Everything is local, with no server.

## setup

```powershell
pip install -r requirements.txt

python launcher.py          # tray icon appears; tracker starts in the background
```

The icon shows up in the taskbar's `^` overflow area. Drag it onto the taskbar
if you want it always visible.

- **Left-click** the icon to open the GUI. If the GUI is already open, it's
  brought to the front instead of opening a second window.
- **Right-click** for **Open** / **Quit**. Quit asks first, since it stops monitoring.
- **Closing the GUI window** only closes the GUI. Monitoring keeps running.
- **Start menu / Windows search "Activity Tracker"** opens the GUI, and also
  starts monitoring + the tray first if you'd quit it.
- Running `launcher.py` again while it's already running just opens the GUI.

The browser extension for website tracking is separate. See
`../monitoring_system/extension/HOW_TO_INSTALL.md`.

## install (startup + Start menu)

```powershell
.\install_startup.ps1               # install
.\install_startup.ps1 -Uninstall    # remove
```

Creates two `Activity Tracker.lnk` shortcuts, both running `pythonw launcher.py`
(no console window):
- **shell:startup**: starts monitoring + the tray at every login.
- **Start menu**: runs with `--open`, so it's searchable and works as "open the app".

It also generates `icon.ico` (the tray icon's drawing) for the shortcuts. The
script refuses to install if that Python is missing the tray dependencies. It
isn't a real installed program: there's no entry in Settings > Apps, and moving
the repo folder breaks the shortcuts until you rerun the script.

## crashes

If the tracker or the tray crashes, a popup says so and the app exits when you
click OK. Nothing restarts it until your next login. Tracebacks go to
`computer_app/launcher.log` (tray + tracker) and `gui/gui.log` (GUI). Both are
only written when running windowless under pythonw.

A GUI error doesn't stop monitoring. A failed button click shows an error popup
and the window stays open. If the whole window crashes, you get a popup, and
monitoring keeps going in the tray.

## dev notes

- pystray runs tray menu actions inside the tray window's message handler, and a
  dialog opened from there never gets mouse clicks. That's why Quit asks from its
  own thread. Anything new in the menu that shows a dialog needs the same treatment.

- `RUN_ME.py` (repo root) runs the tracker in a terminal for testing. The
  tracker holds a single-instance lock, so if the tray is already running it
  exits instead of double-tracking (and vice versa: the tray shows a crash popup
  saying another copy is running).
- `dashboard.py` + `ui/` are the old pywebview dashboard for the Pi server,
  which is out of scope for now. The tray doesn't use them.
