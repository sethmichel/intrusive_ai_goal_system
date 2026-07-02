"""
Generates one loadable extension folder per browser under extension/build/,
substituting BROWSER_PROCESS into src/background.js and src/manifest.json.

Run this after any change to src/manifest.json or src/background.js, then hit
the reload icon for the extension on each browser's extensions page (no need
to re-pick the folder via "Load unpacked" again).
"""

from pathlib import Path

# folder name under build/ -> BROWSER_PROCESS value (must match Tracker.KNOWN_BROWSERS)
BROWSERS = {
    "chrome": "chrome.exe",
    "brave": "brave.exe",
    "edge": "msedge.exe",
}

SRC_DIR = Path(__file__).parent / "src"
BUILD_DIR = Path(__file__).parent / "build"


def build():
    manifest_template = (SRC_DIR / "manifest.json").read_text(encoding="utf-8")
    background_template = (SRC_DIR / "background.js").read_text(encoding="utf-8")

    for folder_name, browser_process in BROWSERS.items():
        out_dir = BUILD_DIR / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "manifest.json").write_text(
            manifest_template.replace("__BROWSER_PROCESS__", browser_process),
            encoding="utf-8",
        )
        (out_dir / "background.js").write_text(
            background_template.replace("__BROWSER_PROCESS__", browser_process),
            encoding="utf-8",
        )
        print(f"built extension/build/{folder_name}/ ({browser_process})")


if __name__ == "__main__":
    build()
