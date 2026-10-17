# SkyPass — project memory

Weather-aware satellite transit planning: turns public orbital elements and public
weather forecasts into a conflict-free, executable night of observations for one
small ground station. Ships as a CLI, a Python library, and a React planning console,
all driven by the same engine. Companion implementation for the papers in `final_paper/`.

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
experiments/      9 validation experiments + figure/table generators + paper checker
tests/            42 deterministic unit tests, no network
results/          Experiment outputs (JSON + console logs) — the papers' only data source
generated/        Result macros (numbers.tex) and tables, built by make_tables.py
figures/          Generated vector figures (PDF tracked; PNG previews gitignored)
final_paper/      The only manuscripts: ieee/ (6 pp), springer/ (12 pp), reports/ (audit)
tle_archive/      Dated element-set archives (tracked on purpose)
cache/            Cached Open-Meteo responses (gitignored, regenerated on demand)
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
python -m pytest tests -q                     # 42 tests, no network

python experiments/expN_*.py                  # regenerate results/*.json
python experiments/make_figures.py            # results → figures/*.pdf
python experiments/make_tables.py             # results → generated/, then updates both final papers
python experiments/check_paper.py             # citations, cross-refs, macros, figures (final_paper/ieee)

python webapp/server.py                       # http://localhost:8000 (serves built UI)
cd webapp/ui && npm ci && npm run build       # React build; npm run dev for Vite on :5173
cd final_paper/ieee && tectonic -X compile skypass.tex        # local build
cd final_paper/springer && tectonic -X compile skypass-sn.tex
```

Useful `plan` flags: `--radio`, `--no-weather`, `--sat ISS,NOAA`, `--mask`, `--gap`,
`--w-elev`, `--lat/--lon/--alt/--name`, `--csv/--json/--ics`, `--limit`.

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

---

## Invariants and traps

1. **Pin `models=era5` on the Open-Meteo archive endpoint.** The default best-match
   series *is* the archived forecast for recent dates, so verifying against it scores
   a forecast against a copy of itself and reports a perfect, meaningless skill of 1.0.
   This bug was actually hit. See `weather.py:161`.
2. **`tle_archive/` is tracked deliberately.** CelesTrak serves only current elements,
   so without the dated archive a past prediction cannot be reproduced. Same reasoning
   for `results/`, `figures/*.pdf` and `generated/`.
3. **Every number in the papers flows through `generated/numbers.tex`** (147 macros).
   Never hand-type a result into the LaTeX; re-run `make_tables.py`, which also copies
   the values into `final_paper/ieee/generated/` and the inlined block of
   `final_paper/springer/skypass-sn.tex`.
4. **Paper figures are copies.** `make_figures.py` writes to `figures/`. The IEEE copy
   uses 5 of them in `final_paper/ieee/figures/` (`--font times`); the Springer copy uses
   `Fig1.pdf`-`Fig3.pdf` flat in its folder (`--font cm --wide 6.0`, renamed). Copy them
   across after regenerating, or the uploads go stale.
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
| Length | **6 pages** (hard limit, full to the last line) | 12 pages (journal has no limit) |
| References | 30 (2020+ set) | 17, DOIs included |
| Figures | 5 + TikZ architecture | `Fig1.pdf` (architecture), `Fig2.pdf`, `Fig3.pdf` |
| Title | SkyPass: Exact Weather-Aware Scheduling of Satellite Passes for Small Ground Stations | SkyPass: Weather-Aware Satellite Pass Scheduling for Small Ground Stations and the Decision-Dependent Value of Cloud Forecasts |

- Springer allows **one `.tex` file** (no `\input`): macros are inlined, figures flat.
- Prose rules from this file apply. Neither paper uses bold run-in paragraph labels
  (the user asked for them to be removed); the Springer abstract is one unlabelled
  paragraph in Purpose / Methods / Results / Conclusion order, without the word "must".
- Both carry an AI-use statement (Springer: Experimental Setup; IEEE: Acknowledgements)
  that the authors must confirm. The Springer copy has no author-contributions section
  (removed at the user's request).
- `final_paper/reports/` holds the audit: change log (C1-C19, P1-P7, V1-V7), claim
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

**The two findings worth preserving:** a forecast is only worth something when the
planner may *skip a night* (it cannot discriminate within one night, where cloud is
autocorrelated and pass quality varies more); and calibrating the forecast against
reanalysis raises the gain in every regime. Uncalibrated, it is worse than ignoring
weather **under a nightly quota only** (-9.2% EV); under a budget it still helps, less.
Do not restate the unqualified "worse than ignoring weather" form (audit C2).

---

## Known inconsistencies / open items

- **The live planner does not calibrate the forecast** (found 13 Oct 2026). `pipeline.plan()`
  and `webapp/server.py` pass the raw Open-Meteo forecast to the score; calibration exists
  only in `experiments/exp4_weather_value.py`. The CLI uses `optimal_schedule` (no K, no
  budget) and the web app a per-night `capacity_schedule`; neither exposes `budget_schedule`.
  The shipped tool therefore runs the configuration the experiments say gains nothing.
  See `memory.md` section 11.
- **Audit corrections (13 Oct 2026)** are in `final_paper/` and must not be undone:
  weather value at **6** stations (skill at 7); raw forecast worse than ignoring weather
  **only under the quota**; epoch-correct geometry **lowers** the half-budget clear gain
  (37.6 -> 33.2%); the funnel's cloud stage is diagnostic; the DP recurrence is
  `OPT[p(j)][k-1]` in 1-based terms; the 37.6% clear-sky gain comes from the
  `skypass-prob` arm. See `final_paper/reports/change_log.md`.
- **Bootstrap done.** `results/exp9_bootstrap.json` reproduces exp 4 exactly. Half budget:
  EV +19.0% [+9.2, +24.9], clear +37.6% [+3.1, +80.4]; quota intervals include zero.
- **Nothing since commit `9a288c4` is committed.** The public repository is behind the
  working tree. Removing `paper/`, `overleaf/` and the old `docs/*.pdf` will show as
  deletions of tracked files in the next commit.
- Authors still to confirm: AI-use statement, funding and competing interests; ORCIDs.
- A Tata Technologies InnoVent submission package was built **outside this repo** at
  `../SkyPass_Tata_InnoVent_Submission/`. It is deliberately not tracked here.
