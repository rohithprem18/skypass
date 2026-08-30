"""Render every paper figure from the saved experiment results.

Reads results/*.json and writes figures/*.pdf (vector, for LaTeX). Run the
experiments first; each figure is skipped with a warning if its inputs are
missing.

Usage:
    python experiments/make_figures.py
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _common import FIG_DIR, RESULTS_DIR

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 8,
    "axes.titlesize": 8.5,
    "axes.labelsize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.4,
    "axes.axisbelow": True,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

# Colour-blind-safe qualitative palette (Okabe-Ito).
C = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
     "red": "#D55E00", "purple": "#CC79A7", "grey": "#666666",
     "sky": "#56B4E9", "yellow": "#F0E442"}

COL = 3.4          # IEEE single column, inches
WIDE = 7.1         # double column


def _load(name):
    p = os.path.join(RESULTS_DIR, f"{name}.json")
    if not os.path.exists(p):
        print(f"  [skip] {name}.json not found")
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, f"{name}.pdf")
    fig.savefig(path)
    plt.close(fig)
    print(f"  -> {path}")


# ---------------------------------------------------------------------------
def fig_forecast_skill():
    d = _load("exp3_forecast")
    if not d:
        return
    pooled = d["pooled"]
    leads = sorted(int(k) for k in pooled)
    hss = [pooled[str(k)]["hss"] for k in leads]
    mae = [pooled[str(k)]["mae"] for k in leads]
    pers = d["pooled_baselines"].get("persistence_24h", {})
    clim = d["pooled_baselines"].get("climatology", {})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDE, 2.3))

    ax1.plot(leads, hss, "o-", color=C["blue"], lw=1.4, ms=4,
             label="NWP forecast")
    if pers:
        ax1.axhline(pers["hss"], color=C["orange"], ls="--", lw=1.2,
                    label=f"persistence 24 h ({pers['hss']:.2f})")
    if clim:
        ax1.axhline(clim["hss"], color=C["grey"], ls=":", lw=1.2,
                    label="climatology (0.00)")
    ax1.set_xlabel("forecast lead time (days)")
    ax1.set_ylabel("Heidke skill score")
    ax1.set_title("(a) skill of the clear-sky decision")
    ax1.set_ylim(-0.02, max(hss) * 1.25)
    ax1.legend(frameon=False, loc="upper right")

    ax2.plot(leads, mae, "s-", color=C["red"], lw=1.4, ms=4, label="NWP forecast")
    if pers:
        ax2.axhline(pers["mae"], color=C["orange"], ls="--", lw=1.2,
                    label="persistence 24 h")
    if clim:
        ax2.axhline(clim["mae"], color=C["grey"], ls=":", lw=1.2,
                    label="climatology")
    ax2.set_xlabel("forecast lead time (days)")
    ax2.set_ylabel("MAE of cloud fraction")
    ax2.set_title("(b) continuous error")
    ax2.legend(frameon=False, loc="lower right")
    _save(fig, "fig_forecast_skill")


def fig_site_skill():
    d = _load("exp3_forecast")
    if not d:
        return
    sites = d["sites"]
    # Seven curves need seven legend entries, which will not fit inside the
    # axes without covering data. Put them under the plot instead.
    fig, ax = plt.subplots(figsize=(COL, 2.9))
    cols = [C["blue"], C["orange"], C["green"], C["red"], C["purple"],
            C["sky"], C["grey"]]
    for (k, s), c in zip(sites.items(), cols):
        leads = sorted(int(x) for x in s["leads"])
        ax.plot(leads, [s["leads"][str(l)]["hss"] for l in leads], "-o",
                ms=2.6, lw=1.1, color=c,
                label=f"{s['site'].split(',')[0]} ({100 * s['mean_cloud']:.0f}%)")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xlabel("forecast lead time (days)")
    ax.set_ylabel("Heidke skill score")
    ax.set_title("Forecast skill by site (mean cloud in brackets)", fontsize=8)
    ax.legend(frameon=False, ncol=2, fontsize=6, loc="upper center",
              bbox_to_anchor=(0.5, -0.28), handlelength=1.6,
              columnspacing=1.2, borderaxespad=0.0)
    _save(fig, "fig_site_skill")


def fig_weather_value():
    """Per-site gain under the budget regime where the forecast can act."""
    d = _load("exp4_weather_value")
    if not d:
        return
    sites = d["sites"]
    names, sky, orc = [], [], []
    for k, v in sites.items():
        names.append(v["site"].split(",")[0])
        sky.append(v["gain_clear_pct"])
        orc.append(v["oracle_gain_clear_pct"])

    fig, ax = plt.subplots(figsize=(WIDE, 2.5))
    xs = list(range(len(names)))
    w = 0.38
    ax.bar([x - w / 2 for x in xs], orc, width=w, label="oracle (observed sky)",
           color=C["green"], edgecolor="white", linewidth=0.4, zorder=2)
    ax.bar([x + w / 2 for x in xs], sky, width=w, label="SkyPass (forecast)",
           color=C["blue"], edgecolor="white", linewidth=0.4, zorder=2)
    ax.axhline(0, color="black", lw=0.7, zorder=3)
    ax.set_xticks(xs)
    ax.set_xticklabels(names)
    ax.set_ylabel("gain vs. weather-blind (%)")
    # Headroom above the tallest bar, so the legend has somewhere to sit.
    top = max(orc + sky)
    bot = min(orc + sky)
    ax.set_ylim(bot - abs(bot) * 0.15 - 2, top * 1.30)
    ax.set_axisbelow(True)
    # Legend above the axes: with a bar reaching the top of the panel there is
    # no in-plot corner it can occupy without covering data.
    ax.legend(frameon=False, ncol=2, loc="lower center",
              bbox_to_anchor=(0.5, 1.005), handlelength=1.4, columnspacing=1.6,
              borderaxespad=0.0)
    _save(fig, "fig_weather_value")


def fig_budget_modes():
    """The headline: the forecast only pays when the station may skip nights."""
    d = _load("exp4_weather_value")
    if not d or not d.get("budget_modes"):
        print("  [skip] budget modes not present")
        return
    bm = d["budget_modes"]
    order = [k for k in ("nightly-quota", "budget-75pct", "budget-50pct",
                         "budget-25pct") if k in bm]
    labels = {"nightly-quota": "every\nnight", "budget-75pct": "75% of\nnights",
              "budget-50pct": "50% of\nnights", "budget-25pct": "25% of\nnights"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDE, 2.5))
    xs = list(range(len(order)))
    w = 0.38
    sky = [bm[k]["gain_clear_pct"] for k in order]
    orc = [bm[k]["oracle_gain_clear_pct"] for k in order]
    ax1.bar([x - w / 2 for x in xs], orc, width=w, color=C["green"],
            label="oracle", edgecolor="white", linewidth=0.4)
    ax1.bar([x + w / 2 for x in xs], sky, width=w, color=C["blue"],
            label="SkyPass", edgecolor="white", linewidth=0.4)
    ax1.axhline(0, color="black", lw=0.7)
    ax1.set_xticks(xs)
    ax1.set_xticklabels([labels[k] for k in order])
    ax1.set_ylabel("gain vs. weather-blind (%)")
    ax1.set_xlabel("observing budget for the window")
    ax1.set_title("(a) value of the forecast")
    ax1.legend(frameon=False)

    blind = [100 * bm[k]["success_rate_blind"] for k in order]
    sp = [100 * bm[k]["success_rate_skypass_prob"] for k in order]
    ax2.bar([x - w / 2 for x in xs], blind, width=w, color=C["orange"],
            label="weather-blind", edgecolor="white", linewidth=0.4)
    ax2.bar([x + w / 2 for x in xs], sp, width=w, color=C["blue"],
            label="SkyPass", edgecolor="white", linewidth=0.4)
    ax2.set_xticks(xs)
    ax2.set_xticklabels([labels[k] for k in order])
    ax2.set_ylabel("scheduled passes under clear sky (%)")
    ax2.set_xlabel("observing budget for the window")
    ax2.set_title("(b) observations that actually worked")
    ax2.legend(frameon=False)
    _save(fig, "fig_budget_modes")


def fig_lead_sweep():
    d = _load("exp4_weather_value")
    if not d or not d.get("lead_sweep"):
        print("  [skip] lead sweep not present (run exp4 with --lead-sweep)")
        return
    sw = d["lead_sweep"]
    leads = sorted(int(k) for k in sw)
    gain = [sw[str(l)]["gain_clear_pct"] for l in leads]
    orc = [sw[str(l)]["oracle_gain_clear_pct"] for l in leads]
    fig, ax = plt.subplots(figsize=(COL, 2.2))
    ax.plot(leads, orc, "s--", color=C["green"], lw=1.2, ms=3.5,
            label="oracle (observed sky)")
    ax.plot(leads, gain, "o-", color=C["blue"], lw=1.4, ms=4,
            label="SkyPass (forecast)")
    ax.axhline(0, color="black", lw=0.7)
    ax.set_xlabel("forecast lead time (days)")
    ax.set_ylabel("gain vs. weather-blind (%)")
    # The sweep runs in the nightly-quota regime, where the gain is ~0 at every
    # lead. Naming that is the honest title: nothing here decays, because there
    # is no gain to decay from.
    ax.set_title("Under a nightly quota, no lead time helps", fontsize=8)
    ax.legend(frameon=False, fontsize=6.5, loc="center right")
    _save(fig, "fig_lead_sweep")


def fig_calibration():
    d = _load("exp4_weather_value")
    if not d:
        return
    sites = d["sites"]
    fig, ax = plt.subplots(figsize=(COL, 2.4))
    xs = [i / 50 for i in range(51)]
    cols = [C["blue"], C["orange"], C["green"], C["red"], C["purple"],
            C["sky"], C["grey"]]
    for (k, s), c in zip(sites.items(), cols):
        cal = s.get("calibration")
        if not cal:
            continue
        ys = [max(0.0, min(1.0, cal["intercept"] + cal["slope"] * x)) for x in xs]
        ax.plot(xs, ys, lw=1.2, color=c,
                label=f"{s['site'].split(',')[0]} (b={cal['slope']:.2f})")
    ax.plot([0, 1], [0, 1], "k:", lw=0.9, label="perfectly reliable")
    ax.set_xlabel("forecast cloud fraction")
    ax.set_ylabel("expected observed cloud fraction")
    ax.set_title("Forecast reliability is far from the diagonal")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=6)
    _save(fig, "fig_calibration")


def fig_scheduler():
    d = _load("exp5_scheduling")
    if not d:
        return
    a = d["part_a_exactness"]["heuristics"]
    c = d["part_c_scaling"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(WIDE, 2.3))

    # Two decimals matter here: greedy-on-the-score reaches 99.95%, which at one
    # decimal prints as "100.0" and would read as exact when it is not.
    names = sorted(a, key=lambda k: a[k]["mean_ratio_to_optimum"])
    vals = [100.0 * a[k]["mean_ratio_to_optimum"] for k in names]
    short = [k.replace("greedy-", "") for k in names]
    # Greedy on the true objective is near-optimal; the proxy rules are not.
    # Colouring them apart is the honest reading of this panel.
    colours = [C["orange"] if k != "greedy-highest-value" else C["sky"]
               for k in names]
    bars = ax1.barh(short + ["DP (exact)"], vals + [100.0],
                    color=colours + [C["blue"]],
                    edgecolor="white", linewidth=0.5)
    ax1.set_xlim(min(vals) - 7, 101.5)
    ax1.set_xlabel("mean objective, % of the exact optimum")
    ax1.set_title("(a) proxy rules lose value; score-greedy does not")
    for b, v in zip(bars, vals + [100.0]):
        ax1.text(v - 0.5, b.get_y() + b.get_height() / 2, f"{v:.2f}",
                 va="center", ha="right", fontsize=6, color="white")

    ns = [r["n"] for r in c]
    ms = [1000 * r["mean_s"] for r in c]
    ax2.loglog(ns, ms, "o-", color=C["blue"], lw=1.4, ms=4, label="measured")
    ref = [ms[0] * (n / ns[0]) for n in ns]
    ax2.loglog(ns, ref, "k:", lw=0.9, label="linear reference")
    ax2.set_xlabel("candidate passes $n$")
    ax2.set_ylabel("scheduling time (ms)")
    ax2.set_title("(b) exact DP scales linearly in practice")
    ax2.legend(frameon=False)
    _save(fig, "fig_scheduler")


def fig_funnel():
    d = _load("exp6_pipeline")
    if not d:
        return
    rows = d["part_a_optical"]
    key = "chennai" if "chennai" in rows else list(rows)[0]
    f = rows[key]["funnel"]
    stages = [("geometric\npasses", f["geometric"]),
              ("sunlit", f["sunlit"]),
              ("observer\nin darkness", f["dark_sky"]),
              ("bright\nenough", f["bright_enough"]),
              ("forecast\nsky usable", f["cloud_clear"]),
              ("scheduled", f["scheduled"])]
    fig, ax = plt.subplots(figsize=(WIDE, 2.2))
    labels = [s[0] for s in stages]
    vals = [s[1] for s in stages]
    cols = [C["grey"], C["yellow"], C["sky"], C["orange"], C["blue"], C["green"]]
    # The funnel spans three orders of magnitude, so on a linear axis the final
    # stages are invisible -- which hides the very drop the figure is about.
    floor = 1.0
    bars = ax.bar(labels, [max(v, floor) for v in vals], bottom=floor,
                  color=cols, edgecolor="white", linewidth=0.6, zorder=2)
    ax.set_yscale("symlog", linthresh=10)
    for b, v, prev in zip(bars, vals, [None] + vals[:-1]):
        txt = f"{v:,}" if prev is None else f"{v:,}\n({100.0 * v / vals[0]:.1f}%)"
        ax.annotate(txt, (b.get_x() + b.get_width() / 2, max(v, floor)),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=6.5, zorder=3)
    ax.set_ylabel("passes (log scale)")
    ax.set_ylim(floor, max(vals) * 6.0)
    ax.grid(axis="y", which="major", alpha=0.25, linewidth=0.4)
    ax.set_axisbelow(True)
    ax.set_title(f"Visibility funnel, {rows[key]['site']}, "
                 f"{rows[key]['horizon_days']:.0f}-day horizon")
    _save(fig, "fig_funnel")


def fig_weight_sensitivity():
    d = _load("exp6_pipeline")
    if not d:
        return
    rows = d["part_b_weight_sensitivity"]
    w = [r["w_elev"] for r in rows]
    fig, ax = plt.subplots(figsize=(COL, 2.2))
    ax.plot(w, [r["jaccard_vs_default"] for r in rows], "o-", color=C["blue"],
            lw=1.4, ms=4, label="Jaccard vs $w_e=0.5$")
    ax.set_xlabel("elevation weight $w_e$  ($w_d = 1 - w_e$)")
    ax.set_ylabel("Jaccard overlap of the timetable")
    ax.set_ylim(0, 1.05)
    ax2 = ax.twinx()
    ax2.plot(w, [r["mean_el_max_deg"] for r in rows], "s--", color=C["orange"],
             lw=1.2, ms=3.5, label="mean culmination")
    ax2.set_ylabel("mean culmination elevation (deg)")
    ax2.grid(False)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], frameon=False,
              loc="lower center")
    ax.set_title("Timetable is stable across score weights")
    _save(fig, "fig_weight_sensitivity")


def fig_accuracy():
    """Timing agreement against both references.

    Three things this has to get right. The two series differ by roughly an
    order of magnitude, so a linear axis renders the Skyfield bars as slivers:
    hence the log scale. The p95 whisker is an upper quantile, not a symmetric
    spread, so it is drawn upward only -- a symmetric bar would dip below zero,
    which is meaningless for an absolute difference. And the legend goes above
    the axes, where it cannot cover a bar or a whisker.
    """
    d = _load("exp1_accuracy")
    if not d:
        return
    a, b = d["part_a_dense_reference"], d["part_b_skyfield"]
    groups = [r"$|\Delta t_{\mathrm{AOS}}|$",
              r"$|\Delta t_{\mathrm{TCA}}|$",
              r"$|\Delta t_{\mathrm{LOS}}|$"]
    keys = ["d_aos_s", "d_tca_s", "d_los_s"]
    have_b = "d_aos_s" in b

    fig, ax = plt.subplots(figsize=(COL, 2.35))
    xs = list(range(len(groups)))
    w = 0.34

    series = [(a, C["orange"], "vs. 1 s dense scan", -w / 2)]
    if have_b:
        series.append((b, C["blue"], "vs. Skyfield", w / 2))

    for src, colour, label, off in series:
        means = [src[k]["mean"] for k in keys]
        # Upper-only whisker: the bar top is the mean, the cap is p95.
        upper = [max(src[k]["p95"] - src[k]["mean"], 0.0) for k in keys]
        pos = [x + off for x in xs]
        ax.bar(pos, means, w, color=colour, label=label, edgecolor="white",
               linewidth=0.5, zorder=2)
        ax.errorbar(pos, means, yerr=[[0.0] * len(means), upper], fmt="none",
                    ecolor="black", elinewidth=0.8, capsize=2.5, capthick=0.8,
                    zorder=3)
        for x, m in zip(pos, means):
            ax.annotate(f"{m:.3f}", (x, m), xytext=(0, -2.5),
                        textcoords="offset points", ha="center", va="top",
                        fontsize=5.8, color="white", zorder=4)

    ax.set_yscale("log")
    lo = min(min(s[0][k]["mean"] for k in keys) for s in series)
    hi = max(max(s[0][k]["p95"] for k in keys) for s in series)
    ax.set_ylim(lo / 3.0, hi * 2.6)
    ax.set_xticks(xs)
    ax.set_xticklabels(groups)
    ax.set_xlim(-0.55, len(groups) - 0.45)
    ax.set_ylabel("absolute difference (s)")
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v:g}" if v >= 0.01 else ""))
    ax.grid(axis="y", which="both", alpha=0.25, linewidth=0.4)
    ax.set_axisbelow(True)
    # Legend above the axes so it can never sit on top of the data. No axes
    # title: the LaTeX caption carries it, and a title here would collide with
    # the legend and duplicate the caption in print.
    ax.legend(frameon=False, ncol=2, loc="lower center",
              bbox_to_anchor=(0.5, 1.005), handlelength=1.4,
              columnspacing=1.4, borderaxespad=0.0)
    _save(fig, "fig_accuracy")


def fig_tle_age():
    """Where prediction accuracy actually comes from, as a function of age."""
    d = _load("exp8_tle_age")
    if not d or d.get("skipped") or not d.get("by_age"):
        print("  [skip] exp8 age data not present")
        return
    by = d["by_age"]
    acc = _load("exp1_accuracy")
    floor = None
    if acc and "d_tca_s" in acc.get("part_b_skyfield", {}):
        floor = acc["part_b_skyfield"]["d_tca_s"]["mean"]

    labels, mids, means, p95s = [], [], [], []
    for k, v in by.items():
        lo, hi = k.replace(" d", "").split("-")
        mids.append((float(lo) + float(hi)) / 2.0)
        labels.append(k)
        means.append(v["d_tca_s"]["mean"])
        p95s.append(v["d_tca_s"]["p95"])

    fig, ax = plt.subplots(figsize=(COL, 2.5))
    ax.plot(mids, p95s, "s--", color=C["orange"], lw=1.1, ms=3.4, label="p95")
    ax.plot(mids, means, "o-", color=C["blue"], lw=1.5, ms=4.2, label="mean")
    if floor:
        # The numerical noise floor: below this line the algorithm, not the
        # elements, would be the limiting term.
        ax.axhline(floor, color=C["grey"], ls=":", lw=1.1)
        ax.annotate("numerical floor\n(vs. Skyfield)", (mids[0], floor),
                    xytext=(2, 4), textcoords="offset points",
                    fontsize=5.8, color=C["grey"], va="bottom")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("element-set age at prediction time (days)")
    ax.set_ylabel("culmination-time error (s)")
    ax.set_title("Elements dominate beyond a few days", fontsize=8)
    ax.grid(True, which="both", alpha=0.22, linewidth=0.4)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    _save(fig, "fig_tle_age")


def _placeholder(name):
    """Emit a visibly-blank figure so a partially-run study still compiles."""
    fig, ax = plt.subplots(figsize=(COL, 1.4))
    ax.text(0.5, 0.5, f"[{name}: experiment not yet run]", ha="center",
            va="center", fontsize=8, color=C["grey"])
    ax.set_axis_off()
    _save(fig, name)


def main():
    print("Rendering figures...")
    for fn in (fig_accuracy, fig_forecast_skill, fig_site_skill,
               fig_calibration, fig_weather_value, fig_budget_modes,
               fig_lead_sweep, fig_scheduler, fig_funnel,
               fig_weight_sensitivity, fig_tle_age):
        try:
            fn()
        except Exception as exc:                      # noqa: BLE001
            print(f"  [error] {fn.__name__}: {type(exc).__name__}: {exc}")

    # The paper references a fixed set of figures; fill any gaps so that a
    # half-finished run still produces a compilable document.
    for name in ("fig_accuracy", "fig_forecast_skill", "fig_site_skill",
                 "fig_calibration", "fig_weather_value", "fig_lead_sweep",
                 "fig_scheduler", "fig_funnel", "fig_weight_sensitivity",
                 "fig_budget_modes", "fig_tle_age"):
        if not os.path.exists(os.path.join(FIG_DIR, f"{name}.pdf")):
            _placeholder(name)


if __name__ == "__main__":
    main()
