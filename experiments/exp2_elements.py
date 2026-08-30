"""Experiment 2 -- how much does the element set itself limit prediction?

Pass timing is only as good as the orbital elements behind it. Two measurements:

A. Epoch-age distribution of an operationally fetched catalogue -- how old are
   the elements a small station actually plans with?
B. Independent-provider divergence. CelesTrak and AMSAT publish separately
   curated element sets for many of the same objects, usually at different
   epochs. Predicting the same passes from both bounds the timing uncertainty
   that no amount of numerical refinement can remove, and shows how that
   uncertainty grows with the epoch separation.

This is the honest ceiling on SkyPass's 0.06 s numerical agreement: the elements
are worth seconds, not milliseconds.

Usage:
    python experiments/exp2_elements.py [--days 2]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os

from _common import ARCHIVE_DIR, banner, fmt, save, stats

from skypass.config import GROUND_STATIONS, PlannerConfig
from skypass.passes import Tracker, find_passes, match_passes
from skypass.tle import (dedupe, latest_archive, list_archives, load_archive,
                         epoch_age_stats)
from skypass.timeutil import utcnow


def part_a(records, now):
    banner("2A  Element-set epoch age in an operational catalogue")
    st = epoch_age_stats(records, now)
    ages = sorted(r.age_days(now) for r in records)
    buckets = {"<1 d": 0, "1-2 d": 0, "2-3 d": 0, "3-7 d": 0, ">7 d": 0}
    for a in ages:
        if a < 1:
            buckets["<1 d"] += 1
        elif a < 2:
            buckets["1-2 d"] += 1
        elif a < 3:
            buckets["2-3 d"] += 1
        elif a < 7:
            buckets["3-7 d"] += 1
        else:
            buckets[">7 d"] += 1
    print(f"  objects {st['n']}   mean {st['mean']:.2f} d   "
          f"median {st['median']:.2f} d   p90 {st['p90']:.2f} d   "
          f"max {st['max']:.2f} d")
    for k, v in buckets.items():
        print(f"    {k:>7}  {v:4d}  ({100.0 * v / st['n']:5.1f}%)")
    return {"summary": st, "histogram": buckets,
            "deciles": [round(ages[int(q * (len(ages) - 1))], 3)
                        for q in [i / 10 for i in range(11)]]}


def part_b(site, cfg, days, now):
    banner("2B  CelesTrak versus AMSAT element sets for the same objects")
    amsat_files = sorted(f for f in os.listdir(ARCHIVE_DIR)
                         if f.startswith("amsat-"))
    if not amsat_files:
        print("  no AMSAT archive -- run: python -m skypass fetch --amsat")
        return {"skipped": "no amsat archive"}

    ct = dedupe(load_archive(latest_archive(ARCHIVE_DIR)))
    am = dedupe(load_archive(os.path.join(ARCHIVE_DIR, amsat_files[-1])))
    common = sorted(set(ct) & set(am))
    print(f"  objects in both catalogues: {len(common)}")

    t0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = t0 + dt.timedelta(days=days)

    rows, d_tca, d_aos, d_el = [], [], [], []
    by_sep = {}
    for nid in common:
        a, b = ct[nid], am[nid]
        sep = abs((a.epoch - b.epoch).total_seconds()) / 86400.0
        try:
            pa = find_passes(Tracker(site), a.satrec(), a.name, nid, t0, t1, cfg)
            pb = find_passes(Tracker(site), b.satrec(), b.name, nid, t0, t1, cfg)
        except Exception:
            continue
        pairs = [(x, y) for x, y in match_passes(pa, pb, tol_s=600.0)
                 if not (x.clipped or y.clipped)]
        for x, y in pairs:
            dt_tca = abs((x.tca - y.tca).total_seconds())
            d_tca.append(dt_tca)
            d_aos.append(abs((x.aos - y.aos).total_seconds()))
            d_el.append(abs(x.el_max_deg - y.el_max_deg))
            bucket = ("<0.5 d" if sep < 0.5 else "0.5-1 d" if sep < 1.0
                      else "1-2 d" if sep < 2.0 else ">2 d")
            by_sep.setdefault(bucket, []).append(dt_tca)
        if pairs:
            rows.append({"norad_id": nid, "name": a.name,
                         "epoch_sep_days": round(sep, 3),
                         "n_passes": len(pairs),
                         "mean_dtca_s": round(
                             sum(abs((x.tca - y.tca).total_seconds())
                                 for x, y in pairs) / len(pairs), 3)})

    s_tca, s_aos, s_el = stats(d_tca), stats(d_aos), stats(d_el)
    print(f"  matched passes {s_tca.get('n', 0)} over {len(rows)} objects")
    print(f"  |dTCA| s   {fmt(s_tca)}")
    print(f"  |dAOS| s   {fmt(s_aos)}")
    print(f"  |dElMax| deg {fmt(s_el)}")
    print("\n  by epoch separation:")
    order = ["<0.5 d", "0.5-1 d", "1-2 d", ">2 d"]
    sep_stats = {}
    for k in order:
        if k in by_sep:
            s = stats(by_sep[k])
            sep_stats[k] = s
            print(f"    {k:>8}  n={s['n']:4d}  mean {s['mean']:7.2f} s  "
                  f"median {s['median']:7.2f} s  p95 {s['p95']:8.2f} s")
    rows.sort(key=lambda r: -r["mean_dtca_s"])
    return {"n_common": len(common), "n_objects_matched": len(rows),
            "d_tca_s": s_tca, "d_aos_s": s_aos, "d_elmax_deg": s_el,
            "by_epoch_separation": sep_stats,
            "worst_objects": rows[:10]}


def part_c(site, cfg, days, now):
    """If two or more daily archives exist, measure day-over-day divergence."""
    banner("2C  Day-over-day divergence between successive daily archives")
    files = [f for f in list_archives(ARCHIVE_DIR)]
    if len(files) < 2:
        print(f"  only {len(files)} daily archive(s); needs >= 2.")
        print("  Run 'python -m skypass fetch' on separate days to populate.")
        return {"skipped": "fewer than two daily archives",
                "n_archives": len(files)}
    newest = dedupe(load_archive(files[-1]))
    t0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = t0 + dt.timedelta(days=days)
    out = []
    for f in files[:-1]:
        old = dedupe(load_archive(f))
        d = []
        for nid in set(old) & set(newest):
            try:
                pa = find_passes(Tracker(site), newest[nid].satrec(),
                                 newest[nid].name, nid, t0, t1, cfg)
                pb = find_passes(Tracker(site), old[nid].satrec(),
                                 old[nid].name, nid, t0, t1, cfg)
            except Exception:
                continue
            d += [abs((x.tca - y.tca).total_seconds())
                  for x, y in match_passes(pa, pb, tol_s=600.0)
                  if not (x.clipped or y.clipped)]
        age = (dt.date.fromisoformat(os.path.basename(files[-1])[:10])
               - dt.date.fromisoformat(os.path.basename(f)[:10])).days
        s = stats(d)
        out.append({"file": os.path.basename(f), "age_days": age, "d_tca_s": s})
        if s.get("n"):
            print(f"    {os.path.basename(f)}  age {age:2d} d  n={s['n']:5d}  "
                  f"mean {s['mean']:7.2f} s  p95 {s['p95']:8.2f} s")
    return {"archives": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=2.0)
    ap.add_argument("--station", default="chennai")
    args = ap.parse_args()
    site = GROUND_STATIONS[args.station]
    cfg = PlannerConfig()
    now = utcnow()
    records = load_archive(latest_archive(ARCHIVE_DIR))
    print(f"Catalogue: {len(records)} objects, site {site.name}")

    a = part_a(records, now)
    b = part_b(site, cfg, args.days, now)
    c = part_c(site, cfg, args.days, now)
    save("exp2_elements", {"site": site.name, "horizon_days": args.days,
                           "part_a_epoch_age": a,
                           "part_b_provider_divergence": b,
                           "part_c_day_over_day": c})


if __name__ == "__main__":
    main()
