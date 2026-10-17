# Research audit report

Initial assessment of SkyPass before correction, with prioritised weaknesses.
Corrections made in response are in `change_log.md`; what remains open is in
`submission_readiness_report.md`.

## 1. What was inspected

| Area | Files |
|---|---|
| Manuscripts | `paper/skypass.tex` (IEEE, 13 pp, 59 refs), `paper/v2/skypass.tex` (IEEE, 6 pp, 30 refs), `paper/springer/skypass-sn.tex` (Springer, 29 pp), `paper/springer/v2/skypass-sn-short.tex` (Springer, 10 pp, 17 refs) |
| Bibliographies | `paper/refs.bib`, `paper/v2/refs.bib`, `paper/springer/v2/references.bib` |
| Results | all 22 tracked files in `results/` (experiments 1-8 and the epoch-correct rerun) |
| Generators | `experiments/make_tables.py`, `experiments/make_figures.py`, `experiments/exp4_weather_value.py`, `experiments/exp9_bootstrap.py` |
| Implementation | `skypass/scheduler.py`, `skypass/passes.py`, `skypass/pipeline.py`, `skypass/scoring.py`, `skypass/weather.py`, `skypass/geometry.py`, `skypass/config.py` |
| Tests | `tests/` (42 tests) |
| Data provenance | `tle_archive/`, `cache/`, git tracking state |

The two short versions were selected as the manuscripts to correct, because
they are the most recent versions the authors asked for (6-page IEEE,
10-page Springer). The full-length versions share the same findings and the
same defects; the generator-level fixes reach them, the prose fixes do not
(see section 6).

## 2. The paper in one paragraph

SkyPass is an observation planner for a small ground station. It propagates
public orbital elements with SGP4, extracts passes with a bracketing and
bisection search, scores each pass with a multiplicative visibility model, folds
in a cloud forecast after calibrating it against ERA5 reanalysis, and resolves
conflicts exactly as weighted interval scheduling with a per-night capacity
(an O(nK) dynamic program). The central empirical claim is that a cloud forecast
improves realised observations only when the station may choose *which nights*
to observe: under a fixed nightly quota it gives nothing, under a window budget
it gives +19.0% (expected value) and +37.6% (clear-sky count) at six stations
over 60 nights.

## 3. Contributions: novel versus standard

| Contribution | Assessment |
|---|---|
| Bracket-and-bisect pass extraction | Standard numerical technique. The contribution is the validation (0.055 s vs Skyfield, 23.7x fewer calls, recall 99.78%), not the method. Should be presented as engineering, which the text mostly does. |
| Exact capacity-constrained interval scheduling | The recurrence is textbook with a cardinality dimension. The useful point is the *observation* that the small-station problem has this structure, so solvers and metaheuristics are unnecessary. Not a new algorithm. |
| Multiplicative visibility score | Design choice with a clear rationale; not novel. |
| Weather-value evaluation | **The real contribution.** The decision-dependence result (quota vs budget), the calibration result and the mechanism (between-night vs within-night cloud variance) are the parts a journal will judge. |
| Integrated, reproducible pipeline | Valuable for practice; reproducibility is weakened by what is not in the public repository (section 5). |

No "first", "novel", "state-of-the-art" or "unique" (as a novelty claim) is
used. The two "to our knowledge" statements are hedged but not documented.

## 4. Prioritised weaknesses found

### Critical (would mislead a reader if left)

1. **Raw-forecast claim overgeneralised (C2).** The abstract said the raw forecast
   is worse than ignoring weather. That holds only under the quota; under the
   budget regime the paper recommends, the raw forecast still helps.
2. **Epoch-correct claim contradicted by its own data (C3).** "Larger at every
   budget level ... the figures are therefore conservative", while the headline
   regime drops from 37.6% to 33.2%. Also in the full paper's table caption.
3. **Station count wrong in the abstract (C1).** Seven claimed, six evaluated.
4. **Funnel misdescribes the pipeline (C4).** The cloud stage is diagnostic, not
   a filter; Bengaluru schedules more passes than pass the "usable sky" stage.
   Relatedly, the scoring section said overcast passes score zero (C18).
5. **Undocumented method behind a headline number (C17).** The 37.6% clear-sky
   gain comes from a second planner variant weighting passes by a calibrated
   clear-sky probability, which the manuscripts did not describe.

### Major (a careful reviewer would raise them)

6. **No uncertainty on the headline result (C14).** Six stations, one season,
   pooled point estimates. A station-level bootstrap existed as code but had
   never completed.
7. **Off-by-one in the printed recurrence (C5).** The code is correct; the
   paper's equation is not, as written.
8. **Calibration described wrongly (C9).** Slopes quoted as "0.56 and below"
   when two exceed it; curves described as lying above the diagonal when they
   cross it.
9. **Provider cross-check is not independent (C15).** Median difference zero.
10. **Data statement overstates what is released (R1).**
11. **Illegible figures in both short versions.** Double-column figures printed
    at 0.4-0.5 scale, about 3 pt lettering, against Springer's explicit
    legibility rule.
12. **Springer non-compliance.** Abstract structure, declarations heading, DOIs
    stripped, figure naming (V1-V5).
13. **Only the larger value model in the abstract (C6).**

### Minor

14. Coarse-step rationale stated backwards (C7); "without risking missed
    transits" contradicted by four missed passes.
15. Ageing errors heavy-tailed but reported by mean only (C10).
16. GA slowdown quoted without the GA's search budget (C12).
17. Weight-sensitivity endpoint claim inaccurate (C13).
18. One uncited factual sentence in IEEE related work (C16).
19. Inconsistent thousands separators (R2).
20. No AI-use disclosure, required by both publishers' policies (R3).

### Verified as correct (no change)

* No calibration leakage: the fit uses the 90 days ending the day before the
  evaluation window, night hours only.
* ERA5 is pinned (`models=era5`), avoiding the self-verification trap.
* The DP implementation is exact and matched brute force on 2000 instances.
* The diffuse-sphere phase function, score constants (60 deg, 480 s) and the
  pass-extraction algorithm match the code.
* The headline budget regime is chosen by a fixed rule, not post hoc.
* All 42 unit tests pass.
* Every number in both manuscripts resolves to a generated macro.

## 5. Evidence gaps

| Gap | Effect |
|---|---|
| `cache/` (weather series) not in the repository | Weather results reproducible only while Open-Meteo serves the same archive. |
| Space-Track historical element sets not redistributed | Ageing (exp 8) and epoch-correct (exp 4b) results need a Space-Track account to reproduce. |
| Public repository behind the working tree | Nothing committed since `9a288c4`; the code a reviewer would download does not contain exp 9, the corrected generators, or these manuscripts. |
| One season (June-August 2026) | Monsoon dominates two stations; seasonal generality untested. |
| No documented tool survey or literature search | The two "to our knowledge" claims stay hedged. |
| No similarity check available | Plagiarism risk cannot be certified. |

## 6. Scope of the corrections

* **Corrected manuscripts:** `final_paper/ieee/` and `final_paper/springer/`.
* **Originals untouched:** `paper/v2/` and `paper/springer/v2/` keep their text.
  `paper/skypass.tex` and `paper/springer/skypass-sn.tex` (full versions) carry
  the same prose defects C1-C3, C5-C7, C9-C13, C15; if they are to be submitted
  anywhere, the same edits are needed.
* **Shared generators changed:** `make_tables.py` and `make_figures.py`, which
  also regenerated `paper/generated/` (values unchanged except formatting and
  the corrected `tab_histtle` caption).
