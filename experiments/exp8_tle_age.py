"""Experiment 8 -- how fast does prediction degrade with element-set age?

This is the measurement the paper previously could only describe as future work.
It needs two element sets for the same object at different epochs, with the
fresher one acting as truth, which a single catalogue snapshot cannot provide.
Space-Track's ``gp_history`` supplies them.

Method
------
For each object we take a *reference* element set whose epoch sits just before a
target instant T, and treat the passes it predicts around T as truth -- it is the
best orbit determination available for that time. We then re-predict the same
passes from progressively older element sets of the same object and measure how
far the predicted culmination has moved. Binning by age = T - epoch gives the
degradation curve directly.

This is the honest error budget for the rest of the paper: Section V-A shows the
numerics agree with an independent implementation to 0.06 s, and this experiment
shows what the *elements* contribute on top of that.

Requires Space-Track credentials (see skypass/spacetrack.py).

Usage:
    python experiments/exp8_tle_age.py [--objects 60] [--days 60]
"""
from __future__ import annotations

import argparse
import datetime as dt
import statistics

from _common import ARCHIVE_DIR, banner, fmt, save, stats

from skypass.config import GROUND_STATIONS, PlannerConfig
from skypass.passes import Tracker, find_passes, match_passes, orbital_period_s
from skypass.spacetrack import CredentialsMissing, SpaceTrack
from skypass.tle import latest_archive, load_archive

AGE_BINS = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 7), (7, 14), (14, 30), (30, 90)]


def bin_of(age_days: float):
    for lo, hi in AGE_BINS:
        if lo <= age_days < hi:
            return f"{lo}-{hi} d"
    return None


def pick_objects(records, limit, max_period_s=7200.0):
    """Well-tracked LEO objects: the regime a small station actually observes.

    Objects in very high orbits are excluded because their passes are long or
    permanent, which makes a culmination-time comparison meaningless.
    """
    out = []
    for r in records:
        try:
            if orbital_period_s(r.satrec()) <= max_period_s:
                out.append(r)
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objects", type=int, default=60)
    ap.add_argument("--days", type=int, default=60,
                    help="how far back to pull element-set history")
    ap.add_argument("--station", default="chennai")
    ap.add_argument("--horizon-hours", type=float, default=24.0,
                    help="pass window evaluated around the target instant")
    args = ap.parse_args()

    site = GROUND_STATIONS[args.station]
    cfg = PlannerConfig()
    records = load_archive(latest_archive(ARCHIVE_DIR))
    chosen = pick_objects(records, args.objects)
    nids = [r.norad_id for r in chosen]

    banner(f"8  Prediction degradation with element-set age "
           f"({len(nids)} LEO objects, {args.days} d of history)")

    try:
        st = SpaceTrack()
    except CredentialsMissing as exc:
        print(f"  SKIPPED: {exc}")
        save("exp8_tle_age", {"skipped": "no Space-Track credentials"})
        return 1

    end = dt.date.today()
    start = end - dt.timedelta(days=args.days)
    hist = st.gp_history(nids, start, end)
    if not hist:
        print("  no history returned")
        return 1

    # Target instant: recent enough that a fresh element set exists, but far
    # enough back that older sets are also available.
    target = dt.datetime.combine(end - dt.timedelta(days=1), dt.time(0, 0))
    t0 = target
    t1 = target + dt.timedelta(hours=args.horizon_hours)

    per_bin = {}
    per_bin_el = {}
    rows = []
    n_obj = 0
    for nid, recs in sorted(hist.items()):
        ref = [r for r in recs if r.epoch <= target]
        if len(ref) < 2:
            continue
        newest = ref[-1]
        ref_age = (target - newest.epoch).total_seconds() / 86400.0
        if ref_age > 1.5:            # reference itself must be fresh
            continue
        try:
            truth = find_passes(Tracker(site), newest.satrec(), newest.name,
                                nid, t0, t1, cfg)
        except Exception:
            continue
        truth = [p for p in truth if not p.clipped]
        if not truth:
            continue
        n_obj += 1

        for old in ref[:-1]:
            age = (target - old.epoch).total_seconds() / 86400.0
            b = bin_of(age)
            if b is None:
                continue
            try:
                pred = find_passes(Tracker(site), old.satrec(), old.name,
                                   nid, t0, t1, cfg)
            except Exception:
                continue
            pred = [p for p in pred if not p.clipped]
            pairs = match_passes(pred, truth, tol_s=1800.0)
            for a, t in pairs:
                d = abs((a.tca - t.tca).total_seconds())
                per_bin.setdefault(b, []).append(d)
                per_bin_el.setdefault(b, []).append(
                    abs(a.el_max_deg - t.el_max_deg))
                rows.append({"norad_id": nid, "age_days": round(age, 3),
                             "d_tca_s": round(d, 3),
                             "d_elmax_deg": round(abs(a.el_max_deg
                                                      - t.el_max_deg), 4)})

    if not rows:
        print("  no comparable passes found")
        save("exp8_tle_age", {"skipped": "no comparable passes"})
        return 1

    print(f"\n  objects with a fresh reference : {n_obj}")
    print(f"  aged comparisons               : {len(rows)}")
    print(f"\n  {'age of element set':>20}{'N':>7}{'mean |dTCA|':>13}"
          f"{'median':>10}{'p95':>10}{'mean |dEl|':>12}")
    table = {}
    for lo, hi in AGE_BINS:
        b = f"{lo}-{hi} d"
        if b not in per_bin:
            continue
        s = stats(per_bin[b])
        se = stats(per_bin_el[b])
        table[b] = {"d_tca_s": s, "d_elmax_deg": se}
        print(f"  {b:>20}{s['n']:>7}{s['mean']:>13.2f}{s['median']:>10.2f}"
              f"{s['p95']:>10.2f}{se['mean']:>12.4f}")

    overall = stats([r["d_tca_s"] for r in rows])
    print(f"\n  overall |dTCA|: {fmt(overall)}")

    # A simple slope in seconds of timing error per day of element-set age,
    # fitted through the bin means, is the number a planner actually needs.
    xs, ys = [], []
    for lo, hi in AGE_BINS:
        b = f"{lo}-{hi} d"
        if b in table and table[b]["d_tca_s"]["n"] >= 5:
            xs.append((lo + hi) / 2.0)
            ys.append(table[b]["d_tca_s"]["mean"])
    slope = None
    if len(xs) >= 3:
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx > 0:
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
            print(f"  growth rate: {slope:.2f} s of culmination error "
                  f"per day of element-set age")

    save("exp8_tle_age", {
        "station": site.name, "n_objects": n_obj, "n_comparisons": len(rows),
        "history_days": args.days, "target": target.isoformat(),
        "horizon_hours": args.horizon_hours,
        "by_age": table, "overall_d_tca_s": overall,
        "growth_s_per_day": slope,
        "samples": rows[:500]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
