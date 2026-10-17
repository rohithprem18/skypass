# Claim-to-evidence matrix

Every quantitative claim in both final manuscripts resolves to a macro generated
by `experiments/make_tables.py` from `results/*.json`. For the claims below the
raw JSON value was read independently and compared with the macro and with how
the prose describes it.

Status: **Supported** (number and wording match the evidence), **Corrected**
(number right, wording overreached; fixed, see `change_log.md`), **Qualified**
(supported, but with a limitation now stated), **Unverified** (no evidence in
the project can confirm it).

## Pass prediction

| Claim | Value | Source | Status |
|---|---|---|---|
| Mean culmination agreement with Skyfield | 0.055 s (n = 1761) | `exp1_accuracy.json` `part_b_skyfield.d_tca_s.mean` = 0.0546 | Supported |
| Fewer propagator calls than a 1 s dense scan | 23.7x (2,311,148 vs 54,864,000) | `part_a_dense_reference.call_reduction` | Supported |
| Detection recall vs dense scan | 99.78% (4 missed, 3 spurious, 37 clipped excluded) | `part_a_dense_reference.recall` | Supported |
| Dense-scan "deviation" is the grid's own lag | mean 0.50 s on AOS/LOS, consistent with a 1 s grid | `part_a_dense_reference.d_aos_s` | Supported (argument, not separately measured) |
| Coarse step makes high orbits proportionally cheaper | n/a | `skypass/passes.py:158` | Corrected (C7) |
| "Without risking missed transits" (IEEE) | 4 passes missed | `part_a_dense_reference.missed` | Corrected (C7) |

## Element sets

| Claim | Value | Source | Status |
|---|---|---|---|
| Median catalogue element age | 0.42 d; 90.2% under one day | `exp2_elements.json` | Supported |
| CelesTrak and AMSAT agree as "independent" providers | mean 0.041 s, **median 0.00 s** (308 passes) | `part_b_provider_divergence.d_tca_s` | Corrected (C15) |
| Ageing error, 0-1 d | mean 0.05 s, median 0.01 s (n = 592) | `exp8_tle_age.json` `by_age` | Supported |
| Ageing error, 7-14 d | mean 4.3 s, median 0.70 s (n = 4590) | same | Qualified (C10) |
| Ageing error, beyond a month | mean 75.3 s, median 13.7 s (n = 16039; history 60 d) | same | Qualified (C10) |
| 33,223 aged comparisons over 60 objects | 33,223 | `n_comparisons` | Supported |
| 5-7 day staleness cutoff suits timing work | mean 0.47 s at 5-7 d vs 4.3 s at 7-14 d | same | Supported (design judgement) |

## Forecast skill

| Claim | Value | Source | Status |
|---|---|---|---|
| Verified at seven stations over 60 days | 7 sites, 2026-06-25..08-23 | `exp3_forecast.json` | Supported |
| HSS by lead: 1 d / 3 d / 7 d | 0.347 / 0.289 / 0.114 (n = 10,080 each) | `pooled` | Supported |
| Beats persistence at 1 d, not at 5-7 d | persistence 0.206; HSS 0.145 at 5 d | `pooled_baselines` | Supported |
| Clear-hour threshold | 30% | `clear_threshold` | Supported |

## Weather-aware scheduling value

| Claim | Value | Source | Status |
|---|---|---|---|
| Evaluated at seven stations | **6** stations | `exp4_weather_value.json` `sites` | Corrected (C1) |
| Candidate catalogue for the evaluation | 300 objects | `n_objects` | Supported (now stated) |
| Quota: no benefit | EV -1.5%, clear -0.2%; oracle 12.0% / 31.6% | `budget_modes.nightly-quota` | Corrected wording (C11) |
| Half budget gain | EV +19.0% (`skypass` arm), clear +37.6% (`skypass-prob` arm) | `budget_modes.budget-50pct`; arm mapping in `exp4_weather_value.py:395-397` | Supported; both now reported (C6); second arm now documented (C17) |
| Headline regime not chosen post hoc | fixed preference order 50% > 25% > 75% in generator | `make_tables.py` | Supported |
| Quarter budget clear-sky gain | +55.0% | `budget-25pct` | Supported |
| Clear-sky share rises | 13.9% -> 23.1% | `success_rate_*` | Supported |
| Raw forecast worse than ignoring weather | -9.2% EV under quota only; **+8.0% EV, +29.9% clear** under half budget | `raw_gain_*` | Corrected (C2) |
| Epoch-correct geometry larger "at every budget level" | quota -0.2 -> +9.2; 75% 17.7 -> 19.9; **50% 37.6 -> 33.2**; 25% 55.0 -> 75.9 | `exp4_weather_value_histtle.json` | Corrected (C3) |
| Calibration slopes "0.56 and below" | 0.17-0.61 | `sites.*.calibration.slope` | Corrected (C9) |
| No calibration leakage | fit on 90 d ending the day before the window | `experiments/exp4_weather_value.py:322-330` | Supported |
| ERA5 pinned as truth | `models=era5` | `skypass/weather.py:161-173` | Supported |
| Within-night structure | between/within cloud SD 2.2x; p90 pass 1.8x mean; r = 0.41 | `exp7_structure.json` | Supported |
| Uncertainty on the pooled gains | half budget: EV [+9.2, +24.9]%, clear [+3.1, +80.4]%; quota: both include zero | `exp9_bootstrap.json` (drift 0.000 pp) | Supported, with few-cluster caveat |
| "Calibration raises the gain in every regime" | true for every point estimate; intervals of calibrated and raw overlap; difference not bootstrapped | `exp9_bootstrap.json` | Qualified (stated as point estimates) |

## Scheduling

| Claim | Value | Source | Status |
|---|---|---|---|
| DP matches exhaustive search | 100.00% of 2000 instances | `exp5_scheduling.json` | Supported |
| Greedy by score | 99.95% mean | `heuristics.greedy-highest-value` | Supported |
| Greedy by elevation | 95.39% mean, optimal in 62.7%, worst 9.4% | `heuristics.greedy-max-elevation` | Supported |
| GA quality and cost | 99.67% of optimum, 38,922x slower (mean over 6 sites) | `part_b_vs_genetic` | Qualified (C12) |
| 100,000 candidates in 285.3 ms | 0.2853 s | `part_c_scaling` | Supported |
| Recurrence as printed | off by one in 1-based reading | `skypass/scheduler.py` | Corrected (C5) |

## End-to-end

| Claim | Value | Source | Status |
|---|---|---|---|
| Chennai funnel | 12,449 -> 8,093 -> 1,297 -> 367 -> 87 -> 26 | `exp6_pipeline.json` | Corrected stage (C4) |
| Svalbard: most geometric passes, zero observable | 38,674 geometric, 0 dark | same | Supported |
| 635 objects x 7 days in 109.4 s | 109.4 s | `part_a_optical.chennai.runtime` | Supported |
| Weight stability | Jaccard 0.93 / 0.89 at w_e 0.3 / 0.7; 0.70 at 0.9; 0.86 at 0 | `part_b_weight_sensitivity` | Corrected (C13) |

## Claims that cannot be verified from the project

| Claim | Why unverified | Evidence needed |
|---|---|---|
| "To our knowledge, no tool lets the forecast rank passes or drive a scheduling decision." | No systematic survey of pass-prediction tools exists in the project. | A documented comparison of named tools (e.g. Heavens-Above, Gpredict, N2YO, ISS Detector) and their features. |
| "To our knowledge this machinery has not been applied to observer-side pass planning." | Hedged appropriately, but no literature search log exists. | A recorded search (databases, query strings, dates). |
| Generality: "Both findings generalise to any small facility allocating scarce effort under uncertain sky." | One season, six stations, one instrument model. | Additional seasons or a different facility type. |
