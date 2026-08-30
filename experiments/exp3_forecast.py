"""Experiment 3 -- is a cloud forecast good enough to plan observations with?

Weather-aware planning is only worth doing if the forecast carries skill at the
lead times an observer plans over. This experiment verifies archived operational
forecasts against ERA5 reanalysis at every site, for lead times of 1 to 7 days,
and compares them against the two baselines any forecast must beat:

persistence
    "tomorrow's sky looks like today's"
climatology
    "assume the seasonal mean cloudiness"

The decision being scored is binary and operational: *is this hour clear enough
to observe?* Accuracy alone is misleading when clear hours are rare, so the
Heidke skill score (HSS) is reported: 0 means no better than chance, 1 is
perfect.

Usage:
    python experiments/exp3_forecast.py [--days 60]
"""
from __future__ import annotations

import argparse

from _common import banner, past_window, save

from skypass.config import GROUND_STATIONS
from skypass.weather import (climatology_series, persistence_series,
                             previous_runs, reanalysis, skill_scores)

LEADS = (1, 2, 3, 4, 5, 6, 7)


def evaluate_site(key, site, start, end, clear_threshold):
    print(f"\n  {site.name}  ({start} .. {end})")
    truth = reanalysis(site, start, end)
    if len(truth) == 0:
        print("    no reanalysis data")
        return None
    runs = previous_runs(site, start, end, lead_days=LEADS)

    out = {"site": site.name, "lat": site.lat_deg, "lon": site.lon_deg,
           "n_truth_hours": len(truth), "leads": {}, "baselines": {}}

    mean_cloud = sum(truth.values.values()) / len(truth)
    clear_rate = sum(1 for v in truth.values.values()
                     if v <= clear_threshold) / len(truth)
    out["mean_cloud"] = mean_cloud
    out["clear_hour_rate"] = clear_rate
    print(f"    ERA5 mean cloud {100 * mean_cloud:.1f}%   "
          f"clear hours ({100 * clear_threshold:.0f}% thr) {100 * clear_rate:.1f}%")
    print(f"    {'lead':>6} {'MAE':>7} {'RMSE':>7} {'bias':>7} "
          f"{'acc':>6} {'POD':>6} {'FAR':>6} {'HSS':>6}")

    for lead in sorted(runs):
        s = skill_scores(runs[lead], truth, clear_threshold)
        if not s.get("n"):
            continue
        out["leads"][str(lead)] = s
        print(f"    {lead:>6} {s['mae']:7.3f} {s['rmse']:7.3f} {s['bias']:+7.3f} "
              f"{s['accuracy']:6.3f} {s['pod']:6.3f} {s['far']:6.3f} "
              f"{s['hss']:6.3f}")

    for label, series in (("persistence_24h", persistence_series(truth, 24)),
                          ("climatology", climatology_series(truth))):
        s = skill_scores(series, truth, clear_threshold)
        out["baselines"][label] = s
        if s.get("n"):
            print(f"    {label:>18}  MAE {s['mae']:.3f}  acc {s['accuracy']:.3f}"
                  f"  HSS {s['hss']:.3f}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--clear-threshold", type=float, default=0.30)
    ap.add_argument("--stations", default="all")
    args = ap.parse_args()

    start, end = past_window(args.days)
    keys = (list(GROUND_STATIONS) if args.stations == "all"
            else [s.strip() for s in args.stations.split(",")])

    banner(f"3  Cloud-forecast skill vs lead time  ({args.days} d, "
           f"clear = cloud <= {100 * args.clear_threshold:.0f}%)")
    sites = {}
    for k in keys:
        try:
            r = evaluate_site(k, GROUND_STATIONS[k], start, end,
                              args.clear_threshold)
        except Exception as exc:                     # noqa: BLE001
            print(f"    [warn] {k}: {exc}")
            continue
        if r:
            sites[k] = r

    # Pooled across sites, per lead time.
    banner("3  Pooled across all sites")
    pooled = {}
    print(f"  {'lead':>6} {'MAE':>7} {'RMSE':>7} {'acc':>6} {'POD':>6} "
          f"{'FAR':>6} {'HSS':>6}")
    for lead in [str(x) for x in (0,) + LEADS]:
        rows = [s["leads"][lead] for s in sites.values() if lead in s["leads"]]
        if not rows:
            continue
        n = sum(r["n"] for r in rows)
        agg = {k: sum(r[k] * r["n"] for r in rows) / n
               for k in ("mae", "rmse", "bias", "accuracy", "pod", "far", "hss")}
        agg["n"] = n
        agg["n_sites"] = len(rows)
        pooled[lead] = agg
        print(f"  {lead:>6} {agg['mae']:7.3f} {agg['rmse']:7.3f} "
              f"{agg['accuracy']:6.3f} {agg['pod']:6.3f} {agg['far']:6.3f} "
              f"{agg['hss']:6.3f}")
    pooled_base = {}
    for label in ("persistence_24h", "climatology"):
        rows = [s["baselines"][label] for s in sites.values()
                if s["baselines"].get(label, {}).get("n")]
        if not rows:
            continue
        n = sum(r["n"] for r in rows)
        agg = {k: sum(r[k] * r["n"] for r in rows) / n
               for k in ("mae", "rmse", "accuracy", "pod", "far", "hss")}
        agg["n"] = n
        pooled_base[label] = agg
        print(f"  {label:>18}  MAE {agg['mae']:.3f}  acc {agg['accuracy']:.3f}"
              f"  HSS {agg['hss']:.3f}")

    save("exp3_forecast", {
        "window": {"start": start.isoformat(), "end": end.isoformat(),
                   "days": args.days},
        "clear_threshold": args.clear_threshold,
        "sites": sites, "pooled": pooled, "pooled_baselines": pooled_base})


if __name__ == "__main__":
    main()
