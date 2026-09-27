import os
import sys

'''
Testing entry point: runs the monitoring system (app + website tracking) in a
terminal so you can see its output. In normal use the tray app runs the tracker
instead (computer_app/launcher.py, started at login by install_startup.ps1).
Only one tracker can run at a time, so this exits if the tray is already running.
See monitoring_system/README.md and extension/HOW_TO_INSTALL.md to load the
browser extension first.
'''

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
MONITORING_DIR = os.path.join(REPO_DIR, "monitoring_system")

sys.path.insert(0, MONITORING_DIR)
os.chdir(MONITORING_DIR)  # tracker resolves data/ relative to its own dir

from Computer_Tracker import main

if __name__ == "__main__":
    main()
