"""Experiment 4 -- what is weather-awareness actually worth?

This is the paper's central claim, tested as a controlled retrospective across
seven ground stations spanning arid to equatorial-monsoon cloud climatologies.

Design
------
For every site, all planners choose a conflict-free timetable from the *same*
candidate passes under the *same* observing budget (a small station can observe
only a few targets a night). They differ only in the value they maximise:

  A  blind-greedy   max culmination elevation, the rule an operator uses by hand
  B  blind-optimal  exact DP on the geometric+photometric score, no weather
  C  skypass-raw    exact DP on that score scaled by the RAW forecast clear sky
  D  skypass        exact DP on that score scaled by the CALIBRATED clear sky
  E  oracle         exact DP on that score scaled by the OBSERVED clear sky

Each timetable is then scored against what the sky actually did (ERA5):

    realised yield = sum over scheduled passes of  base_value * (1 - cloud_actual)
    success        = scheduled passes whose observed cloud cover was <= threshold

E is unattainable in practice; it bounds what any forecast could deliver, so the
fraction of the oracle gain recovered is the honest measure of the contribution.

Two design points matter and are reported as findings in their own right:
  * The capacity budget is what creates the decision. With unlimited capacity a
    planner simply observes everything and weather-awareness cannot help.
  * The forecast must be CALIBRATED on an earlier window, and on night hours
    only. The raw forecast is over-confident, and using it directly is worse
    than ignoring weather entirely.

Caveat stated in the paper: passes are propagated from current element sets back
over the window, so absolute pass times carry back-propagation error. That error
is common-mode -- every planner sees an identical candidate set -- so it cannot
bias the comparison between them.

Usage:
    python experiments/exp4_weather_value.py [--days 60] [--lead 1] [--lead-sweep]
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt

from _common import ARCHIVE_DIR, banner, past_window, save

from skypass.config import GROUND_STATIONS, PlannerConfig, ScoreWeights
from skypass.passes import Tracker
from skypass.pipeline import propagate_all
from skypass.scheduler import (budget_schedule, capacity_schedule,
                               greedy_budget, greedy_capacity)
from skypass.scoring import MODE_OPTICAL, priority_of, score_pass
from skypass.spacetrack import CredentialsMissing, SpaceTrack
from skypass.tle import latest_archive, load_archive
from skypass.weather import (fit_calibration, fit_clear_probability,
                             night_hours_filter, previous_runs, reanalysis)

ARMS = ["blind-greedy", "blind-optimal", "skypass-raw", "skypass",
        "skypass-prob", "oracle-ev", "oracle-clear"]

# Two ways to value an observation, and they disagree.
#   EV      value degrades linearly with cloud: a superb pass under broken
#           cloud can still beat a mediocre pass under a clear sky.
#   SUCCESS the observation either works or it does not; a pass above the cloud
#           threshold is worth nothing regardless of its geometry.
# Which one a station should optimise is a modelling choice, not a fact, so both
# are reported for every planner.


def build_candidates(site, records, start, end, cfg, weights):
    """Optically viable passes with their observed cloud cover attached.

    Computed once per site and reused for every arm and every forecast lead.
    """
    t0 = dt.datetime.combine(start, dt.time(0, 0))
    t1 = dt.datetime.combine(end, dt.time(23, 59)) + dt.timedelta(minutes=1)
    truth = reanalysis(site, start, end)
    if len(truth) == 0:
        return None, 0

    tracker = Tracker(site)
    passes, sats = propagate_all(records, tracker, t0, t1, cfg)
    cands = []
    for p in passes:
        if p.clipped:
            continue
        sat = sats.get(p.norad_id)
        if sat is None:
            continue
        # Base value: geometry, photometry and mission priority. Deliberately
        # weather-free, so it is identical across every arm.
        rep = score_pass(p, sat, tracker, clouds=None, weights=weights,
                         mode=MODE_OPTICAL, weather_aware=False)
        if rep.score < cfg.score_floor:
            continue
        c_true = truth.at(p.tca)
        if c_true is None:
            continue
        cands.append({"pass": p, "base": rep.score * priority_of(p.name),
                      "cloud_true": c_true})
    return cands, len(passes)


def build_candidates_historical(site, records, start, end, cfg, weights,
                                st, chunk_days=1):
    """Candidates built from the element sets that were current at the time.

    The default path propagates today's elements backwards over the evaluation
    window, which is fine for comparing planners (the error is common-mode) but
    leaves the absolute pass times wrong. Here the window is walked in chunks
    and each chunk is propagated from the element set that was actually current
    then, which removes that error rather than arguing around it.
    """
    truth = reanalysis(site, start, end)
    if len(truth) == 0:
        return None, 0

    nids = sorted({r.norad_id for r in records})
    # One query for the whole window plus a lookback, then index it in memory.
    # Querying per day would issue hundreds of requests for data that overlaps
    # almost entirely, which is exactly what Space-Track asks clients not to do.
    lookback = start - dt.timedelta(days=30)
    try:
        hist = st.gp_history(nids, lookback, end)
    except Exception as exc:                          # noqa: BLE001
        print(f"  [warn] element-set history unavailable: {exc}")
        return None, 0

    def current_at(when):
        """Latest element set per object with epoch at or before ``when``."""
        out = []
        for recs in hist.values():
            usable = [r for r in recs if r.epoch <= when]
            if usable:
                out.append(usable[-1])
        return out

    tracker = Tracker(site)
    cands, n_geo = [], 0
    day = start
    while day <= end:
        chunk_end = min(day + dt.timedelta(days=chunk_days), end + dt.timedelta(days=1))
        t0 = dt.datetime.combine(day, dt.time(0, 0))
        t1 = dt.datetime.combine(chunk_end, dt.time(0, 0))
        chunk_records = current_at(t0)
        if not chunk_records:
            day = chunk_end
            continue
        passes, sats = propagate_all(chunk_records, tracker, t0, t1, cfg)
        n_geo += len(passes)
        for pth in passes:
            if pth.clipped:
                continue
            sat = sats.get(pth.norad_id)
            if sat is None:
                continue
            rep = score_pass(pth, sat, tracker, clouds=None, weights=weights,
                             mode=MODE_OPTICAL, weather_aware=False)
            if rep.score < cfg.score_floor:
                continue
            c_true = truth.at(pth.tca)
            if c_true is None:
                continue
            cands.append({"pass": pth,
                          "base": rep.score * priority_of(pth.name),
                          "cloud_true": c_true})
        day = chunk_end
    cands.sort(key=lambda c: c["pass"].aos)
    return cands, n_geo


def run_arms(site, cands, calib, capacity, clear_threshold, per_night=True,
             total_budget=None, clearprob=None):
    """Schedule under each policy and score every timetable against ERA5.

    ``total_budget=None`` gives the station a fixed nightly quota, so it goes
    out every night regardless of the sky. Supplying a budget adds the second,
    realistic constraint: the same nightly cap, but a limited number of
    observations for the whole window, so the planner may skip a cloudy night.
    That freedom to skip is the decision a forecast actually informs.
    """
    def build(select_value):
        items, by_id = [], {}
        for c in cands:
            q = copy.copy(c["pass"])
            q.score = select_value(c)
            q.priority = 1.0                  # value already folded in
            items.append(q)
            by_id[id(q)] = c
        return items, by_id

    def solve(items):
        if total_budget is None:
            return capacity_schedule(items, site.setup_gap_min,
                                     capacity=capacity, per_night=per_night,
                                     lon_deg=site.lon_deg)
        return budget_schedule(items, site.setup_gap_min, capacity,
                               total_budget, lon_deg=site.lon_deg)

    def solve_greedy(items):
        if total_budget is None:
            return greedy_capacity(items, site.setup_gap_min, capacity,
                                   key=lambda p: p.el_max_deg,
                                   label="greedy-max-elevation",
                                   per_night=per_night, lon_deg=site.lon_deg)
        return greedy_budget(items, site.setup_gap_min, capacity, total_budget,
                             key=lambda p: p.el_max_deg,
                             label="greedy-max-elevation",
                             lon_deg=site.lon_deg)

    selectors = {
        "blind-greedy": lambda c: c["base"],
        "blind-optimal": lambda c: c["base"],
        "skypass-raw": lambda c: c["base"] * (1.0 - c["cloud_fc"]),
        "skypass": lambda c: c["base"] * (1.0 - calib.apply(c["cloud_fc"])),
        "skypass-prob": lambda c: c["base"] * (clearprob.apply(c["cloud_fc"])
                                               if clearprob else 1.0),
        "oracle-ev": lambda c: c["base"] * (1.0 - c["cloud_true"]),
        "oracle-clear": lambda c: (c["base"]
                                   if c["cloud_true"] <= clear_threshold
                                   else 0.0),
    }
    results = {}
    for arm in ARMS:
        items, by_id = build(selectors[arm])
        sch = solve_greedy(items) if arm == "blind-greedy" else solve(items)

        realised = planned = success_value = 0.0
        n_ok = 0
        clouds = []
        for q in sch.selected:
            c = by_id[id(q)]
            realised += c["base"] * (1.0 - c["cloud_true"])
            planned += c["base"]
            clouds.append(c["cloud_true"])
            if c["cloud_true"] <= clear_threshold:
                n_ok += 1
                success_value += c["base"]
        results[arm] = {
            "n_scheduled": len(sch.selected),
            "realised_yield": realised,          # expected-value metric
            "success_value": success_value,      # threshold metric
            "planned_yield": planned,
            "n_successful": n_ok,
            "success_rate": n_ok / max(len(sch.selected), 1),
            "mean_observed_cloud": (sum(clouds) / len(clouds)) if clouds else None,
            "runtime_s": sch.runtime_s,
        }
    return results


def _gain(results, arm, metric, baseline="blind-optimal"):
    b = results[baseline][metric]
    return 100.0 * (results[arm][metric] - b) / b if b else None


def _pct(v):
    """Format a percentage that may be undefined.

    At a site so overcast that no scheduled pass ever clears the threshold, the
    threshold-model baseline is exactly zero and the relative gain is undefined
    rather than infinite. Say so instead of crashing or printing a fake number.
    """
    return "  n/a" if v is None else f"{v:+.1f}%"


def _pctf(v):
    return "n/a" if v is None else f"{100 * v:.0f}%"


def relative(results):
    """Gains under both value models, each against the weather-blind optimum."""
    out = {}
    for tag, metric, oracle in (("ev", "realised_yield", "oracle-ev"),
                                ("clear", "success_value", "oracle-clear")):
        b = results["blind-optimal"][metric]
        o = results[oracle][metric]
        best_arm = "skypass" if tag == "ev" else "skypass-prob"
        sv = results[best_arm][metric]
        out[f"gain_{tag}_pct"] = _gain(results, best_arm, metric)
        out[f"raw_gain_{tag}_pct"] = _gain(results, "skypass-raw", metric)
        out[f"greedy_gain_{tag}_pct"] = _gain(results, "blind-greedy", metric)
        out[f"oracle_gain_{tag}_pct"] = _gain(results, oracle, metric)
        out[f"recovered_{tag}"] = ((sv - b) / (o - b)
                                   if abs(o - b) > 1e-12 else None)
    # Backwards-compatible aliases used by the figure/table generators.
    out["gain_vs_blind_pct"] = out["gain_ev_pct"]
    out["raw_gain_vs_blind_pct"] = out["raw_gain_ev_pct"]
    out["oracle_gain_pct"] = out["oracle_gain_ev_pct"]
    out["oracle_fraction_recovered"] = out["recovered_ev"]
    return out


def evaluate_site(site, records, start, end, cfg, weights, lead,
                  clear_threshold, capacity, train_days, verbose=True,
                  cache=None, per_night=True, total_budget=None,
                  spacetrack=None):
    cache = cache if cache is not None else {}
    if "cands" not in cache:
        if spacetrack is not None:
            cache["cands"], cache["n_geo"] = build_candidates_historical(
                site, records, start, end, cfg, weights, spacetrack)
        else:
            cache["cands"], cache["n_geo"] = build_candidates(
                site, records, start, end, cfg, weights)
    cands, n_geo = cache["cands"], cache["n_geo"]
    if not cands:
        return None

    if lead not in cache.setdefault("fc", {}):
        cache["fc"][lead] = previous_runs(site, start, end,
                                          lead_days=(lead,))[lead]
    fc_series = cache["fc"][lead]
    for c in cands:
        c["cloud_fc"] = fc_series.at(c["pass"].tca)
    usable = [c for c in cands if c["cloud_fc"] is not None]
    if not usable:
        return None

    # Calibration window ENDS BEFORE the evaluation window, and is restricted to
    # local night hours -- the only regime the planner applies it in.
    tr_end = start - dt.timedelta(days=1)
    tr_start = tr_end - dt.timedelta(days=train_days - 1)
    if lead not in cache.setdefault("cal", {}):
        tr_fc = previous_runs(site, tr_start, tr_end, lead_days=(lead,))[lead]
        tr_tr = reanalysis(site, tr_start, tr_end)
        hf = night_hours_filter(site.lon_deg)
        cache["cal"][lead] = fit_calibration(tr_fc, tr_tr, hour_filter=hf)
        cache.setdefault("prob", {})[lead] = fit_clear_probability(
            tr_fc, tr_tr, threshold=clear_threshold, hour_filter=hf)
    calib = cache["cal"][lead]
    clearprob = cache["prob"][lead]

    results = run_arms(site, usable, calib, capacity, clear_threshold,
                       per_night=per_night, total_budget=total_budget,
                       clearprob=clearprob)
    out = {"site": site.name, "lat": site.lat_deg, "lon": site.lon_deg,
           "budget_mode": ("nightly-quota" if total_budget is None
                           else "cap%d-budget%d" % (capacity, total_budget)),
           "total_budget": total_budget,
           "n_candidates": len(usable), "n_geometric_passes": n_geo,
           "capacity_per_night": capacity, "forecast_lead_days": lead,
           "mean_cloud_over_candidates":
               sum(c["cloud_true"] for c in usable) / len(usable),
           "calibration": calib.as_dict(),
           "clear_probability": clearprob.as_dict(),
           "calibration_window": [tr_start.isoformat(), tr_end.isoformat()],
           "arms": results}
    out.update(relative(results))

    if verbose:
        print(f"\n  {site.name}   candidates {len(usable)}   "
              f"mean observed cloud "
              f"{100 * out['mean_cloud_over_candidates']:.0f}%")
        print(f"    calibration (night, {train_days} d before): "
              f"E[cloud|f] = {calib.intercept:.3f} + {calib.slope:.3f} f   "
              f"r={calib.correlation:+.3f}  n={calib.n}")
        print(f"    {'arm':<15}{'sched':>6}{'EV':>9}{'succVal':>9}"
              f"{'nOK':>6}{'rate':>7}{'meanCld':>9}")
        for a in ARMS:
            r = results[a]
            print(f"    {a:<15}{r['n_scheduled']:6d}{r['realised_yield']:9.2f}"
                  f"{r['success_value']:9.2f}{r['n_successful']:6d}"
                  f"{100 * r['success_rate']:6.1f}%"
                  f"{100 * (r['mean_observed_cloud'] or 0):8.0f}%")
        print(f"    EV metric   : skypass {_pct(out['gain_ev_pct'])}  "
              f"oracle {_pct(out['oracle_gain_ev_pct'])}  recovered "
              f"{_pctf(out['recovered_ev'])}")
        print(f"    Clear metric: skypass-prob {_pct(out['gain_clear_pct'])}  "
              f"oracle {_pct(out['oracle_gain_clear_pct'])}  recovered "
              f"{_pctf(out['recovered_clear'])}")
    return out


def pool(sites):
    pooled = {}
    for a in ARMS:
        pooled[a] = {
            "realised_yield": sum(s["arms"][a]["realised_yield"] for s in sites),
            "success_value": sum(s["arms"][a]["success_value"] for s in sites),
            "planned_yield": sum(s["arms"][a]["planned_yield"] for s in sites),
            "n_scheduled": sum(s["arms"][a]["n_scheduled"] for s in sites),
            "n_successful": sum(s["arms"][a]["n_successful"] for s in sites),
        }
        pooled[a]["success_rate"] = (pooled[a]["n_successful"]
                                     / max(pooled[a]["n_scheduled"], 1))
    return pooled


def pooled_gains(pl):
    """Gains for a pooled result under both value models."""
    out = {}
    for tag, metric, oracle, arm in (
            ("ev", "realised_yield", "oracle-ev", "skypass"),
            ("clear", "success_value", "oracle-clear", "skypass-prob")):
        b = pl["blind-optimal"][metric]
        o = pl[oracle][metric]
        v = pl[arm][metric]
        r = pl["skypass-raw"][metric]
        g = pl["blind-greedy"][metric]
        out[f"gain_{tag}_pct"] = 100.0 * (v - b) / b if b else None
        out[f"raw_gain_{tag}_pct"] = 100.0 * (r - b) / b if b else None
        out[f"greedy_gain_{tag}_pct"] = 100.0 * (g - b) / b if b else None
        out[f"oracle_gain_{tag}_pct"] = 100.0 * (o - b) / b if b else None
        out[f"recovered_{tag}"] = ((v - b) / (o - b)
                                   if abs(o - b) > 1e-12 else None)
    out["success_rate_blind"] = pl["blind-optimal"]["success_rate"]
    out["success_rate_skypass"] = pl["skypass"]["success_rate"]
    out["success_rate_skypass_prob"] = pl["skypass-prob"]["success_rate"]
    out["success_rate_oracle"] = pl["oracle-clear"]["success_rate"]
    out["n_scheduled"] = pl["skypass"]["n_scheduled"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--lead", type=int, default=1)
    ap.add_argument("--clear-threshold", type=float, default=0.30)
    ap.add_argument("--capacity", type=int, default=3)
    ap.add_argument("--train-days", type=int, default=90)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--stations", default="all")
    ap.add_argument("--lead-sweep", action="store_true")
    ap.add_argument("--capacity-sweep", action="store_true")
    ap.add_argument("--tag", default="",
                    help="suffix for the results file, for A/B runs")
    ap.add_argument("--historical-tle", action="store_true",
                    help="propagate from the element sets current at the time "
                         "(needs Space-Track credentials)")
    args = ap.parse_args()

    cfg = PlannerConfig()
    weights = ScoreWeights()
    records = load_archive(latest_archive(ARCHIVE_DIR))[:args.limit]
    start, end = past_window(args.days)
    start_d, end_d = start, end
    keys = (list(GROUND_STATIONS) if args.stations == "all"
            else [s.strip() for s in args.stations.split(",")])

    banner(f"4  Value of weather-awareness  ({args.days} d, lead {args.lead} d, "
           f"{len(records)} objects, {args.capacity} obs/night)")
    print(f"  evaluation window {start} .. {end}")

    st = None
    if args.historical_tle:
        try:
            st = SpaceTrack()
            print("  using epoch-correct historical element sets")
        except CredentialsMissing as exc:
            print(f"  [warn] --historical-tle unavailable: {exc}")
            print("  falling back to back-propagated current elements")

    caches, sites = {}, {}
    for k in keys:
        caches[k] = {}
        try:
            r = evaluate_site(GROUND_STATIONS[k], records, start, end, cfg,
                              weights, args.lead, args.clear_threshold,
                              args.capacity, args.train_days,
                              cache=caches[k], spacetrack=st)
        except Exception as exc:                      # noqa: BLE001
            print(f"  [warn] {k}: {type(exc).__name__}: {exc}")
            continue
        if r:
            sites[k] = r

    banner("4  Pooled across sites")
    pooled = pool(list(sites.values()))
    summary = pooled_gains(pooled)
    bev = pooled["blind-optimal"]["realised_yield"]
    bcl = pooled["blind-optimal"]["success_value"]
    print(f"  {'arm':<15}{'sched':>7}{'EV':>10}{'vs blind':>10}"
          f"{'succVal':>10}{'vs blind':>10}{'nOK':>6}{'rate':>8}")
    for a in ARMS:
        r = pooled[a]
        rev = 100.0 * (r["realised_yield"] - bev) / bev if bev else 0.0
        rcl = 100.0 * (r["success_value"] - bcl) / bcl if bcl else 0.0
        print(f"  {a:<15}{r['n_scheduled']:7d}{r['realised_yield']:10.2f}"
              f"{rev:+9.1f}%{r['success_value']:10.2f}{rcl:+9.1f}%"
              f"{r['n_successful']:6d}{100 * r['success_rate']:7.1f}%")
    print()
    print(f"  Expected-value model : SkyPass {_pct(summary['gain_ev_pct'])}, "
          f"oracle {_pct(summary['oracle_gain_ev_pct'])}, "
          f"recovered {_pctf(summary['recovered_ev'])}")
    print(f"  Threshold model      : SkyPass {_pct(summary['gain_clear_pct'])}, "
          f"oracle {_pct(summary['oracle_gain_clear_pct'])}, "
          f"recovered {_pctf(summary['recovered_clear'])}")
    print(f"  clear-sky success rate: blind "
          f"{100 * summary['success_rate_blind']:.1f}%  ->  SkyPass-prob "
          f"{100 * summary['success_rate_skypass_prob']:.1f}%  (oracle "
          f"{100 * summary['success_rate_oracle']:.1f}%)")

    # --- lead sweep -------------------------------------------------------
    sweep = {}
    if args.lead_sweep:
        banner("4B  Gain versus forecast lead time (pooled over all sites)")
        print(f"  {'lead':>5}{'EV sky':>10}{'EV raw':>9}{'EV orc':>9}"
              f"{'CL sky':>10}{'CL orc':>9}{'clear':>9}")
        for lead in range(1, 8):
            per = []
            for k in list(sites):
                r = evaluate_site(GROUND_STATIONS[k], records, start, end, cfg,
                                  weights, lead, args.clear_threshold,
                                  args.capacity, args.train_days,
                                  verbose=False, cache=caches[k],
                                  spacetrack=st)
                if r:
                    per.append(r)
            if not per:
                continue
            pl = pool(per)
            sweep[str(lead)] = pooled_gains(pl)
            w = sweep[str(lead)]
            print(f"  {lead:>5}{_pct(w['gain_ev_pct']):>10}"
                  f"{_pct(w['raw_gain_ev_pct']):>9}"
                  f"{_pct(w['oracle_gain_ev_pct']):>9}"
                  f"{_pct(w['gain_clear_pct']):>10}"
                  f"{_pct(w['oracle_gain_clear_pct']):>9}"
                  f"{100 * w['success_rate_skypass_prob']:8.1f}%")

    # --- capacity sweep ---------------------------------------------------
    cap_sweep = {}
    if args.capacity_sweep:
        banner("4C  Gain versus nightly observing capacity")
        print(f"  {'cap':>5}{'EV sky':>10}{'EV orc':>9}{'CL sky':>10}"
              f"{'CL orc':>9}{'sched':>8}")
        for cap in (1, 2, 3, 5, 8, 12, 20):
            per = []
            for k in list(sites):
                r = evaluate_site(GROUND_STATIONS[k], records, start, end, cfg,
                                  weights, args.lead, args.clear_threshold,
                                  cap, args.train_days, verbose=False,
                                  cache=caches[k], spacetrack=st)
                if r:
                    per.append(r)
            if not per:
                continue
            pl = pool(per)
            cap_sweep[str(cap)] = pooled_gains(pl)
            cap_sweep[str(cap)]["capacity"] = cap
            w = cap_sweep[str(cap)]
            print(f"  {cap:>5}{_pct(w['gain_ev_pct']):>10}"
                  f"{_pct(w['oracle_gain_ev_pct']):>9}"
                  f"{_pct(w['gain_clear_pct']):>10}"
                  f"{_pct(w['oracle_gain_clear_pct']):>9}"
                  f"{w['n_scheduled']:8d}")

    # --- budget mode: nightly quota vs nightly cap + window budget ---------
    budget_modes = {}
    n_nights = max(1, (end_d - start_d).days + 1)
    banner("4D  Nightly quota versus a nightly cap plus a window budget")
    print("  %-22s%8s%10s%9s%10s%9s%8s"
          % ("mode", "budget", "EV sky", "EV orc", "CL sky", "CL orc", "clear"))
    modes = [("nightly-quota", None)]
    for frac in (0.75, 0.5, 0.25):
        modes.append(("budget-%dpct" % int(100 * frac),
                      max(1, int(round(frac * args.capacity * n_nights)))))
    for mode, budget in modes:
        per = []
        for k in list(sites):
            r = evaluate_site(GROUND_STATIONS[k], records, start_d, end_d, cfg,
                              weights, args.lead, args.clear_threshold,
                              args.capacity, args.train_days, verbose=False,
                              cache=caches[k], total_budget=budget,
                              spacetrack=st)
            if r:
                per.append(r)
        if not per:
            continue
        pl = pool(per)
        budget_modes[mode] = pooled_gains(pl)
        budget_modes[mode]["capacity_per_night"] = args.capacity
        budget_modes[mode]["total_budget"] = budget
        w = budget_modes[mode]
        print("  %-22s%8s%10s%9s%10s%9s%7.1f%%"
              % (mode, str(budget), _pct(w["gain_ev_pct"]),
                 _pct(w["oracle_gain_ev_pct"]), _pct(w["gain_clear_pct"]),
                 _pct(w["oracle_gain_clear_pct"]),
                 100 * w["success_rate_skypass_prob"]))

    save("exp4_weather_value" + args.tag, {
        "window": {"start": start.isoformat(), "end": end.isoformat(),
                   "days": args.days},
        "forecast_lead_days": args.lead, "capacity_per_night": args.capacity,
        "clear_threshold": args.clear_threshold, "train_days": args.train_days,
        "n_objects": len(records),
        "historical_tle": st is not None,
        "sites": sites, "pooled": pooled, "summary": summary,
        "lead_sweep": sweep, "capacity_sweep": cap_sweep,
        "budget_modes": budget_modes, "n_nights": n_nights})


if __name__ == "__main__":
    main()
