"""Experiment 9 -- uncertainty on the weather-value gains.

Experiment 4 reports the headline gains as point estimates pooled over the
stations. A point estimate alone says nothing about how much of the gain is
an accident of which stations happened to be in the panel, so this experiment
attaches a confidence interval to each one.

Design
------
The evaluation is a clustered design: nights within a station are not
independent (cloud is autocorrelated, which is the paper's own finding), so the
resampling unit is the *station*, not the pass or the night. For each budget
mode we recompute the per-station arms over exactly the window Experiment 4
used, then take a cluster bootstrap: resample the stations with replacement,
re-pool, and recompute the gain with the same pooling code Experiment 4 uses.
Percentile intervals are reported.

With six stations the intervals are wide. That is the honest width for this
design, and it is the point: the panel is small, so the pooled gain carries
real uncertainty that a bare "+37.6%" hides.

The window, object limit and all planner settings are read back from
results/exp4_weather_value.json so this cannot drift from the run the paper
reports. The recomputed point estimates are checked against the stored ones
before any resampling is done.

Usage:
    python experiments/exp9_bootstrap.py [--resamples 10000] [--seed 20260101]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import banner, load, save  # noqa: E402

from exp4_weather_value import (ARMS, evaluate_site,  # noqa: E402
                                pool, pooled_gains)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skypass.config import GROUND_STATIONS, PlannerConfig, ScoreWeights  # noqa: E402
from skypass.paths import TLE_ARCHIVE_DIR as ARCHIVE_DIR  # noqa: E402
from skypass.tle import latest_archive, load_archive  # noqa: E402

#: Gains we attach intervals to, as (key in exp4 output, label).
TRACKED = [("gain_clear_pct", "clear-sky gain"),
           ("gain_ev_pct", "expected-value gain"),
           ("oracle_gain_clear_pct", "oracle clear-sky headroom"),
           ("raw_gain_clear_pct", "uncalibrated clear-sky gain")]


def percentile(xs, q):
    """Percentile of a sample, linear interpolation between order statistics."""
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def bootstrap_gains(per_site, resamples, rng):
    """Cluster bootstrap over stations; returns {key: {lo, hi, mean, point}}."""
    point = pooled_gains(pool(per_site))
    draws = {k: [] for k, _ in TRACKED}
    n = len(per_site)
    for _ in range(resamples):
        sample = [per_site[rng.randrange(n)] for _ in range(n)]
        g = pooled_gains(pool(sample))
        for k, _ in TRACKED:
            v = g.get(k)
            if v is not None:
                draws[k].append(v)
    out = {}
    for k, _ in TRACKED:
        d = draws[k]
        out[k] = {
            "point": point.get(k),
            "lo": percentile(d, 0.025),
            "hi": percentile(d, 0.975),
            "mean": sum(d) / len(d) if d else None,
            "n_draws": len(d),
            "share_positive": (sum(1 for x in d if x > 0) / len(d)) if d else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resamples", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--tolerance", type=float, default=0.5,
                    help="max |recomputed - stored| in percentage points")
    args = ap.parse_args()

    src = load("exp4_weather_value")
    start = dt.date.fromisoformat(src["window"]["start"][:10])
    end = dt.date.fromisoformat(src["window"]["end"][:10])
    keys = list(src["sites"])
    capacity = src["capacity_per_night"]
    lead = src["forecast_lead_days"]
    thresh = src["clear_threshold"]
    train = src["train_days"]
    n_obj = src["n_objects"]
    n_nights = src["n_nights"]

    banner(f"9  Uncertainty on the weather-value gains "
           f"({len(keys)} stations, {args.resamples} resamples)")
    print(f"  window {start} .. {end}   (read back from experiment 4)")
    print(f"  stations: {', '.join(keys)}")

    cfg, weights = PlannerConfig(), ScoreWeights()
    records = load_archive(latest_archive(ARCHIVE_DIR))[:n_obj]

    modes = [("nightly-quota", None)]
    for frac in (0.75, 0.5, 0.25):
        modes.append(("budget-%dpct" % int(100 * frac),
                      max(1, int(round(frac * capacity * n_nights)))))

    caches = {k: {} for k in keys}
    rng = random.Random(args.seed)
    results, checks = {}, []

    for mode, budget in modes:
        per = []
        for k in keys:
            r = evaluate_site(GROUND_STATIONS[k], records, start, end, cfg,
                              weights, lead, thresh, capacity, train,
                              verbose=False, cache=caches[k],
                              total_budget=budget)
            if r:
                per.append(r)
        if len(per) != len(keys):
            print(f"  [warn] {mode}: {len(per)}/{len(keys)} stations evaluated")

        # the recomputation must reproduce experiment 4 before we trust it
        recomputed = pooled_gains(pool(per))
        stored = src["budget_modes"][mode]
        drift = {k: abs((recomputed[k] or 0) - (stored[k] or 0))
                 for k, _ in TRACKED if stored.get(k) is not None}
        worst = max(drift.values()) if drift else 0.0
        checks.append((mode, worst))
        status = "ok" if worst <= args.tolerance else "DRIFT"
        print(f"\n  {mode:<16} budget {str(budget):>5}   "
              f"reproduces experiment 4: {status} (max drift {worst:.3f} pp)")

        results[mode] = {"total_budget": budget,
                         "bootstrap": bootstrap_gains(per, args.resamples, rng),
                         "max_drift_pp": worst,
                         "per_site": {s["site"]: {a: s["arms"][a] for a in ARMS}
                                      for s in per}}
        for key, label in TRACKED:
            b = results[mode]["bootstrap"][key]
            if b["point"] is None:
                continue
            print(f"      {label:<30} {b['point']:+7.1f}%  "
                  f"95% CI [{b['lo']:+.1f}, {b['hi']:+.1f}]  "
                  f"P(>0)={b['share_positive']:.2f}")

    worst_overall = max(w for _, w in checks)
    print(f"\n  largest drift from experiment 4: {worst_overall:.3f} pp "
          f"(tolerance {args.tolerance})")
    if worst_overall > args.tolerance:
        print("  [warn] recomputation does not reproduce experiment 4; "
              "intervals are NOT comparable to the reported point estimates")

    save("exp9_bootstrap", {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "stations": keys, "n_objects": n_obj, "capacity_per_night": capacity,
        "forecast_lead_days": lead, "clear_threshold": thresh,
        "train_days": train, "n_nights": n_nights,
        "resamples": args.resamples, "seed": args.seed,
        "resampling_unit": "station (cluster bootstrap)",
        "interval": "percentile, 95%",
        "reproduces_exp4_within_pp": worst_overall,
        "modes": results})


if __name__ == "__main__":
    main()
