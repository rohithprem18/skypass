"""Experiment 7 -- why weather-awareness helps where it does.

Experiment 4 shows that a forecast is worth nothing to a station with a fixed
nightly quota and a great deal to one that may skip nights. This experiment
measures the two quantities that explain that result, so the mechanism is
evidence rather than assertion.

A. Cloud structure. How much of the variation in observed cloud lies *between*
   observing nights versus *within* one? A forecast can only help a
   quota-constrained planner by discriminating within a night; if cloud barely
   varies there, there is nothing to discriminate.

B. Pass-quality structure. How much does the weather-free value of a pass vary?
   The score is a product, so a planner chasing clear sky must give up base
   value. If pass quality varies more than sky quality, that trade loses.

C. Forecast informativeness at the actual candidate-pass timestamps, which is
   the only place it is ever applied.

Usage:
    python experiments/exp7_structure.py [--days 30]
"""
from __future__ import annotations

import argparse
import statistics

from _common import ARCHIVE_DIR, banner, past_window, save

from exp4_weather_value import build_candidates

from skypass.config import GROUND_STATIONS, PlannerConfig, ScoreWeights
from skypass.scheduler import observing_night
from skypass.tle import latest_archive, load_archive
from skypass.weather import previous_runs


def correlation(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / ((sxx * syy) ** 0.5) if sxx * syy > 0 else float("nan")


def analyse(site, cands, fc_series):
    for c in cands:
        c["cloud_fc"] = fc_series.at(c["pass"].tca)
    usable = [c for c in cands if c["cloud_fc"] is not None]
    if len(usable) < 20:
        return None

    # --- A: cloud structure ------------------------------------------------
    nights = {}
    for c in usable:
        nights.setdefault(observing_night(c["pass"], site.lon_deg), []).append(c)
    multi = [v for v in nights.values() if len(v) >= 3]
    night_means = [statistics.fmean([c["cloud_true"] for c in v]) for v in multi]
    within_sd = [statistics.pstdev([c["cloud_true"] for c in v]) for v in multi]
    between_sd = statistics.pstdev(night_means) if len(night_means) > 1 else 0.0
    mean_within = statistics.fmean(within_sd) if within_sd else 0.0

    # --- B: pass-quality structure ----------------------------------------
    bases = sorted(c["base"] for c in usable)
    n = len(bases)
    base_mean = statistics.fmean(bases)
    base_p90 = bases[int(0.90 * (n - 1))]
    base_max = bases[-1]

    # --- C: forecast informativeness at pass times -------------------------
    r = correlation([c["cloud_fc"] for c in usable],
                    [c["cloud_true"] for c in usable])
    k = max(1, len(usable) // 10)
    top_fc = sorted(usable, key=lambda c: c["cloud_fc"])[:k]
    top_base = sorted(usable, key=lambda c: -c["base"])[:k]
    cloud_top_fc = statistics.fmean([c["cloud_true"] for c in top_fc])
    cloud_all = statistics.fmean([c["cloud_true"] for c in usable])
    cloud_top_base = statistics.fmean([c["cloud_true"] for c in top_base])

    return {
        "site": site.name,
        "n_candidates": len(usable),
        "n_nights": len(nights),
        "n_nights_multi": len(multi),
        "cloud_between_night_sd": between_sd,
        "cloud_within_night_sd": mean_within,
        "between_within_ratio": (between_sd / mean_within
                                 if mean_within > 1e-9 else None),
        "base_mean": base_mean,
        "base_p90": base_p90,
        "base_max": base_max,
        "base_p90_over_mean": base_p90 / base_mean if base_mean else None,
        "forecast_corr_at_passes": r,
        "cloud_all": cloud_all,
        "cloud_top_decile_by_forecast": cloud_top_fc,
        "cloud_top_decile_by_base": cloud_top_base,
        "cloud_reduction_by_forecast": cloud_all - cloud_top_fc,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--lead", type=int, default=1)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--stations", default="all")
    args = ap.parse_args()

    cfg, weights = PlannerConfig(), ScoreWeights()
    records = load_archive(latest_archive(ARCHIVE_DIR))[:args.limit]
    start, end = past_window(args.days)
    keys = (list(GROUND_STATIONS) if args.stations == "all"
            else [s.strip() for s in args.stations.split(",")])

    banner(f"7  Structure of cloud and of pass quality ({args.days} d, "
           f"{len(records)} objects)")
    print(f"  window {start} .. {end}")
    print(f"\n  {'station':<18}{'cand':>6}{'btwn SD':>9}{'wthn SD':>9}"
          f"{'ratio':>7}{'p90/mean':>10}{'corr':>7}{'dCloud':>8}")

    rows = {}
    for k in keys:
        site = GROUND_STATIONS[k]
        try:
            cands, _ = build_candidates(site, records, start, end, cfg, weights)
            if not cands:
                continue
            fc = previous_runs(site, start, end, lead_days=(args.lead,))[args.lead]
            r = analyse(site, cands, fc)
        except Exception as exc:                      # noqa: BLE001
            print(f"  [warn] {k}: {type(exc).__name__}: {exc}")
            continue
        if not r:
            continue
        rows[k] = r
        print(f"  {r['site'][:17]:<18}{r['n_candidates']:6d}"
              f"{r['cloud_between_night_sd']:9.3f}"
              f"{r['cloud_within_night_sd']:9.3f}"
              f"{(r['between_within_ratio'] or 0):7.2f}"
              f"{(r['base_p90_over_mean'] or 0):10.2f}"
              f"{r['forecast_corr_at_passes']:+7.3f}"
              f"{r['cloud_reduction_by_forecast']:+8.3f}")

    if rows:
        agg = {
            "between_within_ratio": statistics.fmean(
                [r["between_within_ratio"] for r in rows.values()
                 if r["between_within_ratio"]]),
            "base_p90_over_mean": statistics.fmean(
                [r["base_p90_over_mean"] for r in rows.values()
                 if r["base_p90_over_mean"]]),
            "forecast_corr_at_passes": statistics.fmean(
                [r["forecast_corr_at_passes"] for r in rows.values()]),
            "cloud_reduction_by_forecast": statistics.fmean(
                [r["cloud_reduction_by_forecast"] for r in rows.values()]),
        }
        print(f"\n  Pooled: cloud varies {agg['between_within_ratio']:.1f}x more "
              f"between nights than within one.")
        print(f"          the top-decile pass is worth "
              f"{agg['base_p90_over_mean']:.1f}x the mean pass.")
        print(f"          forecast/observed correlation at pass times: "
              f"{agg['forecast_corr_at_passes']:+.3f}")
        print(f"          selecting the clearest-forecast decile lowers observed "
              f"cloud by {agg['cloud_reduction_by_forecast']:.3f}.")
        save("exp7_structure", {"window": {"start": start.isoformat(),
                                           "end": end.isoformat(),
                                           "days": args.days},
                                "forecast_lead_days": args.lead,
                                "n_objects": len(records),
                                "sites": rows, "pooled": agg})


if __name__ == "__main__":
    main()
