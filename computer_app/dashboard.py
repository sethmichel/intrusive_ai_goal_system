import json
import os

import webview

'''
The computer GUI: a pywebview native window rendering ui/index.html (Edge
WebView2 on Win10/11, preinstalled). The HTML talks straight to the Pi's REST
API with fetch -- same contract as the phone app, per v1_design.md. The only
thing Python provides is the client config (server url + token) via js_api.
'''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_CONFIG_PATH = os.path.join(os.path.dirname(BASE_DIR), "client_config.json")


class Bridge:
    def get_config(self):
        try:
            with open(CLIENT_CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            return {"server_url": (cfg.get("server_url") or "").rstrip("/"),
                    "api_token": cfg.get("api_token", "")}
        except (OSError, ValueError):
            return {"server_url": "", "api_token": ""}


def main():
    webview.create_window(
        "Accountability",
        os.path.join(BASE_DIR, "ui", "index.html"),
        js_api=Bridge(),
        width=1150,
        height=850,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
