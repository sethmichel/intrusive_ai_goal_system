import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

_latest_url = None
_lock = threading.Lock()


class _ExtensionHandler(BaseHTTPRequestHandler):
    """Receives URL POSTs from the browser extension."""

    def do_POST(self):
        global _latest_url
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            url = data.get("url", "")
            if url:
                with _lock:
                    _latest_url = url
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def get_latest_url():
    """Return the most recently POSTed URL (or None if nothing received yet)."""
    with _lock:
        return _latest_url


def start_server(port=7834):
    server = HTTPServer(("127.0.0.1", port), _ExtensionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port
