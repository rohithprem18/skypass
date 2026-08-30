"""Experiment 6 -- end-to-end pipeline: funnel, runtime, and robustness.

A. The visibility funnel and wall-clock cost of a full operational plan, for
   every preset ground station. This is the "what does it actually do" table.
B. Sensitivity of the produced timetable to the score weights. If a planner's
   output flips completely when w_elev moves from 0.4 to 0.6, the weighting is
   doing the deciding rather than the physics; Jaccard overlap against the
   default settles that.
C. Runtime scaling with catalogue size and planning horizon.

Usage:
    python experiments/exp6_pipeline.py [--days 7]
"""
from __future__ import annotations

import argparse

from _common import ARCHIVE_DIR, RESULTS_DIR, banner, save

from skypass.config import GROUND_STATIONS, PlannerConfig, ScoreWeights
from skypass.pipeline import plan
from skypass.report import format_plan, write_csv, write_ics, write_json
from skypass.scoring import MODE_OPTICAL, MODE_RADIO
from skypass.tle import latest_archive, load_archive
from skypass.weather import WeatherUnavailable, forecast


def part_a(records, days, cfg):
    banner("6A  Operational plan at every station (optical, weather-aware)")
    print(f"  {'station':<20}{'passes':>8}{'sunlit':>8}{'dark':>7}{'bright':>8}"
          f"{'clear':>7}{'cand':>6}{'sched':>7}{'runtime s':>11}")
    rows = {}
    for key, site in GROUND_STATIONS.items():
        r = plan(site=site, days=days, records=records, cfg=cfg,
                 mode=MODE_OPTICAL, weather_aware=True, fetch_weather=True)
        f = r.funnel
        rows[key] = r.summary()
        print(f"  {site.name[:19]:<20}{f.geometric:8d}{f.sunlit:8d}"
              f"{f.dark_sky:7d}{f.bright_enough:8d}{f.cloud_clear:7d}"
              f"{f.above_floor:6d}{f.scheduled:7d}"
              f"{r.runtime['total']:11.1f}")
    return rows


def part_a_radio(records, days, cfg):
    banner("6A'  Same catalogue, radio mode (no illumination constraint)")
    print(f"  {'station':<20}{'passes':>8}{'cand':>7}{'sched':>7}{'runtime s':>11}")
    rows = {}
    for key, site in GROUND_STATIONS.items():
        r = plan(site=site, days=days, records=records, cfg=cfg,
                 mode=MODE_RADIO, weather_aware=False, fetch_weather=False)
        f = r.funnel
        rows[key] = r.summary()
        print(f"  {site.name[:19]:<20}{f.geometric:8d}{f.above_floor:7d}"
              f"{f.scheduled:7d}{r.runtime['total']:11.1f}")
    return rows


def part_b(records, days, cfg, site):
    banner("6B  Sensitivity of the timetable to the score weights")
    # Fetch the forecast once and reuse it: every weighting must see exactly the
    # same sky, or the comparison measures the weather rather than the weights.
    try:
        clouds = forecast(site, days=int(days) + 1)
    except WeatherUnavailable as exc:
        print(f"  [warn] weather unavailable ({exc}); continuing blind")
        clouds = None
    ref = plan(site=site, days=days, records=records, cfg=cfg,
               weights=ScoreWeights(w_elev=0.5, w_dur=0.5),
               clouds=clouds, weather_aware=True, fetch_weather=False)
    ref_keys = {p.key() for p in ref.schedule.selected}
    print(f"  {'w_elev':>7}{'w_dur':>7}{'sched':>7}{'Jaccard':>9}"
          f"{'mean elMax':>12}{'mean dur s':>12}{'mean cloud':>12}")
    rows = []
    for w in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0):
        r = plan(site=site, days=days, records=records, cfg=cfg,
                 weights=ScoreWeights(w_elev=w, w_dur=1.0 - w),
                 clouds=clouds, weather_aware=True, fetch_weather=False)
        sel = r.schedule.selected
        keys = {p.key() for p in sel}
        jac = (len(keys & ref_keys) / len(keys | ref_keys)) if (keys | ref_keys) else 1.0
        el = sum(p.el_max_deg for p in sel) / max(len(sel), 1)
        du = sum(p.duration_s for p in sel) / max(len(sel), 1)
        cl = [p.detail.get("cloud") for p in sel if p.detail.get("cloud") is not None]
        mc = sum(cl) / len(cl) if cl else float("nan")
        rows.append({"w_elev": w, "w_dur": 1.0 - w, "n_scheduled": len(sel),
                     "jaccard_vs_default": jac, "mean_el_max_deg": el,
                     "mean_duration_s": du, "mean_cloud": mc})
        print(f"  {w:7.1f}{1 - w:7.1f}{len(sel):7d}{jac:9.3f}"
              f"{el:12.1f}{du:12.0f}{mc:12.3f}")
    return rows


def part_c(records, cfg, site):
    banner("6C  Runtime scaling")
    rows = []
    print(f"  {'objects':>8}{'days':>6}{'passes':>8}{'propagations':>14}"
          f"{'propagate s':>13}{'score s':>9}{'sched s':>9}{'total s':>9}")
    for n_obj in (50, 150, 300, 635):
        for days in (1, 7):
            r = plan(site=site, days=days, records=records[:n_obj], cfg=cfg,
                     weather_aware=False, fetch_weather=False)
            t = r.runtime
            rows.append({"n_objects": n_obj, "days": days,
                         "n_passes": r.funnel.geometric,
                         "propagations": r.propagations,
                         "propagate_s": t["propagate"], "score_s": t["score"],
                         "schedule_s": t["schedule"], "total_s": t["total"]})
            print(f"  {n_obj:8d}{days:6d}{r.funnel.geometric:8d}"
                  f"{r.propagations:14,}{t['propagate']:13.2f}"
                  f"{t['score']:9.2f}{t['schedule']:9.3f}{t['total']:9.2f}")
    return rows


def part_d(records, days, cfg, site):
    """Emit a real deliverable so the exported artefacts are exercised."""
    banner("6D  Exported artefacts for the demonstration plan")
    r = plan(site=site, days=days, records=records, cfg=cfg,
             mode=MODE_OPTICAL, weather_aware=True, fetch_weather=True)
    sel = r.schedule.selected
    out_dir = RESULTS_DIR
    paths = {
        "csv": write_csv(sel, f"{out_dir}/demo_schedule.csv"),
        "ics": write_ics(sel, f"{out_dir}/demo_schedule.ics", site.name),
        "json": write_json(r, f"{out_dir}/demo_plan.json"),
    }
    with open(f"{out_dir}/demo_plan.txt", "w", encoding="utf-8") as fh:
        fh.write(format_plan(r, limit=40))
    paths["txt"] = f"{out_dir}/demo_plan.txt"
    for k, v in paths.items():
        print(f"  {k:>5}  {v}")
    print()
    print(format_plan(r, limit=12))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--station", default="chennai")
    ap.add_argument("--limit", type=int, default=635)
    args = ap.parse_args()

    cfg = PlannerConfig()
    records = load_archive(latest_archive(ARCHIVE_DIR))[:args.limit]
    site = GROUND_STATIONS[args.station]
    print(f"Catalogue {len(records)} objects, horizon {args.days} d")

    a = part_a(records, args.days, cfg)
    ar = part_a_radio(records, args.days, cfg)
    b = part_b(records, args.days, cfg, site)
    c = part_c(records, cfg, site)
    d = part_d(records, args.days, cfg, site)
    save("exp6_pipeline", {"horizon_days": args.days, "n_objects": len(records),
                           "part_a_optical": a, "part_a_radio": ar,
                           "part_b_weight_sensitivity": b,
                           "part_c_scaling": c, "part_d_artefacts": d})


if __name__ == "__main__":
    main()
