import os
import sys

'''
Entry point for the GUI: goals (home), goal history, and monitoring summaries.
This is what the tray icon opens (computer_app/launcher.py). The tracker doesn't
need to be running to use it; it just reads the goal file and the tracker's
monthly summary CSVs.
'''

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO_DIR, "gui"))

from app import main

if __name__ == "__main__":
    main()
