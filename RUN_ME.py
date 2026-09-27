import os
import sys

'''
Single entry point: run this to start the monitoring system (app + website
tracking). Local-only unless client_config.json exists at repo root (it
doesn't by default) -- see monitoring_system/README.md and
extension/HOW_TO_INSTALL.md to load the browser extension first.
'''

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
MONITORING_DIR = os.path.join(REPO_DIR, "monitoring_system")

sys.path.insert(0, MONITORING_DIR)
os.chdir(MONITORING_DIR)  # tracker resolves data/ relative to its own dir

from Computer_Tracker import main

if __name__ == "__main__":
    main()
