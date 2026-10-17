# Simulated peer review

Three independent reviews of the corrected Springer manuscript
(`final_paper/springer/skypass-sn.tex`), followed by the author response.
Section and figure references are to that manuscript; the same points apply to
the IEEE copy unless noted. "Resolved" is used only where the revised text or a
recorded result demonstrates it.

---

## Reviewer 1: domain expert (astrodynamics, observing, forecast verification)

**Summary.** A clear, well-instrumented systems paper. The pass-prediction
validation is solid. The interesting result is the decision-dependence of
forecast value; the paper should lean on it harder and position it against the
forecast-value literature.

### Major concerns

| # | Concern | Location | Evidence | Required correction | Status |
|---|---|---|---|---|---|
| R1.1 | The central finding (forecast value depends on the decision) is the cost-loss framing of forecast value, which the paper does not cite or engage. | Introduction, Related Work, Conclusion | No Murphy (1977) or Richardson (2000) in the 17 references. | Cite and position against cost-loss / economic-value literature. | **Open.** Recommended in the citation audit; adds about 2 references. |
| R1.2 | SGP4 paper without Spacetrack Report #3 or Vallado et al. (2006). | Related Work | Absent from the short version; present in `paper/refs.bib`. | Restore the two foundational references. | **Open.** Author decision (length). |
| R1.3 | The CelesTrak/AMSAT comparison is presented as cross-provider validation. | Sec. 5.2 | Median difference 0.00 s. | State that the providers share upstream sets. | **Resolved** (C15). |
| R1.4 | One season (June to August), two monsoon stations: is the quota result seasonal? | Results, Discussion | Single 60-day window. | Either a second season or a stated limitation. | **Partly resolved:** limitation stated ("one season"); no second season run. |
| R1.5 | Closest observer-side literature (ground-based sensor tasking for space surveillance under weather) is missing. | Related Work | Not discussed. | Add 1-2 references. | **Open.** |

### Minor concerns

| # | Concern | Status |
|---|---|---|
| R1.6 | Ageing errors are heavy-tailed; means alone mislead. | Resolved (C10). |
| R1.7 | Calibration curve description inconsistent with the slopes. | Resolved (C9). |
| R1.8 | The "magnitude gate is an ordering rather than a prediction" caveat is good; give an indication of photometric error. | Open; no photometric validation data in the project. |

---

## Reviewer 2: technical and methodological expert

**Summary.** The engineering is careful (ERA5 pinned, calibration fitted out of
sample, an exact solver validated against brute force). The statistics on the
headline result are thin, and several sentences overstated what the tables show.

### Major concerns

| # | Concern | Location | Evidence | Required correction | Status |
|---|---|---|---|---|---|
| R2.1 | Headline gains are pooled point estimates over six stations with no uncertainty. | Abstract, Sec. 5.4 | No interval reported. | Station-level (cluster) uncertainty. | **Resolved:** cluster bootstrap run; half-budget intervals exclude zero (EV +9.2 to +24.9%, clear +3.1 to +80.4%) and are reported with the few-cluster caveat. A larger station panel would still be needed to narrow the clear-sky interval. |
| R2.2 | "Raw forecast worse than ignoring weather" contradicts the budget results. | Abstract, Sec. 5.4, Conclusion | Raw +8.0% / +29.9% at half budget. | Restrict the claim to the quota. | **Resolved** (C2). |
| R2.3 | "Epoch-correct geometry larger at every budget level" contradicted at the half budget. | Sec. 5.4 | 37.6% to 33.2%. | Report all four regimes; drop "conservative". | **Resolved** (C3). |
| R2.4 | Recurrence `OPT[p(j)+1][k-1]` off by one in the stated indexing. | Eq. (4) | `scheduler.py` uses 0-based p(j). | Restate. | **Resolved** (C5). |
| R2.5 | Funnel implies cloud is a hard stage; the code weights it. | Sec. 5.6, Fig. 3 | Bengaluru: 25 scheduled, 19 cloud-clear. | Correct the figure and text. | **Resolved** (C4). |
| R2.6 | GA comparison: the slowdown is a function of the GA's budget. | Sec. 5.5 | Population 60, 120 generations. | State settings. | **Resolved** (C12). |
| R2.13 | The clear-sky headline comes from a planner variant not described in the Methods. | Sec. 3.3, 5.4 | `exp4_weather_value.py:395-397` | Describe the clear-probability planner. | **Resolved** (C17). |
| R2.7 | Is the 50% budget the regime chosen because it looks best? | Sec. 5.4 | Generator uses a fixed preference order. | State the choice rule. | **Resolved** (Springer): the text now says the central budget level is the headline and Fig. 2 shows all four regimes; the generator's fixed choice rule was verified. IEEE shows all four in its figure. |

### Minor concerns

| # | Concern | Status |
|---|---|---|
| R2.8 | Calibrated value bounds not stated. | Resolved (C8). |
| R2.9 | Coarse-step rationale backwards. | Resolved (C7). |
| R2.10 | Weight-sensitivity claim imprecise. | Resolved (C13). |
| R2.11 | Evaluation uses a 300-object subset, not the 635-object catalogue. | Resolved: now stated. |
| R2.12 | Threshold model uses a hard 30% cut; sensitivity to it is not shown. | Open. The full paper's data do not include a threshold sweep. |

---

## Reviewer 3: critical publication reviewer (clarity, ethics, venue fit)

**Summary.** Readable, well structured, honest about limitations. Several
compliance and transparency items were missing.

### Major concerns

| # | Concern | Location | Evidence | Required correction | Status |
|---|---|---|---|---|---|
| R3.1 | Abstract does not follow the journal's Purpose / Methods / Results / Conclusion structure. | Abstract | Journal guidelines. | Restructure. | **Partly resolved:** content follows the four-part order; labels omitted at the authors' request (P2). |
| R3.2 | Figures illegible at print size. | Figs. 2, 3 | About 3 pt lettering. | Regenerate at print width. | **Resolved** for Springer (V6). **Open** for IEEE (page limit). |
| R3.3 | Data statement claims weather series are released; they are not. | Declarations | `cache/` untracked. | Correct the statement. | **Resolved** (R1). |
| R3.4 | The code link leads to a repository that does not contain the code described. | Declarations | Nothing committed since `9a288c4`. | Commit, push, and preferably archive a tagged release with a DOI (e.g. Zenodo). | **Open: blocker.** |
| R3.5 | No disclosure of generative-AI use. | Methods | Journal LLM policy. | Add a statement. | **Draft added; author confirmation required** (R3/V2). |

### Minor concerns

| # | Concern | Status |
|---|---|---|
| R3.6 | "Declarations" heading should be "Statements and Declarations". | Resolved (V3). |
| R3.7 | DOIs missing from references. | Resolved (V4). |
| R3.8 | ORCIDs absent. | Open (author information). |
| R3.9 | Generalisation in the conclusion goes beyond one setting. | Resolved (softened). |
| R3.10 | Peer-review model unknown: if double-blind, the GitHub URL de-anonymises. | Open (check at submission). |

---

## Author response summary

Resolved in the revised manuscripts: R1.3, R1.6, R1.7, R2.1-R2.11, R2.13,
R3.2 (Springer), R3.3, R3.6, R3.7, R3.9.

Partly resolved: R1.4 (limitation stated, no second season), R3.1 (abstract
unlabelled by request).

Open, needing author action or new work: R1.1, R1.2, R1.5 (literature additions,
which change page count), R1.8, R2.12 (would need new experiments), R3.2 for
IEEE (page-limit trade-off), R3.4 (publish the code), R3.5 (confirm AI
statement), R3.8, R3.10.

### Remaining rejection risks, most serious first

1. **R3.4** An editor or reviewer following the code link to a repository that
   does not match the paper is a credibility problem for a reproducibility-led
   paper.
2. **R2.1, residual.** The half-budget clear-sky interval (+3.1 to +80.4%) is
   positive but wide, from six stations; a reviewer may ask for more stations
   or a second season before accepting the 37.6% figure. The expected-value
   gain (+9.2 to +24.9%) is the firmer number.
3. **R1.1** Missing the forecast-value literature makes the main finding look
   unaware of prior framing.
4. **Venue fit.** SN Computer Science is broad; reviewers may be algorithms
   specialists who see the scheduling contribution as textbook. The paper's
   weight has to rest on the empirical weather finding, which the abstract now
   foregrounds.
