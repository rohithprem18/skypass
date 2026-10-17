# SkyPass: project memory (handoff file)

Complete working memory of the SkyPass project for an assistant taking it over.
Everything here was verified against the code and `results/*.json` on
**13 Oct 2026**. The manuscripts (in `final_paper/`) are deliberately
out of scope; this file is about the system, its experiments and its results.

---

## 1. What SkyPass is

SkyPass is a **weather-aware satellite pass planner for small ground stations**
(university labs, amateur-radio clubs, individual optical observers). Given a
location, it:

1. downloads public orbital elements (TLEs),
2. propagates every satellite with SGP4,
3. finds every pass over the station (rise, peak, set),
4. scores each pass for visibility (geometry, sunlight/darkness, brightness, cloud),
5. picks the best set of non-overlapping passes the station can actually attend,
6. exports a timetable (terminal table, CSV, JSON, iCalendar) and serves a web app.

It ships as a Python library, a CLI, and a React web console, all driven by the
same engine. Runtime dependency: only `sgp4` (Python >= 3.9). Licence MIT.

* Repo: `github.com/rohithprem18/skypass` (public). Local: `C:\Users\admin\Documents\projctss\SkyPass`.
* Author: Rohith Prem S (`rohithprem18`), CSE, Saveetha Engineering College, Chennai.
  Supervisor: Dr. R. Selvakumar (AI & ML). Academic context: Project Work Phase 1 (19AI701).
* Default station: Chennai, India.

---

## 2. Status snapshot (13 Oct 2026)

* **Git:** last commit `9a288c4`. Everything since is uncommitted, including
  experiment 9 and its results, generator fixes, `final_paper/`, `CLAUDE.md`,
  this file. The public repository is behind the working tree.
* **Tests:** `python -m pytest tests -q` -> 42 passed (2.7 s, no network).
* **Deployment:** Vercel. `vercel.json` builds `webapp/ui` and rewrites `/api/*`
  to `api/index.py` (wraps `webapp.server`). Branch `origin/vercel` exists.
* **Experiments:** 1-9 all have results in `results/`. Experiment 9 (bootstrap)
  was run on 13 Oct 2026 and reproduces experiment 4 exactly.

---

## 3. Read this first: traps and known gaps

1. **The live planner does not calibrate the forecast.** `skypass.pipeline.plan()`
   (used by the CLI and the web app) passes the *raw* Open-Meteo cloud forecast
   into the score (`pipeline.py:168`). Calibration (`weather.fit_calibration`) is
   only applied inside the experiments (`experiments/exp4_weather_value.py`).
   Experiment 4 shows the raw forecast is *worse than ignoring weather* under a
   nightly quota. Fixing this is the top engineering task (section 11).
2. **The live planner does not offer the regime where weather helps.** CLI `plan()`
   uses `optimal_schedule` (no per-night limit, no window budget). The web app uses
   `capacity_schedule(..., per_night=True)` when a `capacity` query parameter is
   given. Neither exposes `budget_schedule`, the window-budget scheduler that is
   the only regime with a measured weather benefit.
3. **Pin `models=era5` on the Open-Meteo archive endpoint** (`weather.py:161`).
   The default "best match" archive series *is* the archived forecast for recent
   dates, so verifying against it gives a fake perfect skill of 1.0. This bug was hit.
4. **`tle_archive/` is tracked on purpose.** CelesTrak serves only current
   elements; without the dated archive no past prediction is reproducible. Only
   one date is archived: `2026-08-29.txt` (+ `amsat-2026-08-29.txt`).
5. **`cache/` (Open-Meteo responses) is gitignored**, about 190 files locally.
   Weather results are reproducible only while Open-Meteo still serves the same archive.
6. **Space-Track** historical elements (experiments 4b, 8) need credentials in
   env vars or `.env.local` / `.env` / `.spacetrack` (all gitignored) and are not
   redistributed. Never write credentials into output.
7. **Every reported number must come from `results/` via
   `experiments/make_tables.py`** (writes `generated/numbers.tex`, 147 macros, and
   updates both papers in `final_paper/`). Never hand-type a result anywhere.
8. **Element age is a first-class constraint.** Elements older than 7 days are
   rejected; it is the largest lever on accuracy.
9. **Funnel caveat.** `Funnel.cloud_clear` (cloud < 0.50) is a *diagnostic count*,
   not a filter. Cloud enters the score as a continuous weight; the scheduler draws
   from passes with score >= 0.05 (`above_floor`). These sets are not nested
   (Bengaluru: 19 cloud-clear, 25 scheduled).

---

## 4. How it works (the pipeline)

`elements -> SGP4 -> pass extraction -> visibility score -> scheduling -> timetable`.
Each stage is a pure function of the previous one, so stages can be ablated
(that is how weather value is measured: same chain, `weather_aware` on/off).

### 4.1 Orbital elements (`skypass/tle.py`)
* Fetch CelesTrak GP groups (`DEFAULT_TLE_GROUPS`): stations, visual, weather,
  amateur, science, resource, cubesat, engineering. URL
  `https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=TLE`.
  AMSAT (`https://www.amsat.org/tle/current/nasabare.txt`) optional, for cross-checks.
* Checksum-validate each line, dedupe by NORAD id keeping the newest epoch,
  archive under the retrieval date (`tle_archive/YYYY-MM-DD.txt`).
* Reject elements older than `max_tle_age_days = 7`. Catalogue size: 635 objects.

### 4.2 Propagation and geometry (`skypass/geometry.py`, `passes.py`)
* SGP4 (reference `sgp4` package) gives TEME positions; rotated to ECEF by GMST;
  WGS-84 topocentric azimuth/elevation/range. Polar motion neglected (< 15 m).
  Refraction computed and reported but **not** applied to the mask.
* Sun position: low-precision solar ephemeris (`sun_teme`). Shadow: conical
  umbra/penumbra (`shadow_state`); only `umbra` counts as eclipsed.

### 4.3 Pass extraction (`passes.find_passes`)
* Coarse elevation sampling with step `h = max(5, min(30, P/240))` seconds
  (`adaptive_coarse_step`; P = orbital period). Short-period orbits get finer steps.
* A sign change of `elevation - mask` between adjacent samples brackets one
  crossing; refine by **bisection** to `tol_s = 0.1` s (AOS, LOS).
* Culmination (TCA) by **golden-section** search.
* Passes already in progress at the window start or still up at the end are
  "clipped" and excluded. Very short grazing passes between two samples can be missed.
* `find_passes_dense` is the 1 s brute-force reference; `PropagationCounter`
  counts SGP4 calls.

### 4.4 Visibility score (`skypass/scoring.py`)
`S = (w_e*f_e + w_d*f_d) * f_m * f_s`, then scheduling value `v = S * priority`.

* `f_e = min(el_max/60 deg, 1)`, `f_d = min(duration/480 s, 1)`, `w_e = w_d = 0.5`
  (normalised to sum 1).
* Optical mode gates, in order: satellite in umbra -> rejected "eclipsed" (score 0);
  Sun not below `twilight_deg = -6` -> rejected "daylight" (0).
* Magnitude: `m = m_std + 5 log10(range/1000 km) - 2.5 log10(F(psi))`,
  `F(psi) = ((pi - psi) cos psi + sin psi) / pi` (diffuse sphere).
  `m_std` from `STANDARD_MAGNITUDE` (e.g. ISS -1.8, HST 1.5, NOAA 4.3), default 5.0.
  If `m > mag_limit (6.0)` -> rejected "too_faint" (0). Otherwise
  `f_m = max(0.10, min(1, (6 - m)/6))` (floor 0.10).
* Sky: `f_s = (1 - c)^cloud_exponent` (exponent 1.0), cloud `c` interpolated at TCA.
  Applied only if `weather_aware` and optical mode (radio mode ignores cloud by default).
* Priority multipliers (`DEFAULT_PRIORITY`, substring match, longest wins):
  ISS 2.0, CSS 1.8, NOAA 1.5, METEOR 1.4, METOP 1.3, HST 1.3, else 1.0.
* Multiplicative on purpose: a failed hard condition must zero the score. Do not
  make it additive.

### 4.5 Weather (`skypass/weather.py`)
* `forecast(site, days)`: operational hourly total cloud from Open-Meteo.
* `previous_runs(site, start, end, lead_days)`: archived forecasts at a given lead.
* `reanalysis(site, start, end, model="era5")`: ERA5 truth.
* `fit_calibration(pred, truth, hour_filter)`: least squares `c_hat = a + b*c_f`,
  clipped to [0, 1]. Fitted on a window that ends before the evaluated period,
  night hours only (`night_hours_filter`, 19:00-05:00 local solar).
* `fit_clear_probability(pred, truth, threshold=0.30, n_bins=10, prior_strength=20)`:
  P(cloud <= 0.30 | forecast) in 10 forecast bins, shrunk toward the base rate.
* `skill_scores`: MAE, RMSE, bias, accuracy, POD, FAR, Heidke skill score.
* Baselines: `persistence_series` (24 h), `climatology_series`.
* Responses cached on disk in `cache/`.

### 4.6 Scheduling (`skypass/scheduler.py`)
Weighted interval scheduling with a setup gap `g = 5 min` (passes i, j compatible
if `end_i + g <= start_j`). Passes sorted by end time; `p(j)` = latest compatible
earlier pass (code uses 0-based `p`, -1 if none, with a 1-based table).

* `optimal_schedule`: unconstrained exact DP, O(n log n).
  `OPT[j] = max(OPT[j-1], v_j + OPT[p(j)+1])` in code indexing.
* `capacity_schedule(..., capacity=K, per_night=True)`: exact, at most K per
  observing night, O(nK) after sort. In 1-based maths:
  `OPT[j][k] = max(OPT[j-1][k], v_j + OPT[p(j)][k-1])`.
* `budget_schedule`: per-night cap plus a total budget for the window, so the
  station may skip nights (the regime where forecasts help).
* `observing_night(pass, lon)`: groups an evening with the following small hours
  by local solar time. Nights are disjoint, so per-night solving stays exact.
* Baselines: `greedy_highest_value`, `greedy_max_elevation`, `greedy_longest_duration`,
  `greedy_earliest_finish`, `greedy_capacity`, `greedy_budget`, `brute_force_*`,
  `genetic_schedule` (order-based GA).

### 4.7 Orchestration and output
* `skypass.pipeline.plan(site, days=7, t0, mode, weather_aware=True, clouds,
  fetch_weather=True, weights, cfg, archive_dir, tle_path, limit, name_filter,
  records, scheduler=optimal_schedule)` -> `PlanResult` (passes, candidates,
  schedule, funnel, runtime, propagation count).
* `Funnel`: catalogue, stale_elements, geometric, sunlit, dark_sky, bright_enough,
  cloud_clear (diagnostic), above_floor, scheduled.
* `skypass/report.py`: `format_plan`, `write_csv`, `write_json`, `write_ics`.
* Public API: `from skypass import plan, GROUND_STATIONS` (see `skypass/__init__.py`).

---

## 5. Configuration defaults (`skypass/config.py`)

| Setting | Default | Meaning |
|---|---|---|
| `Site.min_elev_deg` | 10 | horizon mask |
| `Site.twilight_deg` | -6 | Sun elevation for a dark sky |
| `Site.setup_gap_min` | 5 | re-pointing gap between targets |
| `PlannerConfig.coarse_step_s` | 30 | max coarse step (adaptive step capped here) |
| `PlannerConfig.tol_s` | 0.1 | bisection / golden-section tolerance |
| `PlannerConfig.score_floor` | 0.05 | minimum score to be a candidate |
| `PlannerConfig.cloud_cutoff` | 0.50 | "clouded out" reporting threshold (diagnostic) |
| `PlannerConfig.max_tle_age_days` | 7.0 | stale element rejection |
| `ScoreWeights.w_elev / w_dur` | 0.5 / 0.5 | geometry weights |
| `elev_sat_deg / dur_sat_s` | 60 / 480 | saturation points |
| `mag_limit / mag_bright / mag_floor` | 6.0 / 0.0 / 0.10 | photometric factor |
| `cloud_exponent` | 1.0 | sky factor exponent |

Preset stations (`GROUND_STATIONS`, chosen to span cloud climates):

| Key | Name | Lat | Lon | Alt (m) | Climate |
|---|---|---|---|---|---|
| chennai | Chennai, India | 12.92 | 80.12 | 30 | monsoon (default) |
| bengaluru | Bengaluru, India | 12.97 | 77.59 | 920 | monsoon |
| leh | Leh, India | 34.16 | 77.58 | 3500 | high-altitude arid |
| tucson | Tucson, USA | 32.22 | -110.97 | 728 | desert |
| singapore | Singapore | 1.35 | 103.82 | 15 | equatorial |
| reykjavik | Reykjavik, Iceland | 64.13 | -21.90 | 30 | maritime polar |
| svalbard | Svalbard, Norway | 78.23 | 15.39 | 450 | high Arctic |

---

## 6. Commands

```bash
python -m pip install -e ".[experiments]"   # sgp4 at runtime; numpy, matplotlib, skyfield for experiments
python -m skypass fetch [--amsat]           # download + archive element sets
python -m skypass stations                  # list presets
python -m skypass archives                  # list archived element files
python -m skypass passes --days 1           # geometric passes, no scoring
python -m skypass plan --days 7 --ics results/plan.ics
#   plan flags: --station, --lat/--lon/--alt/--name, --mask, --twilight, --gap,
#   --sat ISS,NOAA, --limit, --radio, --no-weather, --w-elev, --csv/--json/--ics,
#   --json-all, --limit-rows, global --archive-dir
python -m pytest tests -q                   # 42 tests

python experiments/expN_*.py                # regenerate results/*.json
python experiments/make_tables.py           # results -> generated/ (+ updates final_paper/)
python experiments/make_figures.py [--font cm|times] [--wide 6.0] [--out DIR]

python webapp/server.py                     # http://localhost:8000 (serves built UI)
cd webapp/ui && npm ci && npm run build     # React build; npm run dev for Vite on :5173
```

Paths are anchored in `skypass/paths.py` (`PROJECT_ROOT`, `CACHE_DIR`,
`RESULTS_DIR`, `FIGURES_DIR`, `TLE_ARCHIVE_DIR`), so commands work from any subdirectory.

### Web app
* Server: Python stdlib `http.server` only (deliberately no framework).
* Endpoints: `/api/stations`, `/api/plan` (query: station or lat/lon, days,
  capacity, ...), `/api/track`, `/api/ics`.
* `WEB_OBJECT_LIMIT = 140` objects for interactivity (full 635 takes ~2 minutes).
* UI: React 19 + TypeScript 5 + Vite 7 (`webapp/ui/src`). Views: Overview,
  Planner, Passes, Weather, Schedule, Analysis, Experiments, live countdown.

---

## 7. Repository map

| Path | Contents |
|---|---|
| `skypass/` | engine: `config, tle, timeutil, geometry, passes, scoring, weather, scheduler, pipeline, report, spacetrack, cli, paths` |
| `experiments/` | `exp1`-`exp9`, `_common.py`, `make_tables.py`, `make_figures.py`, `check_paper.py` |
| `tests/` | 42 deterministic unit tests, no network |
| `results/` | experiment outputs (JSON + console logs); the only data source for reported numbers |
| `figures/` | generated vector figures (PDF tracked) |
| `tle_archive/` | dated element-set archives (tracked) |
| `cache/` | Open-Meteo responses (gitignored) |
| `webapp/`, `api/` | web server + React UI; Vercel entry point |
| `docs/` | setup notes (e.g. `docs/spacetrack-setup.md`) |
| `generated/` | result macros and tables built by `make_tables.py` |
| `final_paper/` | the only manuscripts (IEEE and Springer) and audit reports (out of scope here) |

---

## 8. Experiments and all results

All weather experiments use the window **2026-06-25 to 2026-08-23 (60 days)**.
Element archive for experiments 1, 4, 5, 6: `tle_archive/2026-08-29.txt`.
Environment recorded in results: Python 3.13.5, sgp4 2.27, Windows 11, Intel CPU.

### Exp 1: pass-prediction accuracy and cost (`exp1_accuracy.py`)
Chennai, 635 objects, 24 h from 2026-08-29, mask 10 deg.

| Quantity | vs 1 s dense scan (mean / p95) | vs Skyfield (mean / p95) |
|---|---|---|
| AOS error | 0.504 / 0.954 s | 0.060 / 0.157 s |
| TCA error | 0.248 / 0.476 s | **0.055** / 0.110 s |
| LOS error | 0.502 / 0.956 s | 0.059 / 0.156 s |
| max-elevation error | 0.0008 / 0.0022 deg | 0.0034 / 0.0102 deg |

* Matched passes 1761; recall vs dense **99.78%** (4 missed, 3 spurious, 37 clipped excluded).
* SGP4 calls 2,311,148 vs 54,864,000 dense: **23.7x fewer**.
* The dense-scan "error" is mostly the 1 s grid's own lag (~0.5 s); SkyPass is
  closer to Skyfield than the dense scan is.

### Exp 2: element sets (`exp2_elements.py`)
* Catalogue epoch age: median **0.42 d**, mean 0.55, p90 0.95, max 13.04;
  573 of 635 under 1 day (90.2%).
* CelesTrak vs AMSAT: 52 objects, 308 matched passes, TCA difference mean
  0.041 s, **median 0.00 s**, p95 0.176, max 1.82. The providers mostly serve
  identical upstream sets, so this is **not** an independent cross-check.

### Exp 3: cloud-forecast skill (`exp3_forecast.py`)
7 stations, ERA5 truth, clear = cloud <= 30%, n = 10,080 hours per lead.

| Lead (days) | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| Pooled HSS | 0.378 | **0.347** | 0.289 | 0.289 | 0.191 | 0.145 | 0.176 | **0.114** |

* Persistence (24 h) HSS 0.206; climatology 0 by construction. Forecast beats
  persistence early, not at 5-7 days.
* Per-station HSS at 1 day: Chennai 0.085, Bengaluru 0.134, Leh 0.298,
  Singapore 0.406, Tucson 0.440, Reykjavik 0.491, Svalbard 0.576. Lowest at the
  monsoon stations.

### Exp 4: value of weather-aware scheduling (`exp4_weather_value.py`)
**6 stations** (Svalbard excluded: no optically observable passes in the window),
first 300 objects, lead 1 day, K = 3 per night, clear threshold 30%, calibration
trained on the 90 days ending the day before the window (27 Mar - 24 Jun 2026),
night hours only. Mean observed cloud over Chennai candidates: 88%.

Arms: `blind-greedy`, `blind-optimal` (baseline), `skypass-raw` (uncalibrated),
`skypass` (calibrated expected cloud), `skypass-prob` (calibrated clear
probability), `oracle-ev`, `oracle-clear` (plan with observed cloud; upper bounds).
Value models: expected value `sum v_j (1 - c_j)` scored for `skypass`;
threshold/clear-sky `sum v_j [c_j <= 0.30]` scored for `skypass-prob`.
Gains are relative to `blind-optimal`; pooling = ratio of sums over stations.

| Regime (budget) | EV gain | Clear gain | Oracle EV / clear | Raw EV / clear | Clear rate blind -> SkyPass |
|---|---|---|---|---|---|
| Nightly quota (none) | -1.5% | -0.2% | 12.0 / 31.6% | **-9.2 / -5.5%** | 15% -> 16% |
| 75% of nights (135) | +7.8% | +17.7% | 30.1 / 60.3% | -0.8 / +11.9% | 14% -> 19% |
| **50% of nights (90)** | **+19.0%** | **+37.6%** | 46.0 / 106.7% | +8.0 / +29.9% | 13.9% -> 23.1% |
| 25% of nights (45) | +19.2% | +55.0% | 61.7 / 179.1% | +8.8 / +43.7% | 13% -> 28% |

* Half budget recovers 41% (EV) and 35% (clear) of the oracle headroom.
* Greedy weather-blind is far worse (about -60% to -75%).
* Under the quota, per-station clear gains: Chennai -2.0, Bengaluru 0.0, Leh +4.5,
  Tucson +3.5, Singapore -5.8, Reykjavik -17.2 (%).
* Lead sweep under the quota (EV, clear) by lead 1-7 d: (-1.5, -0.2), (-2.2, -1.4),
  (-0.9, -3.2), (-1.3, -2.4), (-0.4, -2.8), (+0.5, -1.9), (-0.3, -2.1). Flat:
  no lead helps under a quota.
* Capacity sweep under the quota (EV, clear, oracle clear) for K = 1, 2, 3, 5, 8,
  12, 20: (-2.0, 6.1, 45.4), (0.9, 3.6, 38.0), (-1.5, -0.2, 31.6), (-1.7, -1.8,
  23.1), (-1.2, -3.1, 11.1), (-0.5, -1.7, 4.1), (0.0, -0.2, 1.4).
* Calibration fits (intercept a, slope b): Chennai 0.271 + 0.560 f (r 0.59),
  Bengaluru 0.262 + 0.606 f, Leh 0.305 + 0.532 f, Tucson 0.071 + 0.605 f,
  Singapore 0.700 + 0.172 f, Reykjavik 0.371 + 0.509 f. Slopes 0.17-0.61; lines
  cross the diagonal (clear forecasts under-predict cloud, cloudy ones over-predict).

### Exp 4b: epoch-correct geometry (`exp4_weather_value.py --historical-tle`)
Same as exp 4 but each night uses the element set current that night (Space-Track).

| Regime | Clear gain (default -> epoch-correct) | EV gain (default -> epoch-correct) |
|---|---|---|
| Quota | -0.2 -> +9.2% | -1.5 -> +1.7% |
| 75% | 17.7 -> 19.9% | 7.8 -> 9.3% |
| 50% | **37.6 -> 33.2%** | 19.0 -> 19.0% |
| 25% | 55.0 -> 75.9% | 19.2 -> 45.1% |

Larger in three of four regimes, **smaller at the half budget**. Do not claim the
default run is "conservative".

### Exp 5: scheduling (`exp5_scheduling.py`)
* Exactness: DP matched brute force on **2000/2000** random instances (n <= 14,
  gap 5 min).
* Heuristics vs optimum (mean / optimal fraction / worst): highest value
  99.95% / 98.9% / 85.9%; max elevation 95.39% / 62.7% / **9.4%**; earliest finish
  95.54% / 63.5% / 29.3%; longest duration 95.07% / 61.1% / 24.6%.
* GA (population 60, 120 generations) on 6 real candidate sets (200-1224
  candidates): **99.67%** of optimum, **38,922x** slower on average (8-125 s vs
  0.3-2.3 ms). Slowdown depends on the GA budget.
* Scaling: 100,000 candidates in **285.3 ms** (2.85 us per pass).

### Exp 6: end-to-end pipeline (`exp6_pipeline.py`)
* Chennai, 7 days from 2026-08-29, optical, 635 objects: geometric 12,449 ->
  sunlit 8,093 -> dark sky 1,297 -> bright enough 367 -> above floor 87 ->
  scheduled 26 (cloud_clear diagnostic 85); 109.4 s; 16.2 M propagations.
* Other stations (cloud_clear / above_floor / scheduled): Bengaluru 19/70/25,
  Leh 517/504/95, Tucson 272/283/54, Singapore 246/268/52, Reykjavik 649/700/73,
  Svalbard 0/0/0 (38,674 geometric passes, but the Sun never reaches -6 deg there
  in late August).
* Radio mode skips light/brightness gates and cloud.
* Weight sensitivity (Jaccard vs w_e = 0.5): w_e 0.0 -> 0.86, 0.1 -> 0.89,
  0.3 -> 0.93, 0.7 -> 0.89, 0.9 -> 0.70, 1.0 -> 0.70.
* Scaling (objects, days, passes, seconds): (50,1,151,1.8), (50,7,1084,11.1),
  (150,1,449,4.9), (150,7,3198,32.0), (300,1,894,9.6), (300,7,6231,65.3),
  (635,1,1801,15.8), (635,7,12438,104.4). Propagation dominates; scheduling 2.1 ms.

### Exp 7: why the quota fails (`exp7_structure.py`)
* Between-night / within-night cloud SD ratio **2.2** (cloud is autocorrelated
  within a night).
* 90th-percentile pass value / mean = **1.8** (pass quality varies more than sky).
* Forecast-observed correlation at pass times r = 0.41; clearest-forecast decile
  reduces observed cloud by 0.209.

### Exp 8: element-set ageing (`exp8_tle_age.py`)
60 LEO objects, 60-day Space-Track history, 33,223 aged comparisons; TCA error
vs the freshest set.

| Age | 0-1 d | 1-2 d | 2-3 d | 3-5 d | 5-7 d | 7-14 d | 14-30 d | >30 d |
|---|---|---|---|---|---|---|---|---|
| Mean (s) | 0.05 | 0.09 | 0.10 | 0.20 | 0.47 | 4.31 | 16.23 | 75.31 |
| Median (s) | 0.01 | 0.03 | 0.03 | 0.04 | 0.07 | 0.70 | 2.04 | 13.69 |
| n | 592 | 847 | 703 | 921 | 1162 | 4590 | 8369 | 16039 |

Heavy-tailed. Justifies the 7-day cutoff and daily refresh.

### Exp 9: station-level bootstrap (`exp9_bootstrap.py`)
Cluster bootstrap over the 6 stations, 10,000 resamples, seed 20260101, percentile
95% intervals. Reproduces exp 4 with **0.000 pp** drift. Runtime 34 min.

| Regime | EV gain [95% CI] | Clear gain [95% CI] | P(clear > 0) |
|---|---|---|---|
| Quota | -1.5 [-2.7, +2.0] | -0.2 [-11.6, +3.5] | 0.46 |
| 75% | +7.8 [+3.1, +10.9] | +17.7 [-4.3, +35.2] | 0.95 |
| **50%** | **+19.0 [+9.2, +24.9]** | **+37.6 [+3.1, +80.4]** | 0.98 |
| 25% | +19.2 [+9.3, +38.6] | +55.0 [+24.7, +144.5] | 1.00 |

Raw at 50%: clear +29.9 [+3.6, +90.1]. With six clusters the intervals are
approximate and probably too narrow. Calibrated-minus-raw difference not tested.

---

## 9. What the results mean (state them this way)

* **Forecast value depends on the decision.** Under a fixed nightly quota the
  forecast gives no benefit (intervals include zero). With a window budget that
  lets the station skip nights, it helps: +19.0% EV (CI 9.2-24.9), +37.6% clear
  (CI 3.1-80.4) at half budget. Mechanism: cloud varies 2.2x more between nights
  than within one, and pass quality varies more than sky.
* **Calibration raises the gain in every regime (point estimates).** The raw
  forecast is worse than ignoring weather **only under the quota**; under a budget
  it still helps, less.
* **Accuracy:** 0.055 s vs Skyfield with fresh elements; element age, not the
  algorithm, limits accuracy beyond a few days.
* **Scheduling:** exact and cheap; greedy-by-score is near-optimal on average,
  greedy-by-elevation can be very bad; a GA is unnecessary.

Do **not** say: weather value evaluated at seven stations (it is six; skill is
seven); raw forecast is always worse than ignoring weather; epoch-correct geometry
is larger everywhere / the default is conservative; "usable sky" is a pipeline
stage; CelesTrak and AMSAT are independent; calibration slopes are "0.56 and below".

---

## 10. Data sources

* **CelesTrak** GP elements (no key). **AMSAT** bare TLEs (cross-check).
* **Open-Meteo**: forecast, previous-runs (archived forecasts by lead), archive
  with `models=era5` (truth). No key. Cached in `cache/`.
* **Space-Track**: historical elements, credentials required (`skypass/spacetrack.py`,
  rate-limited, cached; setup in `docs/spacetrack-setup.md`).

---

## 11. Open work (prioritised)

1. **Calibrate in the live planner.** In `pipeline.plan()` (and `webapp/server.py`),
   fit `fit_calibration` on the preceding 90 days of `previous_runs` vs `reanalysis`
   (night hours) and apply `CloudCalibration.apply_series` before scoring. Add a
   test. Consider `--raw-forecast` to keep the old behaviour.
2. **Expose the budget regime.** Add `budget_schedule` to the CLI (e.g.
   `--per-night K --budget N`) and the web app; this is where the forecast pays.
3. **Commit and push** (nothing since `9a288c4`); consider a tagged release with a
   Zenodo DOI.
4. More evidence: a second season, more stations (narrows the bootstrap CI),
   threshold sensitivity (20/30/40%), full 635-object evaluation instead of 300,
   lead-time sweep under the budget regime.
5. Archive weather inputs (or a manifest) so experiments 3, 4, 7, 9 stay reproducible.

---

## 12. Working conventions for this repo

* Commits: conventional style straight to `main` (`feat(webapp): ...`,
  `fix(weather): ...`). Commit or push **only when the user asks**.
* **Never** add Claude/AI attribution (no `Co-Authored-By`, no "Generated with")
  to commits or PRs; the user once force-pushed to remove one.
* Never disable git hooks.
* Never commit secrets (`.env*`, Space-Track credentials).
* Written prose for this project: no em-dashes, formal register, declarative headings.
* After changing results, regenerate with `make_tables.py` / `make_figures.py`;
  never hand-edit numbers.
* `CLAUDE.md` at the repo root holds the longer project notes (including the
  manuscript workflow); this file is the system-and-results summary.
