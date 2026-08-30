"""SkyPass web application -- a local server for the planner.

Deliberately built on the standard library. The planner itself needs only
``sgp4``; making the web interface drag in a framework would mean anyone
reproducing this work has to install more than the paper requires. A JSON API
this small does not justify the dependency.

Every number the interface shows comes from the same ``skypass`` package the
paper validates. Nothing is reimplemented here, so the app cannot drift from
the published results.

Usage:
    python webapp/server.py            # then open http://localhost:8000
    python webapp/server.py --port 8080 --host 0.0.0.0   # expose on the LAN
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skypass.config import (DEFAULT_SITE, GROUND_STATIONS, PlannerConfig,
                            ScoreWeights, Site)
from skypass.geometry import site_ecef, sun_elevation
from skypass.passes import Tracker
from skypass.pipeline import plan
from skypass.report import compass, write_ics
from skypass.scheduler import capacity_schedule, observing_night
from skypass.scoring import MODE_OPTICAL, MODE_RADIO
from skypass.timeutil import utcnow
from skypass.tle import latest_archive, load_archive

# Importable both as `python webapp/server.py` and as `webapp.server`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from context import (conflict_map, darkness_windows,  # noqa: E402
                     hourly_cloud, night_summaries, sunlit_fraction,
                     twilight, twilight_bands)

_HERE = os.path.dirname(os.path.abspath(__file__))
#: Serve the built React app when it exists, and fall back to the dependency-free
#: vanilla build otherwise, so `python webapp/server.py` works whether or not
#: anyone has run `npm run build`.
_DIST = os.path.join(_HERE, "ui", "dist")
STATIC = _DIST if os.path.isfile(os.path.join(_DIST, "index.html"))     else os.path.join(_HERE, "static")
from skypass.paths import TLE_ARCHIVE_DIR as ARCHIVE

#: Catalogue slice used by the interface. The full 635-object catalogue takes
#: minutes to propagate over a week, which is not an interactive experience;
#: the brightest few hundred objects are also the ones an observer can see.
WEB_OBJECT_LIMIT = 140

_LOCK = threading.Lock()
_RECORDS = None


def records():
    """Load and cache the element sets once per process."""
    global _RECORDS
    with _LOCK:
        if _RECORDS is None:
            _RECORDS = load_archive(latest_archive(ARCHIVE))
        return _RECORDS


def sky_track(site, sat, p, n=28):
    """Azimuth/elevation samples across a pass, for the sky chart.

    An observer needs to know *where to look*, not just when, so the interface
    draws the arc the object traces. Sampling here (rather than in the browser)
    keeps SGP4 in one place.
    """
    tracker = Tracker(site)
    out = []
    total = (p.los - p.aos).total_seconds()
    if total <= 0:
        return out
    for i in range(n + 1):
        t = p.aos + dt.timedelta(seconds=total * i / n)
        o = tracker.observe(sat, t)
        if o and o.el_deg >= -1:
            out.append({"az": round(o.az_deg, 2), "el": round(o.el_deg, 2),
                        "t": t.isoformat(timespec="seconds")})
    return out


def resolve_site(q) -> Site:
    """Build a Site from a preset key or explicit coordinates."""
    key = (q.get("station") or "").lower()
    base = GROUND_STATIONS.get(key, DEFAULT_SITE)
    kw = {}
    for field, name, cast in (("lat", "lat_deg", float),
                              ("lon", "lon_deg", float),
                              ("alt", "alt_m", float),
                              ("mask", "min_elev_deg", float),
                              ("twilight", "twilight_deg", float),
                              ("gap", "setup_gap_min", float)):
        if q.get(field) not in (None, ""):
            try:
                kw[name] = cast(q[field])
            except (TypeError, ValueError):
                pass
    if q.get("name"):
        kw["name"] = str(q["name"])[:60]
    elif kw.get("lat_deg") is not None and not key:
        kw["name"] = f"{kw['lat_deg']:.3f}, {kw.get('lon_deg', 0):.3f}"
    return base.with_(**kw) if kw else base


def build_plan(q):
    """Run the planner and shape the result for the interface."""
    site = resolve_site(q)
    days = max(0.5, min(float(q.get("days", 2) or 2), 7.0))
    mode = MODE_RADIO if q.get("mode") == "radio" else MODE_OPTICAL
    weather = q.get("weather", "1") not in ("0", "false", "no")
    try:
        capacity = int(q.get("capacity") or 0)
    except (TypeError, ValueError):
        capacity = 0

    cfg = PlannerConfig()
    recs = records()[:WEB_OBJECT_LIMIT]

    # Fetch the forecast once so the weather-aware and "if it cleared" views
    # see the same sky and the second view costs no extra network call.
    clouds = None
    if weather:
        try:
            from skypass.weather import forecast
            clouds = forecast(site, days=int(min(16, max(1, days + 1))))
        except Exception:                              # noqa: BLE001
            clouds = None

    result = plan(site=site, days=days, records=recs, cfg=cfg, mode=mode,
                  weather_aware=weather, clouds=clouds, fetch_weather=False,
                  weights=ScoreWeights())

    # An observing budget is what makes the weather forecast worth consulting
    # (Sec. V-D of the paper), so the interface offers it as a first-class knob.
    sched = result.schedule
    if capacity > 0 and result.candidates:
        sched = capacity_schedule(result.candidates, site.setup_gap_min,
                                  capacity=capacity, per_night=True,
                                  lon_deg=site.lon_deg)

    sats = {}
    for r in recs:
        try:
            sats[r.norad_id] = r.satrec()
        except Exception:
            continue

    tracker = Tracker(site)

    def shape(selected):
        return [_pass_json(site, sats, p, tracker=tracker) for p in selected]

    chosen = sched.selected if sched else []
    passes = shape(chosen)

    # Everything that cleared the visibility floor, selected or not. The
    # explorer and the scheduler-decision panel both need the passes that lost,
    # not just the ones that won.
    conflicts = conflict_map(result.candidates, chosen, site.setup_gap_min)
    picked = {(c.norad_id, c.aos) for c in chosen}
    candidates = [
        _pass_json(site, sats, c, tracker=tracker, track=False,
                   selected=(c.norad_id, c.aos) in picked,
                   conflicts=conflicts.get(c.norad_id, []))
        for c in result.candidates
    ]

    # When the forecast wipes the list out, an empty screen is the wrong
    # answer: the observer cannot tell "clouded out" from "nothing up there".
    # Re-plan ignoring weather so the interface can say which it is.
    if_clear, blocked = [], 0
    if weather and clouds is not None and not passes:
        alt = plan(site=site, days=days, records=recs, cfg=cfg, mode=mode,
                   weather_aware=False, clouds=clouds, fetch_weather=False,
                   weights=ScoreWeights())
        alt_sched = alt.schedule
        if capacity > 0 and alt.candidates:
            alt_sched = capacity_schedule(alt.candidates, site.setup_gap_min,
                                          capacity=capacity, per_night=True,
                                          lon_deg=site.lon_deg)
        if_clear = shape((alt_sched.selected if alt_sched else [])[:12])
        blocked = len(alt_sched.selected) if alt_sched else 0

    clouds_seen = [p["cloud"] for p in (passes or if_clear)
                   if p.get("cloud") is not None]
    mean_cloud = (sum(clouds_seen) / len(clouds_seen)) if clouds_seen else None

    f = result.funnel
    return {
        "site": {"name": site.name, "lat": site.lat_deg, "lon": site.lon_deg,
                 "alt": site.alt_m, "mask": site.min_elev_deg},
        "window": {"from": result.t0.isoformat(timespec="seconds"),
                   "to": result.t1.isoformat(timespec="seconds"),
                   "days": days},
        "mode": mode,
        "weather_used": result.weather_used,
        "capacity": capacity,
        "funnel": {"catalogue": f.catalogue, "geometric": f.geometric,
                   "sunlit": f.sunlit, "dark": f.dark_sky,
                   "bright": f.bright_enough, "clear": f.cloud_clear,
                   "candidates": f.above_floor, "scheduled": len(passes)},
        "runtime_s": round(result.runtime.get("total", 0.0), 2),
        "propagations": result.propagations,
        "passes": passes,
        "if_clear": if_clear,
        "blocked_by_weather": blocked,
        "candidates": candidates,
        "nights": night_summaries(result.candidates, chosen, site.lon_deg),
        "hourly": hourly_cloud(clouds, result.t0, result.t1),
        "twilight": twilight(site, result.t0, result.t1),
        "darkness": darkness_windows(site, result.t0, result.t1),
        "bands": twilight_bands(site, result.t0, result.t1),
        "setup_gap_min": site.setup_gap_min,
        "mean_cloud": round(mean_cloud, 3) if mean_cloud is not None else None,
        "generated": utcnow().isoformat(timespec="seconds"),
    }


def _pass_json(site, sats, p, tracker=None, track=True, selected=True,
               conflicts=None):
    """One pass, shaped for the interface.

    ``track`` is off for table-only rows: sampling a sky arc for every
    candidate costs 29 SGP4 calls each and nothing draws them.
    """
    d = p.detail or {}
    sat = sats.get(p.norad_id)
    return {
        "selected": selected,
        "conflicts": conflicts or [],
        "sunlit": (sunlit_fraction(tracker, sat, p) if tracker is not None
                   else None),
        "sun_elev": d.get("sun_elev_deg"),
        "phase_deg": d.get("phase_deg"),
        "name": p.name,
        "norad_id": p.norad_id,
        "aos": p.aos.isoformat(timespec="seconds"),
        "tca": p.tca.isoformat(timespec="seconds"),
        "los": p.los.isoformat(timespec="seconds"),
        "duration_s": round(p.duration_s),
        "el_max": round(p.el_max_deg, 1),
        "az_aos": round(p.az_aos_deg, 1),
        "az_tca": round(p.az_tca_deg, 1),
        "az_los": round(p.az_los_deg, 1),
        "dir_aos": compass(p.az_aos_deg),
        "dir_tca": compass(p.az_tca_deg),
        "dir_los": compass(p.az_los_deg),
        "range_km": round(p.range_tca_km),
        "magnitude": d.get("magnitude"),
        "cloud": d.get("cloud"),
        "score": round(p.score, 3),
        "priority": p.priority,
        "night": observing_night(p, site.lon_deg).isoformat(),
        "track": sky_track(site, sat, p) if (sat and track) else [],
    }


def build_track(q):
    """Azimuth/elevation samples for one pass, addressed by object and time.

    Independent of any plan: the caller already knows which object and which
    horizon-to-horizon interval it wants, so this needs an element set and two
    timestamps, not a re-run of the scheduler.
    """
    site = resolve_site(q)
    try:
        norad = int(q.get("norad") or 0)
    except (TypeError, ValueError):
        norad = 0
    aos = q.get("aos")
    los = q.get("los")
    if not norad or not aos:
        return {"track": []}

    rec = next((r for r in records() if r.norad_id == norad), None)
    if rec is None:
        return {"track": []}

    t_aos = dt.datetime.fromisoformat(aos)
    if los:
        t_los = dt.datetime.fromisoformat(los)
    else:
        # Fall back to a generous LEO pass length; the arc is clipped to the
        # horizon below, so an over-long window costs samples, not correctness.
        t_los = t_aos + dt.timedelta(minutes=20)

    tracker = Tracker(site)
    sat = rec.satrec()
    total = max(1.0, (t_los - t_aos).total_seconds())
    out = []
    for i in range(41):
        t = t_aos + dt.timedelta(seconds=total * i / 40)
        o = tracker.observe(sat, t)
        if o and o.el_deg >= -1:
            out.append({"az": round(o.az_deg, 2), "el": round(o.el_deg, 2),
                        "t": t.isoformat(timespec="seconds")})
    return {"track": out}


class Handler(BaseHTTPRequestHandler):
    server_version = "SkyPass/1.0"

    def log_message(self, fmt, *args):        # quieter console
        sys.stderr.write(f"  {self.address_string()} {fmt % args}\n")

    # -- helpers ---------------------------------------------------------
    def _send(self, code, body, ctype="application/json; charset=utf-8",
              extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj, extra=None):
        self._send(code, json.dumps(obj, default=str), extra=extra)

    def _static(self, rel):
        rel = rel.lstrip("/") or "index.html"
        path = os.path.normpath(os.path.join(STATIC, rel))
        # Never serve outside the static directory.
        if not path.startswith(STATIC):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        if not os.path.isfile(path):
            # Single-page app: unknown non-asset paths render the shell.
            if "." not in os.path.basename(path):
                path = os.path.join(STATIC, "index.html")
            if not os.path.isfile(path):
                return self._send(404, "not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(path, "rb") as fh:
            self._send(200, fh.read(), ctype)

    # -- routes ----------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._static("index.html")
            if u.path == "/api/stations":
                return self._json(200, {
                    "stations": [
                        {"key": k, "name": s.name, "lat": s.lat_deg,
                         "lon": s.lon_deg, "alt": s.alt_m}
                        for k, s in GROUND_STATIONS.items()],
                    "catalogue": len(records()),
                    "using": min(WEB_OBJECT_LIMIT, len(records())),
                })
            if u.path == "/api/plan":
                return self._json(200, build_plan(q))
            if u.path == "/api/track":
                return self._json(200, build_track(q))
            if u.path == "/api/ics":
                return self._ics(q)
            return self._static(u.path)
        except FileNotFoundError as exc:
            self._json(503, {"error": "no element sets on disk. Run: "
                                      "python -m skypass fetch",
                             "detail": str(exc)})
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": type(exc).__name__, "detail": str(exc)})

    def _ics(self, q):
        """Return the current plan as a calendar file."""
        from skypass.passes import Pass
        data = build_plan(q)
        objs = []
        for p in data["passes"]:
            o = Pass(name=p["name"], norad_id=p["norad_id"],
                     aos=dt.datetime.fromisoformat(p["aos"]),
                     tca=dt.datetime.fromisoformat(p["tca"]),
                     los=dt.datetime.fromisoformat(p["los"]),
                     el_max_deg=p["el_max"], az_aos_deg=p["az_aos"],
                     az_tca_deg=p["az_tca"], az_los_deg=p["az_los"],
                     range_tca_km=p["range_km"])
            o.score = p["score"]
            o.detail = {k: p[k] for k in ("magnitude", "cloud")
                        if p.get(k) is not None}
            objs.append(o)
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "skypass-plan.ics")
        write_ics(objs, tmp, data["site"]["name"])
        with open(tmp, "rb") as fh:
            body = fh.read()
        self._send(200, body, "text/calendar; charset=utf-8",
                   {"Content-Disposition":
                    'attachment; filename="skypass-plan.ics"'})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1",
                    help="use 0.0.0.0 to reach it from a phone on the same Wi-Fi")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    try:
        n = len(records())
    except FileNotFoundError:
        print("No element sets found. Run first:  python -m skypass fetch")
        return 1

    ui = "React (ui/dist)" if STATIC.endswith("dist") else "vanilla (static/)"
    print(f"SkyPass web  --  {n} objects loaded, "
          f"{min(WEB_OBJECT_LIMIT, n)} used for planning")
    print(f"  serving {ui}")
    print(f"  http://{'localhost' if args.host == '127.0.0.1' else args.host}"
          f":{args.port}")
    if args.host == "0.0.0.0":
        print("  (reachable from other devices on this network)")
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
