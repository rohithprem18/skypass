"""Experiment 1 -- prediction accuracy and propagator cost.

Two questions:

A. Is the coarse-bracket + bisection pass finder as accurate as brute-force
   dense sampling, and how many propagator calls does it save?
B. Does the whole SkyPass chain (frame transform, topocentric geometry, event
   finding) agree with an independently written implementation? Skyfield shares
   only the certified SGP4 core, so agreement validates everything downstream.

Usage:
    python experiments/exp1_accuracy.py [--days 1] [--max-sats 120]
"""
from __future__ import annotations

import argparse
import datetime as dt

from _common import ARCHIVE_DIR, banner, fmt, save, stats

from skypass.config import GROUND_STATIONS, PlannerConfig
from skypass.passes import (Tracker, find_passes, find_passes_dense,
                            match_passes)
from skypass.tle import latest_archive, load_archive
from skypass.timeutil import utcnow


def part_a(records, site, t0, t1, cfg, max_sats):
    banner("1A  Coarse+bisection versus dense 1 s sampling")
    d_aos, d_tca, d_los, d_el = [], [], [], []
    calls_fast = calls_dense = 0
    n_clipped = [0]
    n_fast_total = n_dense_total = 0
    missed = spurious = 0
    n_sats = 0

    for r in records[:max_sats]:
        try:
            sat = r.satrec()
        except Exception:
            continue
        tf, td = Tracker(site), Tracker(site)
        try:
            fast = find_passes(tf, sat, r.name, r.norad_id, t0, t1, cfg)
            dense = find_passes_dense(td, sat, r.name, r.norad_id, t0, t1,
                                      step_s=1.0)
        except Exception:
            continue
        n_sats += 1
        calls_fast += tf.counter.calls
        calls_dense += td.counter.calls
        n_fast_total += len(fast)
        n_dense_total += len(dense)
        pairs = match_passes(fast, dense, tol_s=300.0)
        missed += len(dense) - len(pairs)
        spurious += len(fast) - len(pairs)
        for a, b in pairs:
            # An always-up object (geostationary, high MEO) yields only
            # window-clipped intervals whose AOS/TCA/LOS are window edges, not
            # horizon crossings. Including them would measure nothing.
            if a.clipped or b.clipped:
                n_clipped[0] += 1
                continue
            d_aos.append(abs((a.aos - b.aos).total_seconds()))
            d_tca.append(abs((a.tca - b.tca).total_seconds()))
            d_los.append(abs((a.los - b.los).total_seconds()))
            d_el.append(abs(a.el_max_deg - b.el_max_deg))

    s_aos, s_tca, s_los, s_el = (stats(d_aos), stats(d_tca), stats(d_los),
                                 stats(d_el))
    reduction = calls_dense / max(calls_fast, 1)
    print(f"  satellites            {n_sats}")
    print(f"  passes (fast/dense)   {n_fast_total} / {n_dense_total}")
    print(f"  matched pairs         {s_aos.get('n', 0)}")
    print(f"  missed / spurious     {missed} / {spurious}")
    print(f"  clipped (excluded)    {n_clipped[0]}")
    print(f"  |dAOS| s   {fmt(s_aos)}")
    print(f"  |dTCA| s   {fmt(s_tca)}")
    print(f"  |dLOS| s   {fmt(s_los)}")
    print(f"  |dElMax| deg {fmt(s_el, prec=4)}")
    print(f"  propagator calls: fast {calls_fast:,}  dense {calls_dense:,}"
          f"  -> {reduction:.1f}x fewer")
    return {
        "n_satellites": n_sats,
        "n_passes_fast": n_fast_total,
        "n_passes_dense": n_dense_total,
        "n_matched": s_aos.get("n", 0),
        "missed": missed,
        "spurious": spurious,
        "clipped_excluded": n_clipped[0],
        "recall": (n_dense_total - missed) / max(n_dense_total, 1),
        "d_aos_s": s_aos, "d_tca_s": s_tca, "d_los_s": s_los,
        "d_elmax_deg": s_el,
        "calls_fast": calls_fast, "calls_dense": calls_dense,
        "call_reduction": reduction,
    }


def part_b(records, site, t0, t1, cfg, max_sats):
    banner("1B  SkyPass versus Skyfield (independent implementation)")
    try:
        from skyfield.api import EarthSatellite, load, wgs84
    except ImportError:
        print("  skyfield not installed -- skipping (pip install skyfield)")
        return {"skipped": "skyfield not installed"}

    ts = load.timescale(builtin=True)
    station = wgs84.latlon(site.lat_deg, site.lon_deg, elevation_m=site.alt_m)
    tsf0 = ts.utc(t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second)
    tsf1 = ts.utc(t1.year, t1.month, t1.day, t1.hour, t1.minute, t1.second)

    d_aos, d_tca, d_los, d_el = [], [], [], []
    n_sats = n_sf = n_sp = 0
    for r in records[:max_sats]:
        try:
            sat = r.satrec()
            sfsat = EarthSatellite(r.line1, r.line2, r.name, ts)
        except Exception:
            continue
        n_sats += 1
        mine = find_passes(Tracker(site), sat, r.name, r.norad_id, t0, t1, cfg)
        times, events = sfsat.find_events(station, tsf0, tsf1,
                                          altitude_degrees=site.min_elev_deg)
        theirs, cur = [], {}
        for t, e in zip(times, events):
            u = t.utc_datetime().replace(tzinfo=None)
            if e == 0:
                cur = {"aos": u}
            elif e == 1 and "aos" in cur:
                cur["tca"] = u
                cur["el"] = sfsat.at(t).observe if False else None
            elif e == 2 and "aos" in cur and "tca" in cur:
                cur["los"] = u
                theirs.append(cur)
                cur = {}
        n_sp += len(mine)
        n_sf += len(theirs)
        for m in mine:
            if m.clipped:
                continue
            best, bd = None, None
            for q in theirs:
                d = abs((q["tca"] - m.tca).total_seconds())
                if bd is None or d < bd:
                    best, bd = q, d
            if best is None or bd > 300.0:
                continue
            d_aos.append(abs((m.aos - best["aos"]).total_seconds()))
            d_tca.append(abs((m.tca - best["tca"]).total_seconds()))
            d_los.append(abs((m.los - best["los"]).total_seconds()))
            # Skyfield's own elevation at its culmination instant.
            alt = (sfsat - station).at(
                ts.utc(best["tca"].year, best["tca"].month, best["tca"].day,
                       best["tca"].hour, best["tca"].minute,
                       best["tca"].second)).altaz()[0].degrees
            d_el.append(abs(m.el_max_deg - alt))

    s_aos, s_tca, s_los, s_el = (stats(d_aos), stats(d_tca), stats(d_los),
                                 stats(d_el))
    print(f"  satellites            {n_sats}")
    print(f"  passes SkyPass/Skyfield {n_sp} / {n_sf}")
    print(f"  matched pairs         {s_aos.get('n', 0)}")
    print(f"  |dAOS| s   {fmt(s_aos)}")
    print(f"  |dTCA| s   {fmt(s_tca)}")
    print(f"  |dLOS| s   {fmt(s_los)}")
    print(f"  |dElMax| deg {fmt(s_el, prec=4)}")
    return {"n_satellites": n_sats, "n_passes_skypass": n_sp,
            "n_passes_skyfield": n_sf, "n_matched": s_aos.get("n", 0),
            "d_aos_s": s_aos, "d_tca_s": s_tca, "d_los_s": s_los,
            "d_elmax_deg": s_el}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument("--max-sats", type=int, default=120)
    ap.add_argument("--station", default="chennai")
    args = ap.parse_args()

    site = GROUND_STATIONS[args.station]
    cfg = PlannerConfig()
    path = latest_archive(ARCHIVE_DIR)
    records = load_archive(path)
    t0 = utcnow().replace(hour=0, minute=0, second=0)
    t1 = t0 + dt.timedelta(days=args.days)
    print(f"TLE archive : {path} ({len(records)} objects)")
    print(f"Site        : {site.name}   mask {site.min_elev_deg} deg")
    print(f"Window      : {t0} -> {t1} UTC")

    a = part_a(records, site, t0, t1, cfg, args.max_sats)
    b = part_b(records, site, t0, t1, cfg, args.max_sats)
    save("exp1_accuracy", {
        "site": site.name, "tle_archive": path,
        "t0": t0.isoformat(), "t1": t1.isoformat(),
        "max_sats": args.max_sats, "mask_deg": site.min_elev_deg,
        "coarse_step_s": cfg.coarse_step_s, "tol_s": cfg.tol_s,
        "part_a_dense_reference": a, "part_b_skyfield": b})


if __name__ == "__main__":
    main()
