# SkyPass — project memory

Weather-aware satellite transit planning: turns public orbital elements and public
weather forecasts into a conflict-free, executable night of observations for one
small ground station. Ships as a CLI, a Python library, and a React planning console,
all driven by the same engine. Companion implementation for the papers in `final_paper/`.
**Version 2.0.0** (tag `v2.0.0`) adds two optional learned components in `skypass/ml/`:
a whole-sky-camera cloud nowcast and a satellite-brightness model.

- **Repo:** github.com/rohithprem18/skypass (public) · MIT · Python ≥ 3.9
- **Author:** Rohith Prem S (`rohithprem18`, rohithprem91@gmail.com), CSE, Saveetha
  Engineering College, Chennai. Guide: Dr. R. Selvakumar (AI & ML).
- **Academic context:** Project Work Phase 1 (19AI701), 2023–2027 batch, Team 109,
  register number 212223040172.

---

## Working conventions

- **Never add Claude/Anthropic attribution** to commits or PRs — no `Co-Authored-By`,
  no "Generated with Claude Code". A pushed commit was once rewritten and
  force-pushed specifically to remove this. See `~/.claude/.../memory/`.
- **Commits:** conventional style, straight to `main` (`docs(paper): …`,
  `feat(webapp): …`, `fix(deploy): …`). No branch-per-change workflow in this repo.
- **Never disable git hooks** when committing.
- Commit or push only when asked.

### Prose style (applies to the papers and any written deliverable)

- **No `---` em-dashes.** Both papers were swept to zero; they read as
  AI-generated. Restructure the sentence (comma, semicolon, colon, parentheses,
  or split it) rather than swapping the punctuation.
- **Formal IEEE register.** Avoid essayistic idiom: "earns its keep", "a losing
  game", "bets hard", "blunt instrument", "worth having/doing", "leave value on
  the table", "the picture inverts", "sanity check", "does not need asking".
  Avoid filler "actually / simply / clearly / just".
- **Declarative section headings**, never questions. ("Skill of the cloud
  forecast", not "Does the cloud forecast carry usable skill?")
- Formal prose runs ~10% longer than casual prose; budget for it when a page
  limit is in play.

---

## Layout

```
skypass/          Core engine: propagation, geometry, scoring, weather, scheduling
skypass/ml/       Optional learned components (extra `[ml]`): cloudcam.py, brightness.py
experiments/      11 validation experiments + figure/table generators + paper checker;
                  experiments/diagrams/ holds the TikZ diagram sources
tests/            71 deterministic unit tests, no network (ML tests skip without numpy)
results/          Experiment outputs (JSON + console logs) — the papers' only data source
generated/        Result macros (numbers.tex) and tables, built by make_tables.py
figures/          Generated vector figures (PDF tracked; PNG previews gitignored)
final_paper/      The only manuscripts: ieee/ (6 pp), springer/ (18 pp), reports/ (audit)
tle_archive/      Dated element-set archives (tracked on purpose)
cache/            Cached Open-Meteo responses, ML datasets and trained models under
                  cache/ml/ (gitignored, regenerated on demand)
webapp/           Python stdlib server + React UI
api/              Vercel serverless entry point
docs/             Setup notes and assets
memory.md         Handoff summary of the system and all results (for another assistant)
```

Older paper versions (13-page IEEE, 29-page Springer, the uncorrected short cuts,
`overleaf/`, the Springer template and their compiled PDFs) were moved out of the
project on 15 Oct 2026 to `../SkyPass_old_papers_backup/`. Do not recreate them.

Paths are anchored in `skypass/paths.py` (`PROJECT_ROOT`, `CACHE_DIR`, `RESULTS_DIR`,
`FIGURES_DIR`, `TLE_ARCHIVE_DIR`), so commands work from any subdirectory.

---

## Core package (`skypass/`)

| Module | Role |
|---|---|
| `config.py` | `Site`, `ScoreWeights`, `PlannerConfig`, `GROUND_STATIONS`, magnitude/priority tables, CelesTrak + AMSAT URLs |
| `tle.py` | Fetch, checksum-validate, dedupe, archive by date, reject stale epochs |
| `timeutil.py` | UTC handling, Julian date, GMST |
| `geometry.py` | TEME→ECEF, WGS-84 topocentric, conical shadow, refraction, phase angle, apparent magnitude |
| `passes.py` | `Tracker`, adaptive coarse step, bisection + golden-section refinement, `find_passes` / `find_passes_dense`, `PropagationCounter` |
| `scoring.py` | `score_pass`, `MODE_OPTICAL` / `MODE_RADIO`, `VisibilityReport` |
| `weather.py` | Open-Meteo forecast/archive/previous-runs, `CloudSeries`, calibration, skill scores, persistence & climatology baselines |
| `scheduler.py` | Exact DPs + greedy/GA baselines (see below) |
| `pipeline.py` | `plan()` — the whole chain; `PlanResult`, `Funnel` |
| `report.py` | Terminal timetable, CSV, JSON, iCalendar |
| `spacetrack.py` | Optional historical elements (credentials required) |
| `ml/cloudcam.py` | WSISEG loader, red/blue ratio rule, `PixelGBM`, `UNet`, `default_segmenter()`, `cloud_fraction()` |
| `ml/brightness.py` | SCORE loader and filters, sphere baselines, `BrightnessModel` (gradient-boosted magnitude) |

**Public API:** `from skypass import plan, GROUND_STATIONS` — see `skypass/__init__.py`
for the full `__all__`.

### Pipeline (each stage a pure function of the previous — that is how ablations work)

```
elements → SGP4 propagation → pass extraction → visibility scoring
         → weather calibration → exact scheduling → timetable
```

`Funnel` counts survivors at each constraint: `catalogue → geometric → sunlit →
dark_sky → bright_enough → cloud_clear → above_floor → scheduled`.

### Scoring

`S = (w_e·f_e + w_d·f_d) · f_m · f_s` — **multiplicative on purpose**. A pass failing a
hard requirement (eclipsed, bright sky, overcast) must score zero regardless of
geometry. Do not make this additive; that is exactly the failure mode of
weather-blind planners.

Learned options (v2): `ScoreWeights.magnitude_model="learned"` (CLI
`--learned-brightness`, web `brightness=learned`) replaces the sphere magnitude and
falls back to it when the model or `[ml]` is missing. `plan(nowcast=c)` (CLI
`--sky-image IMG`) overrides the scored cloud for the next hour with a camera
measurement, which is not calibrated. The sphere stays the default because the
learned photometry does not transfer across time (exp 11).

### Schedulers (`scheduler.py`)

- `optimal_schedule` — weighted interval scheduling, exact, O(n log n)
- `capacity_schedule` — adds K observations per night, exact, O(nK)
- `budget_schedule` — multi-night budget, lets the station *skip* nights
- Baselines for comparison: `greedy_*`, `genetic_schedule`, `brute_force_*`
- `observing_night()` groups an evening with the small hours after midnight (local
  solar time), so a night is one session.

---

## Commands

```bash
python -m pip install -e ".[experiments]"     # sgp4 only at runtime; numpy/matplotlib/skyfield for experiments
python -m skypass fetch                       # download + archive elements (run regularly)
python -m skypass stations                    # list presets
python -m skypass archives                    # list archived element files
python -m skypass passes --days 1             # geometric passes, no scoring
python -m skypass plan --days 7 --ics results/plan.ics
python -m pip install -e ".[ml]"              # numpy, pandas, scikit-learn, Pillow, torch
python -m skypass plan --budget 30 --learned-brightness --sky-image sky.jpg
python -m pytest tests -q                     # 71 tests, no network

python experiments/expN_*.py                  # regenerate results/*.json
python experiments/exp10_cloudcam.py          # ~1 h CPU; downloads WSISEG, trains U-Net + GBM
python experiments/exp10_cloudcam.py --final-gbm   # only retrain the deployable GBM
python experiments/exp11_brightness.py        # ~1 min; downloads SCORE, trains the model
python experiments/make_figures.py            # results → figures/*.pdf
python experiments/diagrams/build_diagrams.py # TikZ diagrams (arch, passfind, quota_budget, geometry, unet)
python experiments/make_tables.py             # results → generated/, then updates both final papers
python experiments/check_paper.py             # citations, cross-refs, macros, figures (final_paper/ieee)

python webapp/server.py                       # http://localhost:8000 (serves built UI)
cd webapp/ui && npm ci && npm run build       # React build; npm run dev for Vite on :5173
cd final_paper/ieee && tectonic -X compile skypass.tex        # local build
cd final_paper/springer && tectonic -X compile skypass-sn.tex
```

Useful `plan` flags: `--radio`, `--no-weather`, `--sat ISS,NOAA`, `--mask`, `--gap`,
`--w-elev`, `--lat/--lon/--alt/--name`, `--csv/--json/--ics`, `--limit`,
`--capacity K`, `--budget N`, `--no-calibrate`, `--learned-brightness`, `--sky-image IMG`.

---

## Defaults worth knowing (`config.py`)

`min_elev_deg 10` · `twilight_deg -6` · `setup_gap_min 5` · `coarse_step_s 30` ·
`tol_s 0.1` · `score_floor 0.05` · `cloud_cutoff 0.50` · `max_tle_age_days 7.0` ·
`w_elev/w_dur 0.5` · `mag_limit 6.0`.

Preset stations span cloud climates on purpose: chennai, bengaluru (monsoon), leh
(high-altitude arid), tucson (desert), singapore (equatorial), reykjavik, svalbard
(maritime polar). Default site is chennai.

---

## Data sources

- **CelesTrak** GP elements, 8 groups (`DEFAULT_TLE_GROUPS`) — no key needed
- **AMSAT** — independent provider cross-check
- **Open-Meteo** — forecast, archived forecast, ERA5 reanalysis — no key needed
- **Space-Track** — optional, historical elements only; credentials from env or
  `.env.local` / `.env` / `.spacetrack` (all gitignored). See `docs/spacetrack-setup.md`.
  Credentials are never written into generated output.
- **IAU CPS SCORE** — measured satellite magnitudes, CC-BY 4.0. Any publication must carry
  SCORE's acknowledgement and NSF disclaimer (README and both papers have it). Not redistributed.
- **WSISEG** — 400 labelled whole-sky images, one camera, no licence: cite Xie et al. 2020,
  do not redistribute. Both datasets are downloaded into `cache/ml/` by the experiments.

---

## Invariants and traps

1. **Pin `models=era5` on the Open-Meteo archive endpoint.** The default best-match
   series *is* the archived forecast for recent dates, so verifying against it scores
   a forecast against a copy of itself and reports a perfect, meaningless skill of 1.0.
   This bug was actually hit. See `weather.py:161`.
2. **`tle_archive/` is tracked deliberately.** CelesTrak serves only current elements,
   so without the dated archive a past prediction cannot be reproduced. Same reasoning
   for `results/`, `figures/*.pdf` and `generated/`.
3. **Every number in the papers flows through `generated/numbers.tex`** (about 200 macros).
   Never hand-type a result into the LaTeX; re-run `make_tables.py`, which also copies
   the values into `final_paper/ieee/generated/` and the inlined block of
   `final_paper/springer/skypass-sn.tex`.
4. **Paper figures are copies.** `make_figures.py` writes to `figures/`. The IEEE copy
   uses `fig_tle_age`, `fig_budget_modes`, `fig_scheduler` and `fig_cloudcam_strip` in
   `final_paper/ieee/figures/` (`--font times --wide 3.45`: the two-panel charts switch to a
   compact single-column layout below 4.5 in) plus an inline colour TikZ architecture.
   The Springer copy uses flat files `Fig1`-`Fig13` (`--font cm --wide 6.0 --col 2.75`,
   renamed by first citation): Fig1 arch, Fig2 passfind, Fig3 geometry, Fig4 unet
   (TikZ, from `experiments/diagrams/build_diagrams.py`), Fig5a accuracy, Fig5b
   tle_age, Fig6 forecast_skill, Fig7 quota_budget (TikZ), Fig8a lead_sweep, Fig8b
   calibration, Fig9 budget_modes, Fig10 scheduler, Fig11 funnel, Fig12 cloudcam,
   Fig13 brightness. Copy them across after regenerating, or the uploads go stale.
   Charts are deliberately grid-free (`axes.grid: False` in `make_figures.py`, at the
   authors' request); keep only reference lines that carry meaning.
5. **Never commit secrets.** `.env*` is gitignored; `*.docx`/`*.pptx` review files too.
6. **Element age is a first-class constraint**, not housekeeping — it is the single
   largest lever on prediction accuracy.

---

## Web app

Stdlib `http.server` only — a framework would make reproducing the paper require more
than the paper does. Endpoints: `/api/stations`, `/api/plan`, `/api/track`, `/api/ics`.
`WEB_OBJECT_LIMIT = 140` keeps planning interactive (the full 635-object catalogue
takes minutes). UI views: Overview, Planner, Passes, Weather, Schedule, plus Analysis /
Experiments research pages and a live countdown mode. React 19 + TypeScript 5 + Vite 7.

**Deployment:** Vercel. `vercel.json` builds `webapp/ui` to `dist` and rewrites
`/api/*` → `api/index.py` (a serverless wrapper importing `webapp.server`). There is an
`origin/vercel` branch. Renaming the default branch briefly breaks the deploy hook.

---

## The papers

Only `final_paper/` remains. Both folders are self-contained and upload-ready (zip
the folder's *contents*; compile with pdfLaTeX).

| | `final_paper/ieee/` | `final_paper/springer/` |
|---|---|---|
| Target | IEEE conference (venue not chosen) | SN Computer Science (Springer Nature) |
| Format | IEEEtran conference, 2-col | `sn-jnl`, 1-col, `sn-mathphys-num` |
| Length | **6 pages** (hard limit, full to the last line) | **about 18 pages** (authors' limit, raised from 15 for v2; journal has none) |
| References | 30 (same five ML swaps as Springer) | 30, incl. foundational SGP4 sources, four 2026 papers, SCORE and WSISEG; DOIs where they exist |
| Figures | colour TikZ architecture + 4 charts + ML results table | 13 figures (15 panels): five colour TikZ diagrams + charts |
| Title | SkyPass: Exact Weather-Aware Pass Scheduling with Learned Sky and Brightness Models | SkyPass: A Machine Learning and Exact Optimisation Framework for Weather-Aware Satellite Pass Scheduling at Small Ground Stations |

- Springer allows **one `.tex` file** (no `\input`): macros are inlined, figures flat.
- **Layout is uniform on purpose.** Springer: a preamble override centres one text block on
  every page (sn-jnl hard-codes two-sided mode, so the `oneside` option alone does nothing)
  and the class's `\flushbottom` is left in force: do not add `\raggedbottom` back. Its
  even vertical spacing depends on the preamble block that lowers `\clubpenalty` /
  `\widowpenalty` to 500 (the class's 10000 forced early page breaks that `\flushbottom`
  turned into 60-85 pt gaps above headings), adds `\parskip` stretch and tightens the
  float separations; keep it. Use `\mathbf{1}` for indicators (`\mathbb{1}` has no glyph).
  Springer title page follows the authors' LNCS-style example: Dr. R. Selvakumar first,
  e-mails inside each `\affil` (no `\email`, so no "Corresponding author" line), 10 pt
  `\affilfont`, `\hb` line breaks, `\affilend` eats the class's trailing full stop, and a
  redefined `\abstract` with `\kern-52pt` closes the gap the missing e-mail line leaves.
  IEEE uses `\IEEEaftertitletext{\vspace{-1.2\baselineskip}}` to tighten the title block.
  IEEE:
  `\balance` before the bibliography equalises the last page's columns.
- Prose rules from this file apply. Neither paper uses bold run-in paragraph labels
  (the user asked for them to be removed); the Springer abstract is one unlabelled
  paragraph in Purpose / Methods / Results / Conclusion order, without the word "must".
- Both carry an AI-use statement (Springer: Experimental Setup; IEEE: Acknowledgements)
  that the authors must confirm. The Springer copy has no author-contributions section
  (removed at the user's request).
- `final_paper/reports/` holds the audit: change log (C1-C19, P1-P11, V1-V7), claim
  matrix, citation audit, validation report, compliance checklist, peer review and
  readiness report.
- XeTeX note: local Tectonic builds use XeTeX; the IEEE preamble has a XeTeX-only
  TeX Gyre Termes block because XeTeX cannot load IEEEtran's Times. pdfLaTeX skips it.
- Submitting the same results to IEEE and Springer at the same time would be
  duplicate submission; submit one, or extend substantially for the journal.

---

## Headline validated results (from `results/*.json`)

- Pass extraction: **99.78 %** recall vs a 1 s dense scan, **23.7×** fewer propagator
  calls (54.9 M → 2.31 M); **0.055 s** mean culmination agreement with Skyfield
- Exact DP matched exhaustive search on **100.00 %** of 2,000 random instances;
  100,000 intervals in 285.3 ms. A GA reaches 99.67 % but is 38,922× slower
- Cloud forecast skill: HSS 0.347 (day 1) → 0.289 (day 3) → 0.114 (day 7);
  persistence 0.206
- Weather-aware scheduling: **+37.6 %** clear-sky observations under a window budget,
  **+55.0 %** under a tight budget, but **−0.2 %** under a fixed nightly quota
- TLE ageing: 0.05 s (1 day) → 4.3 s (1 week) → 75.3 s (1 month) culmination error
- Scale: 635 objects × 7 days → 12,438 passes in 104.4 s, scheduling 2.1 ms
- Sky camera (exp 10, WSISEG, blocked 5-fold): cloud-fraction error 27.0 pp (R/B 0.6),
  3.5 pp (tuned R/B), **1.2 pp** (pixel GBM and U-Net); IoU 0.669 / 0.873 / **0.945** /
  0.927. The GBM wins every fold and is the deployed segmenter (no torch needed)
- Brightness (exp 11, SCORE, 17,216 obs, 2,709 sats): unseen-satellite MAE 1.86 (sphere)
  → 1.51 (fitted sphere) → **0.83 mag** (learned); after 2025-07 the learned model ties
  the fitted sphere (2.00 vs 1.99), so the sphere stays the default

**The two findings worth preserving:** a forecast is only worth something when the
planner may *skip a night* (it cannot discriminate within one night, where cloud is
autocorrelated and pass quality varies more); and calibrating the forecast against
reanalysis raises the gain in every regime. Uncalibrated, it is worse than ignoring
weather **under a nightly quota only** (-9.2% EV); under a budget it still helps, less.
Do not restate the unqualified "worse than ignoring weather" form (audit C2).

---

## Known inconsistencies / open items

- **Live-planner gap closed in v2.** `pipeline.plan()` calibrates the forecast by default
  (`weather.site_calibration`, `--no-calibrate` to disable), and the CLI and web app expose
  `--capacity` / `--budget` (`capacity_schedule`, `budget_schedule`).
- **Learned-component limits:** the camera models are trained on one camera (transfer
  untested) and the nowcast's planning value is unmeasured (no public camera archive covers
  the evaluation nights); the brightness model drifts with satellite design, retrain it.
- **Audit corrections (13 Oct 2026)** are in `final_paper/` and must not be undone:
  weather value at **6** stations (skill at 7); raw forecast worse than ignoring weather
  **only under the quota**; epoch-correct geometry **lowers** the half-budget clear gain
  (37.6 -> 33.2%); the funnel's cloud stage is diagnostic; the DP recurrence is
  `OPT[p(j)][k-1]` in 1-based terms; the 37.6% clear-sky gain comes from the
  `skypass-prob` arm. See `final_paper/reports/change_log.md`.
- **Bootstrap done.** `results/exp9_bootstrap.json` reproduces exp 4 exactly. Half budget:
  EV +19.0% [+9.2, +24.9], clear +37.6% [+3.1, +80.4]; quota intervals include zero.
- **v2.0.0 committed and tagged** (21 Oct 2026); it also removed the old `paper/`,
  `overleaf/` and `docs/*.pdf` from the tracked tree.
- Authors still to confirm: AI-use statement, funding and competing interests; ORCIDs.
- A Tata Technologies InnoVent submission package was built **outside this repo** at
  `../SkyPass_Tata_InnoVent_Submission/`. It is deliberately not tracked here.
