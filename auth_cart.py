#!/usr/bin/env python3
"""One-time cart OAuth authorization - starts local callback server."""
import os
import sys
import warnings
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from kroger_api import KrogerAPI

SCOPE = os.environ.get("KROGER_SCOPE", "cart.basic:write cart.basic:read")

kroger = KrogerAPI()
auth_code = None
server_done = threading.Event()

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
        else:
            error = params.get("error", ["unknown"])[0]
            desc = params.get("error_description", [""])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h2>Error: {error} - {desc}</h2>".encode())
        server_done.set()

    def log_message(self, format, *args):
        pass

server = HTTPServer(("localhost", 8000), CallbackHandler)
server_thread = threading.Thread(target=lambda: server.handle_request())
server_thread.daemon = True
server_thread.start()

auth_url = kroger.authorization.get_authorization_url(
    scope=SCOPE,
    state="kroger_auth"
)

print("=" * 60)
print(f"KROGER AUTHORIZATION  (scope: {SCOPE})")
print("=" * 60)
print()
print(auth_url)
print()
print("Waiting... (paste the redirect URL if browser doesn't open)")
try:
    webbrowser.open(auth_url)
except Exception:
    pass

server_done.wait(timeout=120)
server.server_close()

if not auth_code:
    print("❌ Timed out.")
    sys.exit(1)

print("Exchanging code for token...")
try:
    token = kroger.authorization.get_token_with_authorization_code(code=auth_code)
    print(f"✅ Token saved! Scope: {token.get('scope', 'unknown')}")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)
