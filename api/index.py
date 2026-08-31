import datetime as dt
import json
import os
import sys
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Add root directory to sys.path so skypass package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IMPORT_ERROR = None
try:
    from skypass.passes import Pass
    from skypass.report import write_ics
    from webapp.server import GROUND_STATIONS, build_plan, build_track, records
except Exception as e:
    # Log error if server module fails to load
    IMPORT_ERROR = e
    print(f"Error loading webapp.server: {e}", file=sys.stderr)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if IMPORT_ERROR is not None:
            self._send_json(500, {
                "error": type(IMPORT_ERROR).__name__,
                "detail": str(IMPORT_ERROR),
            })
            return

        if path in ("/api/stations", "/api/stations/"):
            try:
                total = len(records())
            except Exception:
                total = 0
            self._send_json(200, {
                "stations": [
                    {"key": k, "name": v.name, "lat": v.lat_deg,
                     "lon": v.lon_deg, "alt": v.alt_m}
                    for k, v in GROUND_STATIONS.items()
                ],
                "catalogue": total,
                "using": min(140, total),
            })

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

        elif path in ("/api/ics", "/api/ics/"):
            try:
                data = build_plan(q)
                objs = []
                for p in data["passes"]:
                    obj = Pass(name=p["name"], norad_id=p["norad_id"],
                               aos=dt.datetime.fromisoformat(p["aos"]),
                               tca=dt.datetime.fromisoformat(p["tca"]),
                               los=dt.datetime.fromisoformat(p["los"]),
                               el_max_deg=p["el_max"], az_aos_deg=p["az_aos"],
                               az_tca_deg=p["az_tca"], az_los_deg=p["az_los"],
                               range_tca_km=p["range_km"])
                    obj.score = p["score"]
                    obj.detail = {k: p[k] for k in ("magnitude", "cloud")
                                  if p.get(k) is not None}
                    objs.append(obj)
                tmp = os.path.join(tempfile.gettempdir(), "skypass-plan.ics")
                write_ics(objs, tmp, data["site"]["name"])
                with open(tmp, "rb") as fh:
                    body = fh.read()
                self._send_bytes(200, body, "text/calendar; charset=utf-8",
                                 {"Content-Disposition":
                                  'attachment; filename="skypass-plan.ics"'})
            except Exception as err:
                traceback.print_exc()
                self._send_json(500, {"error": type(err).__name__,
                                      "detail": str(err)})

        else:
            self._send_json(404, {"error": f"Endpoint {path} not found"})

    def _send_json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self._send_bytes(code, body, "application/json; charset=utf-8")

    def _send_bytes(self, code, body, content_type, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
