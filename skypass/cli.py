"""Command-line interface: ``python -m skypass <command>``."""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from .config import (DEFAULT_SITE, GROUND_STATIONS, PlannerConfig,
                     ScoreWeights, Site)
from .passes import Tracker
from .pipeline import load_catalogue, plan, propagate_all
from .report import format_passes, format_plan, write_csv, write_ics, write_json
from .scoring import MODE_OPTICAL, MODE_RADIO
from .timeutil import utcnow
from .tle import (archive_path, dedupe, epoch_age_stats, fetch_amsat,
                  fetch_celestrak, list_archives, load_archive,
                  write_archive)


def resolve_site(args) -> Site:
    base = GROUND_STATIONS.get((args.station or "").lower(), DEFAULT_SITE)
    kw = {}
    if args.lat is not None:
        kw["lat_deg"] = args.lat
    if args.lon is not None:
        kw["lon_deg"] = args.lon
    if args.alt is not None:
        kw["alt_m"] = args.alt
    if args.name:
        kw["name"] = args.name
    if args.mask is not None:
        kw["min_elev_deg"] = args.mask
    if args.twilight is not None:
        kw["twilight_deg"] = args.twilight
    if args.gap is not None:
        kw["setup_gap_min"] = args.gap
    return base.with_(**kw) if kw else base


# ---------------------------------------------------------------------------
def cmd_fetch(args) -> int:
    print("Fetching element sets...")
    recs = fetch_celestrak()
    if args.amsat:
        recs += fetch_amsat()
    best = dedupe(recs)
    if not best:
        print("No element sets retrieved.", file=sys.stderr)
        return 1
    path = archive_path(args.archive_dir)
    n = write_archive(sorted(best.values(), key=lambda r: r.norad_id), path)
    stats = epoch_age_stats(best.values(), utcnow())
    print(f"Archived {n} unique objects -> {path}")
    print(f"Element-set age: median {stats['median']:.2f} d, "
          f"p90 {stats['p90']:.2f} d, max {stats['max']:.2f} d")
    return 0


def cmd_stations(args) -> int:
    print(f"{'key':<12}{'name':<24}{'lat':>9}{'lon':>10}{'alt m':>8}")
    for k, s in GROUND_STATIONS.items():
        print(f"{k:<12}{s.name:<24}{s.lat_deg:9.3f}{s.lon_deg:10.3f}{s.alt_m:8.0f}")
    return 0


def cmd_passes(args) -> int:
    site = resolve_site(args)
    cfg = PlannerConfig()
    recs, stale = load_catalogue(args.archive_dir, t=utcnow(), cfg=cfg,
                                 limit=args.limit, name_filter=args.sat)
    t0 = utcnow()
    t1 = t0 + dt.timedelta(days=args.days)
    tracker = Tracker(site)
    ps, _ = propagate_all(recs, tracker, t0, t1, cfg)
    print(f"{site.name}: {len(ps)} geometric passes from {len(recs)} objects "
          f"over {args.days} d (mask {site.min_elev_deg:.0f} deg)\n")
    print(format_passes(ps, limit=args.limit_rows, show_score=False))
    return 0


def cmd_plan(args) -> int:
    site = resolve_site(args)
    weights = ScoreWeights(w_elev=args.w_elev, w_dur=1.0 - args.w_elev)
    res = plan(site=site, days=args.days,
               mode=MODE_RADIO if args.radio else MODE_OPTICAL,
               weather_aware=not args.no_weather,
               fetch_weather=not args.no_weather,
               weights=weights, archive_dir=args.archive_dir,
               limit=args.limit, name_filter=args.sat, verbose=True)
    print(format_plan(res, limit=args.limit_rows))
    sel = res.schedule.selected if res.schedule else []
    if args.csv:
        print(f"\nCSV  -> {write_csv(sel, args.csv)}")
    if args.ics:
        print(f"ICS  -> {write_ics(sel, args.ics, site.name)}")
    if args.json:
        print(f"JSON -> {write_json(res, args.json, include_all=args.json_all)}")
    return 0


def cmd_archives(args) -> int:
    files = list_archives(args.archive_dir)
    if not files:
        print("No archives yet. Run: python -m skypass fetch")
        return 1
    for f in files:
        recs = load_archive(f)
        print(f"{f}  {len(recs):5d} objects")
    return 0


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="skypass",
        description="Weather-aware integrated satellite transit planner.")
    ap.add_argument("--archive-dir", default="tle_archive")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def site_args(p):
        p.add_argument("--station", help="preset key (see 'stations')")
        p.add_argument("--lat", type=float)
        p.add_argument("--lon", type=float)
        p.add_argument("--alt", type=float)
        p.add_argument("--name")
        p.add_argument("--mask", type=float, help="elevation mask, deg")
        p.add_argument("--twilight", type=float, help="dark-sky sun elevation, deg")
        p.add_argument("--gap", type=float, help="setup gap between targets, min")
        p.add_argument("--sat", help="comma-separated name substrings")
        p.add_argument("--limit", type=int, help="cap catalogue size")
        p.add_argument("--limit-rows", type=int, default=30)

    p = sub.add_parser("fetch", help="download and archive element sets")
    p.add_argument("--amsat", action="store_true",
                   help="also merge the AMSAT set")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("stations", help="list preset ground stations")
    p.set_defaults(func=cmd_stations)

    p = sub.add_parser("archives", help="list archived element-set files")
    p.set_defaults(func=cmd_archives)

    p = sub.add_parser("passes", help="list geometric passes (no scoring)")
    site_args(p)
    p.add_argument("--days", type=float, default=1.0)
    p.set_defaults(func=cmd_passes)

    p = sub.add_parser("plan", help="full weather-aware plan and timetable")
    site_args(p)
    p.add_argument("--days", type=float, default=7.0)
    p.add_argument("--radio", action="store_true",
                   help="radio mode: ignore illumination and magnitude")
    p.add_argument("--no-weather", action="store_true",
                   help="ablation: plan weather-blind")
    p.add_argument("--w-elev", type=float, default=0.5,
                   help="weight on the elevation term (duration gets 1-w)")
    p.add_argument("--csv"), p.add_argument("--ics"), p.add_argument("--json")
    p.add_argument("--json-all", action="store_true")
    p.set_defaults(func=cmd_plan)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
