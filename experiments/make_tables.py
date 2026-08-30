"""Generate the paper's LaTeX tables and inline numbers from results/*.json.

Every figure quoted in the paper is emitted here, so the text cannot drift from
the experiments: the paper \\input{}s these files rather than hard-coding values.

Writes:
    paper/generated/tab_*.tex      booktabs tables
    paper/generated/numbers.tex    \\newcommand macros for inline values

Usage:
    python experiments/make_tables.py
"""
from __future__ import annotations

import json
import os

from _common import RESULTS_DIR

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "paper", "generated")

MACROS: dict = {}


def load(name):
    p = os.path.join(RESULTS_DIR, f"{name}.json")
    if not os.path.exists(p):
        print(f"  [skip] {name}.json missing")
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


WRITTEN = set()


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    WRITTEN.add(name[:-4] if name.endswith(".tex") else name)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"  -> paper/generated/{name}")


def mac(key, value):
    """Register an inline macro. Keys must be letters only (TeX restriction)."""
    MACROS[key] = value


def esc(s):
    return str(s).replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")


def num(x, p=2):
    return f"{x:.{p}f}" if x is not None else "--"


# ---------------------------------------------------------------------------
def tab_accuracy():
    d = load("exp1_accuracy")
    if not d:
        return
    a, b = d["part_a_dense_reference"], d["part_b_skyfield"]
    rows = [("$|\\Delta t_\\mathrm{AOS}|$", "d_aos_s"),
            ("$|\\Delta t_\\mathrm{TCA}|$", "d_tca_s"),
            ("$|\\Delta t_\\mathrm{LOS}|$", "d_los_s")]
    L = [r"\begin{table}[t]",
         r"\caption{Pass-timing agreement over the full catalogue ("
         + str(a["n_satellites"]) + r" objects, "
         + str(a["n_matched"]) + r" matched passes, 24\,h horizon). "
         r"Values in seconds.}",
         r"\label{tab:accuracy}", r"\centering",
         r"\begin{tabular}{lcccc}", r"\toprule",
         r"& \multicolumn{2}{c}{vs.\ 1\,s dense scan} "
         r"& \multicolumn{2}{c}{vs.\ Skyfield} \\",
         r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
         r"Quantity & mean & p95 & mean & p95 \\", r"\midrule"]
    for label, key in rows:
        L.append(f"{label} & {num(a[key]['mean'], 3)} & {num(a[key]['p95'], 3)} "
                 f"& {num(b[key]['mean'], 3)} & {num(b[key]['p95'], 3)} \\\\")
    L.append(f"$|\\Delta \\varepsilon_\\mathrm{{max}}|$ (deg) & "
             f"{num(a['d_elmax_deg']['mean'], 4)} & "
             f"{num(a['d_elmax_deg']['p95'], 4)} & "
             f"{num(b['d_elmax_deg']['mean'], 4)} & "
             f"{num(b['d_elmax_deg']['p95'], 4)} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_accuracy.tex", "\n".join(L) + "\n")

    mac("NSats", a["n_satellites"])
    mac("NPasses", a["n_passes_fast"])
    mac("NMatched", a["n_matched"])
    mac("CallReduction", num(a["call_reduction"], 1))
    mac("CallsFast", f"{a['calls_fast']:,}".replace(",", "\\,"))
    mac("CallsDense", f"{a['calls_dense']:,}".replace(",", "\\,"))
    mac("Recall", num(100.0 * a["recall"], 2))
    mac("Missed", a["missed"])
    mac("SkyfieldTca", num(b["d_tca_s"]["mean"], 3))
    mac("SkyfieldAos", num(b["d_aos_s"]["mean"], 3))
    mac("SkyfieldTcaMax", num(b["d_tca_s"]["max"], 3))
    mac("DenseAos", num(a["d_aos_s"]["mean"], 3))


def tab_elements():
    d = load("exp2_elements")
    if not d:
        return
    a = d["part_a_epoch_age"]["summary"]
    h = d["part_a_epoch_age"]["histogram"]
    b = d["part_b_provider_divergence"]
    mac("EpochMedian", num(a["median"], 2))
    mac("EpochMean", num(a["mean"], 2))
    mac("EpochPninety", num(a["p90"], 2))
    mac("EpochMax", num(a["max"], 2))
    mac("EpochUnderOne", num(100.0 * h["<1 d"] / a["n"], 1))
    mac("NCatalogue", a["n"])
    if "d_tca_s" in b:
        mac("ProviderTcaMean", num(b["d_tca_s"]["mean"], 3))
        mac("ProviderTcaPninetyfive", num(b["d_tca_s"]["p95"], 3))
        mac("ProviderTcaMax", num(b["d_tca_s"]["max"], 2))
        mac("ProviderN", b["d_tca_s"]["n"])
        mac("ProviderObjects", b["n_objects_matched"])

        L = [r"\begin{table}[t]",
             r"\caption{Pass-timing divergence between two independently "
             r"curated element sets (CelesTrak vs.\ AMSAT) for the same "
             r"objects, grouped by the separation of their epochs.}",
             r"\label{tab:elements}", r"\centering",
             r"\begin{tabular}{lrrrr}", r"\toprule",
             r"Epoch separation & $N$ & mean & median & p95 \\",
             r"& & (s) & (s) & (s) \\", r"\midrule"]
        for k, v in b.get("by_epoch_separation", {}).items():
            L.append(f"{esc(k)} & {v['n']} & {num(v['mean'], 3)} & "
                     f"{num(v['median'], 3)} & {num(v['p95'], 3)} \\\\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        write("tab_elements.tex", "\n".join(L) + "\n")


def tab_forecast():
    d = load("exp3_forecast")
    if not d:
        return
    pooled = d["pooled"]
    base = d["pooled_baselines"]
    L = [r"\begin{table}[t]",
         r"\caption{Cloud-forecast verification against ERA5 reanalysis, "
         r"pooled over all seven stations (" + str(d["window"]["days"]) +
         r"\,d, " + f"{pooled['1']['n']:,}".replace(",", "\\,") +
         r" station-hours per lead). The decision scored is "
         r"``is this hour clear enough to observe?'' at a "
         + num(100 * d["clear_threshold"], 0) + r"\% cloud threshold.}",
         r"\label{tab:forecast}", r"\centering",
         r"\setlength{\tabcolsep}{4.2pt}",
         r"\begin{tabular}{lccccc}", r"\toprule",
         r"Lead (d) & MAE & RMSE & Accuracy & POD & HSS \\", r"\midrule"]
    for k in sorted(pooled, key=lambda x: int(x)):
        if int(k) == 0:
            continue
        r = pooled[k]
        L.append(f"{k} & {num(r['mae'], 3)} & {num(r['rmse'], 3)} & "
                 f"{num(r['accuracy'], 3)} & {num(r['pod'], 3)} & "
                 f"{num(r['hss'], 3)} \\\\")
    L.append(r"\midrule")
    for label, key in (("Persistence (24\\,h)", "persistence_24h"),
                       ("Climatology", "climatology")):
        if key in base:
            r = base[key]
            L.append(f"{label} & {num(r['mae'], 3)} & {num(r['rmse'], 3)} & "
                     f"{num(r['accuracy'], 3)} & {num(r['pod'], 3)} & "
                     f"{num(r['hss'], 3)} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_forecast.tex", "\n".join(L) + "\n")

    mac("HssOne", num(pooled["1"]["hss"], 3))
    mac("HssThree", num(pooled["3"]["hss"], 3))
    mac("HssSeven", num(pooled["7"]["hss"], 3))
    mac("MaeOne", num(pooled["1"]["mae"], 3))
    mac("AccOne", num(100 * pooled["1"]["accuracy"], 1))
    mac("HssPersistence", num(base["persistence_24h"]["hss"], 3))
    mac("MaePersistence", num(base["persistence_24h"]["mae"], 3))
    mac("ForecastDays", d["window"]["days"])
    mac("ForecastStart", d["window"]["start"])
    mac("ForecastEnd", d["window"]["end"])
    mac("ClearThreshold", num(100 * d["clear_threshold"], 0))


ARM_LABELS = [
    ("blind-greedy", "Greedy, weather-blind"),
    ("blind-optimal", "Exact DP, weather-blind"),
    ("skypass-raw", "SkyPass, raw forecast"),
    ("skypass", "SkyPass, calibrated"),
    ("skypass-prob", "SkyPass, clear-probability"),
    ("oracle-ev", "Oracle (expected value)"),
    ("oracle-clear", "Oracle (threshold)"),
]


def tab_weather_value():
    d = load("exp4_weather_value")
    if not d:
        return
    sites, pooled, s = d["sites"], d["pooled"], d["summary"]
    bev = pooled["blind-optimal"]["realised_yield"]
    bcl = pooled["blind-optimal"]["success_value"]

    L = [r"\begin{table*}[t]",
         r"\caption{Realised observation yield pooled over seven stations ("
         + str(d["window"]["days"]) + r"\,d, " + str(d["n_objects"])
         + r" objects, " + str(d["capacity_per_night"])
         + r" observations per night, forecast lead "
         + str(d["forecast_lead_days"]) + r"\,d). All planners choose from an "
         r"identical candidate set; every timetable is scored against ERA5 "
         r"under both value models. This is the fixed nightly-quota regime, in "
         r"which the station must observe every night; "
         r"Table~\ref{tab:budgetmodes} relaxes that.}",
         r"\label{tab:weathervalue}", r"\centering",
         r"\begin{tabular}{lrrrrr}", r"\toprule",
         r"& & \multicolumn{2}{c}{Expected value} "
         r"& \multicolumn{2}{c}{Threshold} \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}",
         r"Planner & Sched. & yield & vs.\ blind & value & vs.\ blind \\",
         r"\midrule"]
    for key, label in ARM_LABELS:
        r = pooled[key]
        rev = 100.0 * (r["realised_yield"] - bev) / bev if bev else 0.0
        rcl = 100.0 * (r["success_value"] - bcl) / bcl if bcl else 0.0
        L.append(f"{label} & {r['n_scheduled']} & "
                 f"{num(r['realised_yield'], 1)} & {rev:+.1f}\\% & "
                 f"{num(r['success_value'], 1)} & {rcl:+.1f}\\% \\\\")
        if key == "skypass-prob":
            L.append(r"\midrule")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    write("tab_weather_value.tex", "\n".join(L) + "\n")

    # Per-site
    L = [r"\begin{table}[t]",
         r"\caption{Per-station context. $\bar c$ is the mean observed cloud "
         r"cover over candidate passes and $b$ the fitted calibration slope, "
         r"which measures how much of the forecast signal survives "
         r"verification. Gains are under the threshold value model at a "
         r"50\% window budget.}",
         r"\label{tab:persite}", r"\centering",
         r"\begin{tabular}{lrrrrr}", r"\toprule",
         r"Station & $\bar c$ (\%) & $b$ & Cand. & SkyPass & Oracle \\",
         r"\midrule"]
    for k, v in sites.items():
        L.append(f"{esc(v['site'].split(',')[0])} & "
                 f"{100 * v['mean_cloud_over_candidates']:.0f} & "
                 f"{num(v['calibration']['slope'], 2)} & "
                 f"{v['n_candidates']} & "
                 f"{v['gain_clear_pct']:+.1f}\\% & "
                 f"{v['oracle_gain_clear_pct']:+.1f}\\% \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_persite.tex", "\n".join(L) + "\n")

    mac("EvalDays", d["window"]["days"])
    mac("EvalStart", d["window"]["start"])
    mac("EvalEnd", d["window"]["end"])
    mac("Capacity", d["capacity_per_night"])
    mac("EvalObjects", d["n_objects"])
    mac("TrainDays", d["train_days"])
    mac("ClearThresholdEval", num(100 * d["clear_threshold"], 0))
    mac("QuotaGainEV", num(s["gain_ev_pct"], 1))
    mac("QuotaGainClear", num(s["gain_clear_pct"], 1))
    mac("QuotaOracleEV", num(s["oracle_gain_ev_pct"], 1))
    mac("QuotaOracleClear", num(s["oracle_gain_clear_pct"], 1))
    mac("QuotaRawEV", num(s["raw_gain_ev_pct"], 1))
    mac("GreedyGain", num(s["greedy_gain_ev_pct"], 1))
    ch = sites.get("chennai") or next(iter(sites.values()))
    mac("CloudChennai", num(100 * ch["mean_cloud_over_candidates"], 0))
    mac("SlopeChennai", num(ch["calibration"]["slope"], 2))

    # Budget modes -- the headline result.
    bm = d.get("budget_modes") or {}
    if bm:
        L = [r"\begin{table*}[t]",
             r"\caption{The decisive design choice. A fixed nightly quota "
             r"forces the station out every night, so the forecast can only "
             r"reorder passes within a night and buys nothing. Giving it the "
             r"same nightly cap but a limited budget for the window lets it "
             r"skip cloudy nights, and the forecast becomes valuable. Gains "
             r"are against the weather-blind exact planner under the same "
             r"budget.}",
             r"\label{tab:budgetmodes}", r"\centering",
             r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"& & \multicolumn{2}{c}{Expected value} "
             r"& \multicolumn{2}{c}{Threshold} & \\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}",
             r"Budget & $B$ & SkyPass & Oracle & SkyPass & Oracle "
             r"& Clear \\", r"\midrule"]
        pretty = {"nightly-quota": "Nightly quota",
                  "budget-75pct": "75\\% of nights",
                  "budget-50pct": "50\\% of nights",
                  "budget-25pct": "25\\% of nights"}
        # The tightest budget, quoted in the text to show the trend is monotone.
        tight = bm.get("budget-25pct")
        if tight:
            mac("TightGainClear", num(tight["gain_clear_pct"], 1))
            mac("TightGainEV", num(tight["gain_ev_pct"], 1))
            mac("TightClearRate",
                num(100 * tight["success_rate_skypass_prob"], 1))
            mac("TightBudget", tight["total_budget"])
        for k, v in bm.items():
            L.append(f"{pretty.get(k, esc(k))} & "
                     f"{v['total_budget'] if v['total_budget'] else '--'} & "
                     f"{v['gain_ev_pct']:+.1f}\\% & "
                     f"{v['oracle_gain_ev_pct']:+.1f}\\% & "
                     f"{v['gain_clear_pct']:+.1f}\\% & "
                     f"{v['oracle_gain_clear_pct']:+.1f}\\% & "
                     f"{100 * v['success_rate_skypass_prob']:.0f}\\% \\\\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
        write("tab_budgetmodes.tex", "\n".join(L) + "\n")

        best = None
        for k in ("budget-50pct", "budget-25pct", "budget-75pct"):
            if k in bm:
                best = bm[k]
                mac("BestBudgetMode", pretty.get(k, k))
                break
        if best:
            mac("BudgetGainEV", num(best["gain_ev_pct"], 1))
            mac("BudgetGainClear", num(best["gain_clear_pct"], 1))
            mac("BudgetOracleEV", num(best["oracle_gain_ev_pct"], 1))
            mac("BudgetOracleClear", num(best["oracle_gain_clear_pct"], 1))
            mac("BudgetRecoveredEV", num(100 * (best["recovered_ev"] or 0), 0))
            mac("BudgetRecoveredClear",
                num(100 * (best["recovered_clear"] or 0), 0))
            mac("BudgetClearRate",
                num(100 * best["success_rate_skypass_prob"], 1))
            mac("BudgetBlindClearRate",
                num(100 * best["success_rate_blind"], 1))
            mac("BudgetTotal", best["total_budget"])

    # Lead sweep
    ls = d.get("lead_sweep") or {}
    if ls:
        L = [r"\begin{table}[t]",
             r"\caption{Weather-aware gain against forecast lead time, in "
             r"the nightly-quota regime. The result is flat and near zero at "
             r"every lead: under a quota the forecast has nothing to act on, "
             r"so no amount of forecast skill converts into yield.}",
             r"\label{tab:leadsweep}", r"\centering",
             r"\begin{tabular}{lrrrr}", r"\toprule",
             r"Lead (d) & SkyPass (EV) & Oracle (EV) & SkyPass & Oracle \\",
             r"\midrule"]
        for k in sorted(ls, key=lambda x: int(x)):
            v = ls[k]
            L.append(f"{k} & {v['gain_ev_pct']:+.1f}\\% & "
                     f"{v['oracle_gain_ev_pct']:+.1f}\\% & "
                     f"{v['gain_clear_pct']:+.1f}\\% & "
                     f"{v['oracle_gain_clear_pct']:+.1f}\\% \\\\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        write("tab_leadsweep.tex", "\n".join(L) + "\n")

    # Capacity sweep
    cs = d.get("capacity_sweep") or {}
    if cs:
        L = [r"\begin{table}[t]",
             r"\caption{Gain against the nightly observing cap. The benefit "
             r"is largest for the smallest stations: one that can observe "
             r"everything never has to choose.}",
             r"\label{tab:capsweep}", r"\centering",
             r"\setlength{\tabcolsep}{4pt}",
             r"\begin{tabular}{lrrrr}", r"\toprule",
             r"Obs./night & SkyPass (EV) & Oracle (EV) & SkyPass & Oracle \\",
             r"\midrule"]
        for k in sorted(cs, key=lambda x: int(x)):
            v = cs[k]
            L.append(f"{k} & {v['gain_ev_pct']:+.1f}\\% & "
                     f"{v['oracle_gain_ev_pct']:+.1f}\\% & "
                     f"{v['gain_clear_pct']:+.1f}\\% & "
                     f"{v['oracle_gain_clear_pct']:+.1f}\\% \\\\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        write("tab_capsweep.tex", "\n".join(L) + "\n")


def tab_scheduling():
    d = load("exp5_scheduling")
    if not d:
        return
    a = d["part_a_exactness"]
    L = [r"\begin{table}[t]",
         r"\caption{Scheduling quality on " + f"{a['n_instances']:,}".replace(",", "\\,") +
         r" randomised instances small enough to enumerate exhaustively "
         r"($n \le 14$, setup gap " + num(a["gap_min"], 0) + r"\,min).}",
         r"\label{tab:scheduling}", r"\centering",
         r"\setlength{\tabcolsep}{4pt}",
         r"\begin{tabular}{lrr}", r"\toprule",
         r"Algorithm & Mean \% of opt. & Optimal in \% \\", r"\midrule",
         r"Exact DP (SkyPass) & 100.00 & "
         + num(100 * a["dp_optimal_fraction"], 2) + r" \\", r"\midrule"]
    for k, v in a["heuristics"].items():
        L.append(f"{esc(k.replace('greedy-', 'Greedy, '))} & "
                 f"{100 * v['mean_ratio_to_optimum']:.2f} & "
                 f"{100 * v['optimal_fraction']:.2f} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_scheduling.tex", "\n".join(L) + "\n")

    mac("SchedTrials", f"{a['n_instances']:,}".replace(",", "\\,"))
    mac("DPOptimalPct", num(100 * a["dp_optimal_fraction"], 2))
    worst = min(a["heuristics"].items(),
                key=lambda kv: kv[1]["mean_ratio_to_optimum"])
    best = max(a["heuristics"].items(),
               key=lambda kv: kv[1]["mean_ratio_to_optimum"])
    mac("GreedyBestPct", num(100 * best[1]["mean_ratio_to_optimum"], 2))
    mac("GreedyWorstPct", num(100 * worst[1]["mean_ratio_to_optimum"], 2))
    ge = a["heuristics"]["greedy-max-elevation"]
    mac("GreedyElevPct", num(100 * ge["mean_ratio_to_optimum"], 2))
    mac("GreedyElevMin", num(100 * ge["min_ratio"], 1))
    mac("GreedyElevOptPct", num(100 * ge["optimal_fraction"], 1))
    gv = a["heuristics"]["greedy-highest-value"]
    mac("GreedyValuePct", num(100 * gv["mean_ratio_to_optimum"], 2))
    mac("GreedyValueMin", num(100 * gv["min_ratio"], 1))

    b = d.get("part_b_vs_genetic") or []
    if b:
        ratios = [r["ga_ratio"] for r in b]
        slow = [r["ga_slowdown"] for r in b]
        mac("GAPct", num(100 * sum(ratios) / len(ratios), 2))
        mac("GASlowdown", f"{sum(slow) / len(slow):,.0f}".replace(",", "\\,"))
        L = [r"\begin{table}[t]",
             r"\caption{Exact dynamic program versus an order-based genetic "
             r"algorithm on real candidate sets (7-day horizon).}",
             r"\label{tab:genetic}", r"\centering",
             r"\begin{tabular}{lrrrr}", r"\toprule",
             r"Station & $n$ & DP (ms) & GA (ms) & GA/DP obj. \\", r"\midrule"]
        for r in b:
            L.append(f"{esc(r['site'].split(',')[0])} & {r['n_candidates']} & "
                     f"{1000 * r['dp_runtime_s']:.2f} & "
                     f"{1000 * r['ga_runtime_s']:.0f} & "
                     f"{r['ga_ratio']:.4f} \\\\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        write("tab_genetic.tex", "\n".join(L) + "\n")

    c = d.get("part_c_scaling") or []
    if c:
        big = max(c, key=lambda r: r["n"])
        mac("DPBigN", f"{big['n']:,}".replace(",", "\\,"))
        mac("DPBigMs", num(1000 * big["mean_s"], 1))


def tab_pipeline():
    d = load("exp6_pipeline")
    if not d:
        return
    rows = d["part_a_optical"]
    L = [r"\begin{table*}[t]",
         r"\caption{End-to-end planning run at every station: "
         + str(d["n_objects"]) + r" objects, "
         + num(d["horizon_days"], 0) + r"-day horizon, optical mode with live "
         r"forecast. Each column is the number of passes surviving that "
         r"constraint. The cloud column is a diagnostic count at a hard "
         r"50\% threshold; the score itself treats cloud continuously, so a "
         r"pass above that threshold can still be scheduled if nothing "
         r"better competes for the slot.}",
         r"\label{tab:pipeline}", r"\centering",
         r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
         r"Station & Geometric & Sunlit & Dark sky & Bright & Cloud $<$50\% "
         r"& Candidates & Scheduled & Runtime (s) \\", r"\midrule"]
    for k, v in rows.items():
        f = v["funnel"]
        L.append(f"{esc(v['site'].split(',')[0])} & {f['geometric']} & "
                 f"{f['sunlit']} & {f['dark_sky']} & {f['bright_enough']} & "
                 f"{f['cloud_clear']} & {f['above_floor']} & {f['scheduled']} & "
                 f"{v['runtime']['total']:.1f} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    write("tab_pipeline.tex", "\n".join(L) + "\n")

    key = "chennai" if "chennai" in rows else list(rows)[0]
    v = rows[key]
    f = v["funnel"]
    mac("DemoGeometric", f["geometric"])
    mac("DemoSunlit", f["sunlit"])
    mac("DemoDark", f["dark_sky"])
    mac("DemoBright", f["bright_enough"])
    mac("DemoClear", f["cloud_clear"])
    mac("DemoScheduled", f["scheduled"])
    mac("DemoRuntime", num(v["runtime"]["total"], 1))
    mac("DemoHorizon", num(d["horizon_days"], 0))
    mac("DemoObjects", d["n_objects"])

    sens = d.get("part_b_weight_sensitivity") or []
    if sens:
        mid = [r for r in sens if 0.3 <= r["w_elev"] <= 0.7]
        if mid:
            mac("JaccardMid", num(min(r["jaccard_vs_default"] for r in mid), 2))
        mac("JaccardExtreme", num(min(r["jaccard_vs_default"] for r in sens), 2))

    sc = d.get("part_c_scaling") or []
    if sc:
        big = max(sc, key=lambda r: (r["n_objects"], r["days"]))
        mac("ScaleObjects", big["n_objects"])
        mac("ScaleDays", big["days"])
        mac("ScaleSeconds", num(big["total_s"], 1))
        mac("ScalePasses", big["n_passes"])
        mac("ScaleSchedMs", num(1000 * big["schedule_s"], 1))


def tab_structure():
    """Exp 7: the mechanism behind the weather result."""
    d = load("exp7_structure")
    if not d:
        return
    sites, ag = d["sites"], d["pooled"]
    L = [r"\begin{table}[t]",
         r"\caption{Why the forecast can only help a station that may skip "
         r"nights. Cloud varies far more \emph{between} observing nights than "
         r"\emph{within} one, so a nightly quota leaves little for a forecast "
         r"to discriminate on; meanwhile pass quality ($v_{90}/\bar v$) varies "
         r"more than the sky does, so chasing clear sky costs base value. "
         r"$\Delta \bar c$ is the reduction in observed cloud obtained by "
         r"taking the clearest-forecast decile.}",
         r"\label{tab:structure}", r"\centering",
         r"\setlength{\tabcolsep}{4pt}",
         r"\begin{tabular}{lrrrrr}", r"\toprule",
         r"Station & $\sigma_{\mathrm{btw}}$ & $\sigma_{\mathrm{wth}}$ "
         r"& ratio & $v_{90}/\bar v$ & $\Delta \bar c$ \\", r"\midrule"]
    for k, v in sites.items():
        L.append(f"{esc(v['site'].split(',')[0])} & "
                 f"{num(v['cloud_between_night_sd'], 3)} & "
                 f"{num(v['cloud_within_night_sd'], 3)} & "
                 f"{num(v['between_within_ratio'], 2)} & "
                 f"{num(v['base_p90_over_mean'], 2)} & "
                 f"{num(v['cloud_reduction_by_forecast'], 3)} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_structure.tex", "\n".join(L) + "\n")

    mac("BtwWthRatio", num(ag["between_within_ratio"], 1))
    mac("BaseSkew", num(ag["base_p90_over_mean"], 1))
    mac("PassCorr", num(ag["forecast_corr_at_passes"], 2))
    mac("CloudReduction", num(ag["cloud_reduction_by_forecast"], 3))
    mac("StructureDays", d["window"]["days"])


def tab_tleage():
    """Exp 8: prediction degradation against element-set age (Space-Track)."""
    d = load("exp8_tle_age")
    if not d or d.get("skipped"):
        return
    by = d.get("by_age") or {}
    if not by:
        return
    L = [r"\begin{table}[t]",
         r"\caption{Degradation of predicted culmination time with element-set "
         r"age, measured against a fresh reference orbit for the same object "
         r"(" + str(d["n_objects"]) + r" LEO objects, "
         + f"{d['n_comparisons']:,}".replace(",", "\\,") +
         r" aged comparisons, historical elements from Space-Track). This is "
         r"the error the elements contribute, on top of the "
         r"sub-second numerical agreement of Table~\ref{tab:accuracy}.}",
         r"\label{tab:tleage}", r"\centering",
         r"\setlength{\tabcolsep}{4pt}",
         r"\begin{tabular}{lrrrr}", r"\toprule",
         r"Element-set age & $N$ & mean & median & p95 \\",
         r"& & (s) & (s) & (s) \\", r"\midrule"]
    for k, v in by.items():
        s = v["d_tca_s"]
        L.append(f"{esc(k)} & {s['n']} & {num(s['mean'], 2)} & "
                 f"{num(s['median'], 2)} & {num(s['p95'], 2)} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_tleage.tex", "\n".join(L) + "\n")

    mac("AgeObjects", d["n_objects"])
    mac("AgeComparisons", f"{d['n_comparisons']:,}".replace(",", "\\,"))
    if d.get("growth_s_per_day") is not None:
        mac("AgeGrowth", num(d["growth_s_per_day"], 2))
    first = next(iter(by.values()))["d_tca_s"]
    mac("AgeDayOne", num(first["mean"], 2))
    for key, macro in (("7-14 d", "AgeWeek"), ("14-30 d", "AgeFortnight"),
                       ("30-90 d", "AgeMonth")):
        if key in by:
            mac(macro, num(by[key]["d_tca_s"]["mean"], 1))


def tab_histtle():
    """Exp 4 re-run with epoch-correct elements, versus the default run."""
    a = load("exp4_weather_value")
    b = load("exp4_weather_value_histtle")
    if not a or not b:
        return
    rows = [("Back-propagated (default)", a), ("Epoch-correct elements", b)]
    L = [r"\begin{table}[t]",
         r"\caption{Effect of how the pass geometry is obtained. The default "
         r"run propagates current elements backwards over the window; the "
         r"second uses the element set that was actually current on each "
         r"night, from Space-Track. The ordering and the monotone rise with "
         r"budget freedom are unchanged, but epoch-correct geometry reports a "
         r"\emph{larger} weather benefit throughout: back-propagation error "
         r"blurs the association between a pass time and the sky above it, "
         r"attenuating the very signal being measured. The default run is "
         r"therefore the conservative one. Threshold value model.}",
         r"\label{tab:histtle}", r"\centering",
         r"\setlength{\tabcolsep}{4pt}",
         r"\begin{tabular}{lrrrr}", r"\toprule",
         r"Element sets & Quota & 75\% & 50\% & 25\% \\", r"\midrule"]
    for label, d in rows:
        bm = d.get("budget_modes") or {}
        cells = []
        for k in ("nightly-quota", "budget-75pct", "budget-50pct",
                  "budget-25pct"):
            v = bm.get(k, {}).get("gain_clear_pct")
            cells.append("--" if v is None else f"{v:+.1f}\\%")
        L.append(f"{label} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_histtle.tex", "\n".join(L) + "\n")

    bm = b.get("budget_modes") or {}
    for k, macro in (("nightly-quota", "HistQuotaClear"),
                     ("budget-50pct", "HistBudgetClear")):
        v = bm.get(k, {}).get("gain_clear_pct")
        if v is not None:
            mac(macro, num(v, 1))


def env_macros():
    for name in ("exp1_accuracy", "exp4_weather_value", "exp6_pipeline"):
        d = load(name)
        if d and "_meta" in d:
            m = d["_meta"]
            mac("PythonVersion", m.get("python", "3.13"))
            mac("SgpVersion", m.get("sgp4_version", "2.27"))
            return


def main():
    print("Generating LaTeX tables...")
    for fn in (tab_accuracy, tab_elements, tab_forecast, tab_weather_value,
               tab_scheduling, tab_pipeline, tab_structure,
               tab_tleage, tab_histtle, env_macros):
        try:
            fn()
        except Exception as exc:                      # noqa: BLE001
            print(f"  [error] {fn.__name__}: {type(exc).__name__}: {exc}")

    # The paper \input{}s a fixed set of tables. If an experiment has not been
    # run yet, emit a visible placeholder rather than letting the LaTeX build
    # fail on a missing file -- a half-finished run should still compile.
    expected = ["tab_accuracy", "tab_elements", "tab_forecast",
                "tab_weather_value", "tab_persite", "tab_scheduling",
                "tab_genetic", "tab_pipeline", "tab_leadsweep",
                "tab_capsweep", "tab_budgetmodes", "tab_structure",
                "tab_tleage", "tab_histtle"]
    os.makedirs(OUT, exist_ok=True)
    for name in expected:
        path = os.path.join(OUT, f"{name}.tex")
        if name not in WRITTEN:
            # Keep the label so \ref{} in the body still resolves.
            label = "tab:" + name[len("tab_"):].replace("_", "")
            write(f"{name}.tex",
                  "\\begin{table}[t]\n\\centering\n"
                  "\\caption{[" + name.replace("_", " ") +
                  ": experiment not yet run]}\n"
                  "\\label{" + label + "}\n"
                  "\\emph{pending}\n\\end{table}\n")

    lines = [r"% Auto-generated by experiments/make_tables.py -- do not edit.",
             r"% Every inline number in the paper resolves through these macros."]
    # Same idea for inline macros: an unrun experiment leaves them undefined,
    # which would abort the build, so any macro the paper uses gets a marker.
    for key in ("NSats", "NPasses", "NMatched", "CallReduction", "CallsFast",
                "CallsDense", "Recall", "Missed", "SkyfieldTca", "SkyfieldAos",
                "DenseAos", "EpochMedian", "EpochUnderOne", "EpochMax",
                "NCatalogue", "ProviderTcaMean", "ProviderTcaPninetyfive",
                "ProviderTcaMax", "ProviderN", "ProviderObjects", "HssOne",
                "HssThree", "HssSeven", "HssPersistence", "ForecastDays",
                "ForecastStart", "ForecastEnd", "ClearThreshold",
                "GreedyGain", "QuotaGainEV", "QuotaGainClear", "QuotaOracleEV",
                "QuotaOracleClear", "QuotaRawEV", "BudgetGainEV",
                "BudgetGainClear", "BudgetOracleEV", "BudgetOracleClear",
                "BudgetRecoveredEV", "BudgetRecoveredClear", "BudgetClearRate",
                "BudgetBlindClearRate", "BudgetTotal", "BestBudgetMode",
                "TightGainClear", "TightGainEV", "TightClearRate",
                "TightBudget", "BtwWthRatio", "BaseSkew",
                "AgeObjects", "AgeComparisons", "AgeGrowth",
                "AgeDayOne", "AgeWeek", "AgeFortnight", "AgeMonth",
                "HistQuotaClear", "HistBudgetClear",
                "PassCorr", "CloudReduction", "StructureDays",
                "ClearThresholdEval", "SlopeChennai",
                "EvalDays", "EvalStart", "EvalEnd", "Capacity", "EvalObjects",
                "TrainDays", "CloudChennai", "SchedTrials", "DPOptimalPct",
                "GreedyBestPct", "GreedyWorstPct", "GreedyElevPct",
                "GreedyElevMin", "GreedyElevOptPct", "GreedyValuePct",
                "GreedyValueMin", "GAPct",
                "GASlowdown", "DPBigN", "DPBigMs", "DemoGeometric",
                "DemoSunlit", "DemoDark", "DemoBright", "DemoClear",
                "DemoScheduled", "DemoRuntime", "DemoHorizon", "DemoObjects",
                "JaccardMid", "JaccardExtreme", "ScaleObjects", "ScaleDays",
                "ScaleSeconds", "PythonVersion", "SgpVersion"):
        MACROS.setdefault(key, r"\textbf{??}")
    for k, v in sorted(MACROS.items()):
        lines.append(f"\\newcommand{{\\{k}}}{{{v}}}")
    write("numbers.tex", "\n".join(lines) + "\n")
    print(f"  ({len(MACROS)} inline macros)")


if __name__ == "__main__":
    main()
