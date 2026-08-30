"""Experiment 5 -- conflict resolution: exactness and cost.

The motivating claim is that a small ground station does not need a heavyweight
solver. Overlapping-pass selection is weighted interval scheduling, which admits
an exact O(n log n) dynamic program. This experiment establishes three things:

A. Optimality. On thousands of randomised instances small enough to enumerate,
   the DP matches exhaustive search exactly, while every greedy heuristic falls
   short by a measurable margin.
B. Cost against a metaheuristic. A genetic algorithm of the kind used in the
   operator-side tasking literature is run on real instances; it needs orders of
   magnitude more time and still does not reach the optimum.
C. Scaling. DP runtime is measured up to catalogue-scale instance sizes.

Usage:
    python experiments/exp5_scheduling.py [--trials 2000]
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import statistics
import time

from _common import ARCHIVE_DIR, banner, save

from skypass.config import GROUND_STATIONS, PlannerConfig, ScoreWeights
from skypass.passes import Pass, Tracker
from skypass.pipeline import propagate_all
from skypass.scheduler import (brute_force_optimal, genetic_schedule,
                               greedy_earliest_finish, greedy_highest_value,
                               greedy_longest_duration, greedy_max_elevation,
                               optimal_schedule)
from skypass.scoring import MODE_OPTICAL, apply_scores
from skypass.tle import latest_archive, load_archive
from skypass.timeutil import utcnow

T0 = dt.datetime(2026, 1, 1)
HEURISTICS = {
    "greedy-max-elevation": greedy_max_elevation,
    "greedy-highest-value": greedy_highest_value,
    "greedy-longest-duration": greedy_longest_duration,
    "greedy-earliest-finish": greedy_earliest_finish,
}


def random_instance(rng, n, horizon_min=720.0):
    out = []
    for i in range(n):
        aos = T0 + dt.timedelta(minutes=rng.uniform(0, horizon_min))
        los = aos + dt.timedelta(minutes=rng.uniform(2, 14))
        p = Pass(name=f"OBJ{i}", norad_id=i, aos=aos,
                 tca=aos + (los - aos) / 2, los=los,
                 el_max_deg=rng.uniform(10, 90))
        p.score = round(rng.uniform(0.02, 1.0), 4)
        p.priority = rng.choice([1.0, 1.0, 1.5, 2.0])
        out.append(p)
    return out


def part_a(trials, gap):
    banner("5A  Exactness against exhaustive search")
    rng = random.Random(20260829)
    ratios = {k: [] for k in HEURISTICS}
    dp_exact = 0
    heur_exact = {k: 0 for k in HEURISTICS}
    n_used = 0
    for _ in range(trials):
        n = rng.randint(2, 14)
        inst = random_instance(rng, n)
        dp = optimal_schedule(inst, gap)
        bf = brute_force_optimal(inst, gap)
        assert dp.is_feasible(gap)
        n_used += 1
        if abs(dp.objective - bf.objective) < 1e-9:
            dp_exact += 1
        for k, fn in HEURISTICS.items():
            s = fn(inst, gap)
            assert s.is_feasible(gap), k
            r = s.objective / bf.objective if bf.objective > 0 else 1.0
            ratios[k].append(r)
            if abs(s.objective - bf.objective) < 1e-9:
                heur_exact[k] += 1
    print(f"  instances                {n_used}   setup gap {gap} min")
    print(f"  DP == exhaustive optimum {dp_exact}/{n_used} "
          f"({100.0 * dp_exact / n_used:.2f}%)")
    print(f"\n  {'heuristic':<26}{'mean ratio':>11}{'min':>8}"
          f"{'optimal in':>12}")
    out = {"n_instances": n_used, "gap_min": gap,
           "dp_optimal_fraction": dp_exact / n_used, "heuristics": {}}
    for k in HEURISTICS:
        m = statistics.fmean(ratios[k])
        out["heuristics"][k] = {
            "mean_ratio_to_optimum": m,
            "min_ratio": min(ratios[k]),
            "optimal_fraction": heur_exact[k] / n_used,
            "mean_shortfall_pct": 100.0 * (1.0 - m),
        }
        print(f"  {k:<26}{m:11.4f}{min(ratios[k]):8.3f}"
              f"{100.0 * heur_exact[k] / n_used:11.1f}%")
    return out


def real_instances(cfg, weights, days, limit):
    """Candidate sets from real passes at each preset station."""
    records = load_archive(latest_archive(ARCHIVE_DIR))[:limit]
    t0 = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = t0 + dt.timedelta(days=days)
    out = {}
    for key, site in GROUND_STATIONS.items():
        tracker = Tracker(site)
        passes, sats = propagate_all(records, tracker, t0, t1, cfg)
        apply_scores(passes, sats, tracker, clouds=None, weights=weights,
                     mode=MODE_OPTICAL, weather_aware=False)
        cand = [p for p in passes if p.score >= cfg.score_floor and not p.clipped]
        out[key] = (site, cand)
    return out


def part_b(cfg, weights, days, limit, ga_pop=60, ga_gen=120):
    banner("5B  Exact DP versus a genetic algorithm on real instances")
    inst = real_instances(cfg, weights, days, limit)
    rows = []
    print(f"  {'site':<20}{'n':>6}{'DP obj':>10}{'DP ms':>9}"
          f"{'GA obj':>10}{'GA ms':>10}{'GA/DP':>8}{'speedup':>9}")
    for key, (site, cand) in inst.items():
        if len(cand) < 5:
            continue
        dp = optimal_schedule(cand, site.setup_gap_min)
        ga = genetic_schedule(cand, site.setup_gap_min, population=ga_pop,
                              generations=ga_gen, seed=1)
        ratio = ga.objective / dp.objective if dp.objective else 1.0
        speed = ga.runtime_s / max(dp.runtime_s, 1e-9)
        rows.append({"site": site.name, "n_candidates": len(cand),
                     "ga_population": ga_pop, "ga_generations": ga_gen,
                     "dp_objective": dp.objective, "dp_runtime_s": dp.runtime_s,
                     "dp_count": dp.count,
                     "ga_objective": ga.objective, "ga_runtime_s": ga.runtime_s,
                     "ga_count": ga.count,
                     "ga_ratio": ratio, "ga_slowdown": speed})
        print(f"  {site.name[:19]:<20}{len(cand):6d}{dp.objective:10.3f}"
              f"{1000 * dp.runtime_s:9.2f}{ga.objective:10.3f}"
              f"{1000 * ga.runtime_s:10.1f}{ratio:8.4f}{speed:8.0f}x")
    if rows:
        print(f"\n  GA reaches on average "
              f"{100 * statistics.fmean(r['ga_ratio'] for r in rows):.2f}% of the "
              f"optimum, taking "
              f"{statistics.fmean(r['ga_slowdown'] for r in rows):.0f}x longer.")
    return rows


def part_c(reps=5):
    banner("5C  Dynamic-program scaling")
    rng = random.Random(11)
    rows = []
    print(f"  {'n':>8}{'mean ms':>10}{'std ms':>9}{'us per pass':>13}")
    for n in (100, 500, 1000, 5000, 10000, 50000, 100000):
        ts = []
        for _ in range(reps):
            inst = random_instance(rng, n, horizon_min=max(720.0, n * 1.5))
            t = time.perf_counter()
            optimal_schedule(inst, 5.0)
            ts.append(time.perf_counter() - t)
        m = statistics.fmean(ts)
        sd = statistics.pstdev(ts)
        rows.append({"n": n, "mean_s": m, "std_s": sd,
                     "us_per_pass": 1e6 * m / n})
        print(f"  {n:8d}{1000 * m:10.2f}{1000 * sd:9.2f}{1e6 * m / n:13.2f}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=2000)
    ap.add_argument("--gap", type=float, default=5.0)
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--ga-pop", type=int, default=60,
                    help="genetic-algorithm population size")
    ap.add_argument("--ga-gen", type=int, default=120,
                    help="genetic-algorithm generations")
    args = ap.parse_args()

    a = part_a(args.trials, args.gap)
    b = part_b(PlannerConfig(), ScoreWeights(), args.days, args.limit,
               args.ga_pop, args.ga_gen)
    c = part_c()
    save("exp5_scheduling", {"part_a_exactness": a,
                             "part_b_vs_genetic": b,
                             "part_c_scaling": c})


if __name__ == "__main__":
    main()
