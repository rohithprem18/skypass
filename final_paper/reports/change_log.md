# Change log

Every significant correction made while preparing `final_paper/`. The original
manuscripts in `paper/v2/` (IEEE, 6 pages) and `paper/springer/v2/` (Springer,
10 pages) were copied, not edited; all manuscript changes below are in the copies.

Status key: **Verified** means the change was checked against the stored
results or the code and the manuscript recompiled cleanly afterwards.

## Scientific and evidence corrections

| ID | Original issue | Correction | Evidence | Status |
|---|---|---|---|---|
| C1 | Abstract and contributions said the weather claim was evaluated "at seven stations". | Forecast skill: 7 stations. Scheduling value: 6 stations (Svalbard has no optically observable passes in the window, so it cannot be scheduled). Both counts now stated, as generated macros `\SkillStations`, `\EvalStations`. | `results/exp3_forecast.json` has 7 sites; `results/exp4_weather_value.json` has 6. | Verified |
| C2 | "Supplying the raw forecast performs worse than disregarding weather entirely" was stated without qualification (abstract, results heading, conclusion). | Restricted to the regime where it holds. Under the nightly quota the raw forecast loses 9.2% (expected value). Under the half budget it still gains 8.0% and 29.9%, less than the calibrated 19.0% and 37.6%. The finding is now "calibration raises the gain in every regime; uncalibrated, the forecast is worse than ignoring weather under a quota". | `exp4_weather_value.json`, `budget_modes.*.raw_gain_*`. | Verified |
| C3 | "Epoch-correct geometry yields a larger benefit at every budget level ... the figures above are therefore conservative." | False at the headline regime: the half-budget threshold gain falls from 37.6% to 33.2% (expected value unchanged, 19.0%). Text now reports the three regimes where it rises and the one where it falls, and drops the "conservative" conclusion. The same claim in the full paper's table caption (`tab_histtle`) was corrected in the generator. | `exp4_weather_value.json` vs `exp4_weather_value_histtle.json`. | Verified |
| C4 | The visibility funnel presented "forecast sky usable" (cloud < 50%) as an applied stage between "bright enough" and "scheduled". | That count is diagnostic only. The scheduler draws from passes above the score floor; cloud enters the score as a continuous weight. At Bengaluru 25 passes were scheduled although only 19 were "cloud-clear", proving the stages are not nested. Figure stage replaced by "above score floor" (87 at Chennai), text and caption corrected. | `skypass/pipeline.py:190-215`; `exp6_pipeline.json` funnels. | Verified |
| C5 | DP recurrence printed `OPT[p(j)+1][k-1]` while defining p(j) as "the latest pass compatible with j". | In the paper's 1-based reading that is off by one (it would admit an incompatible pass). The `+1` is an artefact of the code's 0-based `p(j)` with a 1-based table. Now: passes indexed 1..n, p(j) = largest i < j compatible with j (0 if none), `OPT[p(j)][k-1]`, base cases stated. The code was already correct. | `skypass/scheduler.py:57-166`. | Verified |
| C6 | Abstract and conclusion quoted only the larger of the two value models (37.6%, threshold). | Both models reported: 19.0% (expected value) and 37.6% (clear-sky count). | `exp4_weather_value.json`, `budget-50pct`. | Verified |
| C7 | "Coarse step P/240, capped at 30 s, so higher orbits are sampled proportionally more cheaply." | Backwards: with the cap, every orbit above about a two-hour period is sampled at 30 s; the adaptation makes *short-period* orbits finer. Now: "P/240 bounded to 5-30 s, so short-period orbits, whose passes are shortest, are sampled most finely". The IEEE text also claimed "without risking missed transits", contradicted by 4 missed passes; removed. | `skypass/passes.py:149-158`; `exp1_accuracy.json` (`missed: 4`). | Verified |
| C8 | Calibrated cloud fraction described as `a + b c_f` with no mention of bounds. | States that the value is clipped to [0, 1], as the code does. | `skypass/weather.py:270`. | Verified |
| C9 | "Reliability curves lie well above the diagonal, with slopes of 0.56 and below; a clear forecast at a monsoon station is followed by heavy cloud." | Two stations exceed 0.56 (range 0.17-0.61); the fitted lines cross the diagonal (above it for clear forecasts, below for cloudy ones); expected cloud after a clear forecast at the monsoon stations is 26-27%, not "heavy". Now reports slope and intercept ranges as generated macros. | `exp4_weather_value.json`, `sites.*.calibration`. | Verified |
| C10 | Element-set ageing reported by mean only. | Errors are heavy-tailed (7-14 d: mean 4.3 s, median 0.70 s; >30 d: mean 75.3 s, median 13.7 s). Medians added; caption says "nearly two orders of magnitude in the mean" (78x, not 100x). | `exp8_tle_age.json`, `by_age`. | Verified |
| C11 | Quota result described as "yields little" / "almost nothing". | The quota gains are slightly negative (-1.5%, -0.2%), so "no benefit". | `exp4_weather_value.json`. | Verified |
| C12 | GA comparison quoted a 38,922x slowdown without the GA's search budget. | GA settings (population 60, 120 generations) stated, and the ratio described as dependent on that budget. | `exp5_scheduling.json`, `part_b_vs_genetic`. | Verified |
| C13 | Weight sensitivity: "falling to 0.70 only at the degenerate endpoints where one term is disabled". | 0.70 already occurs at w_e = 0.9 (both terms active), and duration alone (w_e = 0) gives 0.86. Text now states both. | `exp6_pipeline.json`, `part_b_weight_sensitivity`. | Verified |
| C14 | No statement of uncertainty on the pooled weather gains. | Station-level cluster bootstrap run (experiment 9, reproduces experiment 4 exactly). Half-budget 95% intervals now reported (EV +9.2 to +24.9%, clear +3.1 to +80.4%); quota intervals stated as including zero; method and few-cluster caveat in the Discussion. | `results/exp9_bootstrap.json`. | Verified |
| C15 | "Two independently curated providers (CelesTrak and AMSAT) agree to 0.041 s." | The median difference is exactly 0.00 s: the providers largely redistribute the same upstream element sets, so the agreement is not an independent check. Reworded, median added as a macro. | `exp2_elements.json`, `part_b_provider_divergence`. | Verified |
| C16 | IEEE related work: "Consumer predictors ... rarely report or validate the refinement strategy." | Uncited factual claim; removed. | No source in the bibliography supports it. | Verified |
| C17 | The headline clear-sky gain (37.6%) is produced by a planner variant (`skypass-prob`) that weights passes by a calibrated probability of clear sky, which neither manuscript described; the text presented a single planner using 1 - c-hat. | Method now documented in the calibration subsection: P(c <= theta given c_f) in ten forecast bins, shrunk toward the site base rate with 20 pseudo-observations, fitted on the same pre-window; each value model is paired with the planner that maximises its expectation. | `experiments/exp4_weather_value.py:218, 392-397`; `skypass/weather.py:360-384`. | Verified |
| C18 | "A pass under overcast conditions must score zero." | Calibrated cloud never reaches 1 (e.g. Chennai maximum 0.83), so cloud scales the score down rather than zeroing it. Now: eclipse and bright sky zero the score; expected cloud scales it. | `skypass/weather.py:270`; calibration fits in `exp4_weather_value.json`. | Verified |
| C19 | IEEE: "That bounds disagreement between element sets of the same age" referred to the provider comparison, which C15 showed is not an independent check. | Sentence removed. | Follows from C15. | Verified |

## Reproducibility and integrity corrections

| ID | Original issue | Correction | Evidence | Status |
|---|---|---|---|---|
| R1 | Data statement said the repository releases "the cached weather series". | `cache/` is gitignored (0 files tracked). Statement now says weather series are retrieved from Open-Meteo by the released scripts, and that Space-Track historical element sets require an account and are not redistributed. | `git ls-files cache` returns nothing. | Verified |
| R2 | Number formatting inconsistent ("2\,000" beside "12449"). | Grouping centralised in `make_tables.py` (`group()`, SI rule: thin space from five digits). | Regenerated `numbers.tex`. | Verified |
| R3 | No AI-use disclosure. | Draft statements added: Springer (Methods, per journal policy) and IEEE (Acknowledgements, per IEEE policy). **Wording and extent need author confirmation.** | SN Computer Science submission guidelines; IEEE AI-generated text guidelines. | Needs author |

## Venue compliance changes (Springer copy)

| ID | Change | Source of requirement | Status |
|---|---|---|---|
| V1 | Abstract restructured from Context / Action / Result into the journal's mandated Purpose / Methods / Results / Conclusion (230 words, within 150-250). Content is the same CAR material; no "must". | SN Computer Science submission guidelines, "Abstract". | Verified |
| V2 | AI-use statement placed in the Methods-equivalent section (Experimental Setup). | Guidelines, LLM policy. | Needs author |
| V3 | "Declarations" renamed "Statements and Declarations"; funding and competing-interest wording aligned with the journal's sample statements. | Guidelines, "Statements and Declarations". | Verified |
| V4 | DOIs restored for 13 of 17 references (the other 4 are books, a web service and software without DOIs). They had been stripped earlier to save space. | Guidelines: "always include DOIs as full DOI links". | Verified |
| V5 | Figure files renamed `Fig1.pdf`-`Fig3.pdf`. | Guidelines: "Name your figure files with Fig and the figure number". | Verified |
| V6 | Wide figures regenerated at the 5.15 in text width (lettering 6.5-8 pt at print) and placed at full width; architecture diagram at natural size. Previously printed at 0.41-0.52 scale (about 3 pt lettering). | Guidelines: "lines and lettering ... legible at final size". | Verified |
| V7 | Budget figure caption now names the value model plotted (threshold) and explains the oracle. | Guidelines: "Identify all elements found in the figure in the caption". | Verified |

## Generator changes (shared code, not manuscript prose)

| File | Change |
|---|---|
| `experiments/make_tables.py` | `group()` for thousands separators; `audit_macros()` emitting 20 new macros used by the corrections (station counts, raw-forecast gains, epoch-correct EV and quarter-budget values, calibration slope/intercept ranges, ageing medians, GA settings, weight-sensitivity points, provider median, funnel candidate count); `tab_histtle` caption corrected (C3). |
| `experiments/make_figures.py` | Funnel stage "forecast sky usable" replaced by "above score floor" (C4); `--wide` option to lay wide figures out at their printed width (V6). |
| `paper/generated/` | Regenerated by `make_tables.py` (the sanctioned workflow); values unchanged except formatting and the corrected caption. |

## Presentation changes (authors' request)

| ID | Change | Status |
|---|---|---|
| P1 | All bold run-in paragraph labels removed from both manuscripts (e.g. "**Calibration raises the gain in every regime.**", "**Cloud cover is a coarse proxy.**", "**Catalogue.**"). Each label was folded into ordinary prose: either the following sentence already carried the topic, or the label became the subject of the opening sentence. The AI-use sentence in the Springer copy moved into its own paragraph. | Verified (no `\textbf` labels remain in either body) |
| P2 | Springer abstract is one unlabelled paragraph that keeps the Purpose, Methods, Results, Conclusion order. This departs from the journal's labelled structured-abstract format; see the compliance checklist. | Verified; deviation documented |
| P3 | Springer declarations and acknowledgements use standalone unnumbered headings (Funding, Competing interests, Ethics approval and consent, Data and code availability, Author contributions) instead of bold run-ins. | Verified |
| P4 | O(nK) explained. Abstracts now state it in words (running time grows linearly with the number of candidate passes and the nightly limit); the body explains that the table has one entry per pass and per count up to K, each filled in constant time. | Verified |
| P5 | Small station counts printed as words ("seven", "six") through new generated macros `\SkillStationsWord`, `\EvalStationsWord`. | Verified |
| P6 | Author contributions statement removed from the Springer copy at the authors' request. The journal recommends but does not require it. | Verified |
| P7 | Titles reworked. Old (both): "SkyPass: A Weather-Aware Integrated Satellite Transit Planning and Observation System". "Transit" usually means a satellite crossing the Sun or Moon disc in astronomy, and "integrated system" named no contribution. IEEE: "SkyPass: Exact Weather-Aware Scheduling of Satellite Passes for Small Ground Stations". Springer: "SkyPass: Weather-Aware Satellite Pass Scheduling for Small Ground Stations and the Decision-Dependent Value of Cloud Forecasts" (running head "Weather-Aware Satellite Pass Scheduling"). | Verified |

## Length adjustments (IEEE copy, 6-page limit)

To absorb the corrections without exceeding 6 pages: two short introduction
paragraphs merged; a redundant clause on the GA paragraph and the anecdotal
"this behaviour was observed" sentence removed; the valuation limitation
shortened; the uncited sentence C16 removed. No result or limitation was dropped.
