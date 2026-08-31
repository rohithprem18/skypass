import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Add root directory to sys.path so skypass package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from webapp.server import GROUND_STATIONS, build_plan, build_track, records, resolve_site
except Exception as e:
    # Log error if server module fails to load
    print(f"Error loading webapp.server: {e}", file=sys.stderr)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if path in ("/api/stations", "/api/stations/"):
            out = [
                {"key": k, "name": v.name, "lat": v.lat_deg,
                 "lon": v.lon_deg, "alt": v.alt_m}
                for k, v in GROUND_STATIONS.items()
            ]
            self._send_json(200, out)

        elif path in ("/api/plan", "/api/plan/"):
            try:
                out = build_plan(q)
                self._send_json(200, out)
            except Exception as err:
                self._send_json(500, {"error": str(err)})

        elif path in ("/api/track", "/api/track/"):
            try:
                out = build_track(q)
                self._send_json(200, out)
            except Exception as err:
                self._send_json(500, {"error": str(err)})

        else:
            self._send_json(404, {"error": f"Endpoint {path} not found"})

    def _send_json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
