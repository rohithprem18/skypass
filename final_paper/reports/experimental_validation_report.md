# Experimental validation report

What was executed, what was recomputed independently, and what could not be
reproduced here. Environment: Windows 11, Python 3.13.5, `sgp4` 2.27 (the
version recorded in the result files), Tectonic for LaTeX.

## 1. Commands executed

| Command | Result |
|---|---|
| `python -m pytest tests -q` | **42 passed** in 2.70 s (no network). |
| `python experiments/make_tables.py` | Regenerated `paper/generated/` from `results/`: 143 macros, all tables. After experiment 9, also `tab_bootstrap.tex` and the interval macros. |
| `python experiments/make_figures.py --font times --out <dir>` | All 11 figures, Times lettering (IEEE). |
| `python experiments/make_figures.py --font cm --wide 6.0 --out <dir>` | All 11 figures at the Springer text width, Computer Modern. |
| `python experiments/exp9_bootstrap.py` (10,000 resamples, seed 20260101) | Completed; reproduces experiment 4 with 0.000 pp drift. See section 4. |
| `tectonic -X compile` on both final manuscripts | IEEE 6 pages, Springer 11 pages; 0 errors, 0 overfull boxes, 0 undefined references or citations. |
| Crossref / DataCite lookups for all 30 references | See `literature_and_citation_audit.md`. |

Experiments 1-8 were **not** re-run: they take hours, need network access to
CelesTrak and Open-Meteo, and two need Space-Track credentials. Their stored
outputs were audited instead (sections 2 and 3).

## 2. Independent recomputations from stored outputs

| Quantity | How it was recomputed | Result |
|---|---|---|
| Pooled quota-regime gains | Summed `realised_yield` and `success_value` over the six stations' arms in `exp4_weather_value.json` and recomputed the ratios. | EV -1.48%, clear -0.21%, raw EV -9.21%: identical to the stored values. Pooling is a ratio of sums, so stations with more candidates carry more weight. |
| GA mean ratio and slowdown | Averaged the six per-site entries of `part_b_vs_genetic`. | 99.67% and 38,922x: identical. |
| Calibration slope and intercept ranges | Read the six fitted calibrations. | Slopes 0.17-0.61, intercepts 0.07-0.70 (corrects C9). |
| Ageing medians | Read `by_age` bins. | 0.01 / 0.70 / 13.7 s at 0-1 / 7-14 / >30 days (C10). |
| Funnel nesting | Compared `cloud_clear` with `above_floor` and `scheduled` per station. | Not nested: Bengaluru 19 cloud-clear, 25 scheduled (C4). |
| Provider agreement | Read the median of the CelesTrak vs AMSAT difference. | 0.00 s (C15). |
| Per-station quota clear-sky gains | Per-station ratio for the `skypass-prob` arm. | Chennai -2.0, Bengaluru 0.0, Leh +4.5, Tucson +3.5, Singapore -5.8, Reykjavik -17.2 (%). |

## 3. Methodology checks against the code

| Check | Finding |
|---|---|
| Train/test separation for calibration | Fitted on the 90 days ending the day before the evaluation window, night hours only (`exp4_weather_value.py:322-330`). **No leakage.** |
| Verification truth | ERA5 pinned with `models=era5` (`weather.py:161-173`). Without it the archive returns the forecast itself. **Correct.** |
| Oracle arms | Plan with observed cloud; used only as upper bounds. **Correct use.** |
| Headline regime selection | Fixed preference 50% > 25% > 75% in `make_tables.py`, independent of the values. **Not post hoc.** |
| Value model vs planner arm | EV gain uses `skypass` (weight 1 - c-hat); clear-sky gain uses `skypass-prob` (weight P(clear)). Principled, but was undocumented (C17). |
| DP exactness | Code uses 0-based p(j) with a 1-based table; matches brute force on 2000 instances. The paper's printed recurrence was off by one (C5). |
| Coarse step | `max(5, min(30, P/240))` seconds; matches Algorithm 1 in the IEEE copy. |
| GA baseline fairness | Fixed budget (population 60, 120 generations); objective within 0.33% of optimum. The slowdown factor is a property of that budget (C12). Pure Python for both, so the comparison is like for like in language. |
| Evaluation subset | Experiment 4 uses the first 300 objects of the archive, not all 635; now stated. Whether the first 300 are representative was not tested. |

## 4. Station-level uncertainty (experiment 9)

**Design.** Nights within a station are not independent (the paper's own
finding is that cloud is autocorrelated), so the resampling unit is the
station. For each regime the six stations' arms are recomputed over exactly the
window experiment 4 used; stations are resampled with replacement 10,000 times
(seed 20260101), re-pooled with experiment 4's own pooling code, and percentile
95% intervals taken. Before resampling, the script checks that recomputation
reproduces experiment 4.

**Reproduction check.** Maximum drift from the stored experiment 4 values:
**0.000 percentage points** in every regime. The bootstrap therefore describes
the published numbers, not a re-run that happens to differ.

**Run.** `python experiments/exp9_bootstrap.py`, 34 minutes wall time,
output `results/exp9_bootstrap.json` and `results/exp9_console.txt`.

| Regime | EV gain | 95% CI | Clear-sky gain | 95% CI | P(clear gain > 0) |
|---|---|---|---|---|---|
| Nightly quota | -1.5% | [-2.7, +2.0] | -0.2% | [-11.6, +3.5] | 0.46 |
| Budget, 75% of nights | +7.8% | [+3.1, +10.9] | +17.7% | [-4.3, +35.2] | 0.95 |
| **Budget, 50% of nights** | **+19.0%** | **[+9.2, +24.9]** | **+37.6%** | **[+3.1, +80.4]** | 0.98 |
| Budget, 25% of nights | +19.2% | [+9.3, +38.6] | +55.0% | [+24.7, +144.5] | 1.00 |

Uncalibrated planner, half budget: clear-sky +29.9% [+3.6, +90.1].
Oracle headroom, half budget: +106.7% [+68.7, +192.4].

**What it shows.**

* The headline survives: at the half budget both value models' intervals
  exclude zero. The expected-value gain is the more robust of the two
  (+9.2% to +24.9%); the clear-sky gain is real in sign but poorly
  determined (+3.1% to +80.4%), so "37.6%" should be read with its interval.
* The quota finding survives: both intervals straddle zero, consistent with
  "no benefit".
* At the 75% budget the clear-sky interval includes zero; only the
  expected-value gain is established there.
* Calibrated versus raw: the intervals overlap heavily at every budget level.
  The point estimates favour calibration in every regime, but the difference
  itself was not bootstrapped, so "calibration raises the gain" is a
  point-estimate statement, as the manuscripts now say.

**Caveats.** With six clusters a percentile bootstrap is known to understate
uncertainty (each resample can only recombine six stations); the intervals are
approximate and probably too narrow. Both manuscripts state this.

**Now in the manuscripts.** Half-budget intervals in the Results of both copies;
quota intervals stated as including zero; quarter-budget interval in the
Springer copy; method and caveat in the Discussion of both. The full table is
generated as `paper/generated/tab_bootstrap.tex` for the long versions.

## 5. Reproducibility from the supplied materials

| Result | Reproducible from the public repository? |
|---|---|
| Tables and figures from stored results | Yes, once the working tree is pushed (`make_tables.py`, `make_figures.py`). |
| Experiments 1, 5, 6 (accuracy, scheduling, pipeline) | Yes: they use the archived element sets in `tle_archive/` (tracked) and, for experiment 1, the Skyfield package. |
| Experiments 3, 4, 7 (weather) | Conditionally: the weather series are fetched from Open-Meteo and cached locally; the cache is not published, so reproduction depends on Open-Meteo continuing to serve the same archived forecasts and ERA5 values. |
| Experiments 4b, 8 (historical element sets) | Need a Space-Track account; the historical element sets are not redistributed. |
| Experiment 9 | Same inputs as experiment 4; checks it reproduces experiment 4 within 0.5 percentage points before resampling. |
| Random seeds | Experiment 5 GA and experiment 9 use fixed seeds; experiment 4 is deterministic given its inputs. |

**Blocking for any reproducibility claim:** nothing has been committed since
`9a288c4`. The public repository does not yet contain experiment 9 or its results, the
corrected generators, the audit macros, or `final_paper/`.

## 6. Additional experiments that would address real questions

Listed in order of how much they would change a reviewer's confidence. None was
run; none is presented as done.

1. **A second season** (e.g. December-February). Tests whether the quota result
   and the budget gain hold outside the monsoon months. Same scripts, new window.
2. **Threshold sensitivity.** The clear-sky value model uses a hard 30% cut;
   repeating at 20% and 40% shows whether the 37.6% depends on it.
3. **More stations.** The bootstrap interval width is set by six stations; a
   larger panel is the only way to narrow it.
4. **Full-catalogue evaluation** (635 instead of 300 objects), or a check that
   the first 300 objects are representative.
5. **Lead time under the budget regime.** The full paper reports a lead-time
   sweep under the quota only.
