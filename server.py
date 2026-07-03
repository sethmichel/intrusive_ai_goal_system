import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from Config import SERVER_HOST, SERVER_PORT


'''
this is the HTTP server the browser extension posts to. It starts a background HTTPServer and exposes get_latest_url()
so Computer_Tracker.py can read whatever URL the extension last POSTed (used to figure out which site is active in
the browser).
'''


_latest_url = None
_latest_browser = None
_lock = threading.Lock()


class _ExtensionHandler(BaseHTTPRequestHandler):
    """Receives URL POSTs from the browser extension."""

    def do_POST(self):
        global _latest_url, _latest_browser
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            url = data.get("url", "")
            browser = data.get("browser", "")
            if url:
                with _lock:
                    _latest_url = url
                    _latest_browser = browser
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def get_latest_url(process_name):
    """Return the most recently POSTed URL, but only if it was reported by
    process_name (the browser currently in the foreground). This avoids
    misattributing a stale URL from a different browser during the brief
    window between an OS-level focus switch and that browser's extension
    posting its own update."""
    with _lock:
        if _latest_browser != process_name:
            return None
        return _latest_url


def start_server(port=SERVER_PORT):
    server = HTTPServer((SERVER_HOST, port), _ExtensionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port
