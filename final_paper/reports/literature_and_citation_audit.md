# Literature and citation audit

## 1. Bibliographic verification

All 30 entries of the IEEE bibliography (`final_paper/ieee/refs.bib`) were
checked; the 17 Springer entries are a subset. Each entry with a DOI was resolved
against the Crossref API (DataCite as fallback) on 13 Oct 2026 and its title,
year and first author compared with the BibTeX record.

| Result | Count | Entries |
|---|---|---|
| DOI resolves; title, year and first author match | 24 | all DOI-bearing entries |
| Apparent year mismatch, resolved as correct | 2 | `curzi2021tle` (online 2021, print vol. 14 2022), `lawler2022visibility` (online Dec 2021, print vol. 163 2022). The BibTeX uses the print year, which is the conventional choice. |
| Apparent author mismatch, resolved as correct | 1 | `kovar2022tle`: the script misparsed the LaTeX accents in "Kovář"; Crossref confirms Kovář, 2022. |
| No DOI (expected) | 5 | `vallado2022fundamentals` (book), `cormen2022introduction` (book), `celestrak` (web service), `skyfield` (software), `mccants` (data set) |
| No DOI (preprint) | 1 | `mallama2021starlink` (arXiv 2101.00374, IEEE only). An arXiv DOI exists (10.48550/arXiv.2101.00374); the preprint has not been confirmed as peer-reviewed. |

No reference was invented, and none was added during this audit. The raw
verification output is reproducible with the script recorded in the change log
session (Crossref `api.crossref.org/works/<doi>`).

## 2. Citation-to-claim support

| Citation | Claim it is attached to | Assessment |
|---|---|---|
| `vallado2022fundamentals`, `acciarini2025sgp4` | SGP4 is the standard basis for rapid prediction | Supported. |
| `kovar2022tle` | TLE error grows with age, measured against on-board GPS | Supported (1U CubeSat with GPS receiver). |
| `curzi2021tle` (IEEE) | Errors estimated statistically | Supported (uncertainty estimation with RNNs). |
| `fankhauser2023brightness` | Diffuse-sphere phase function for apparent magnitude | Supported. |
| `mallama2021starlink`, `lawler2022visibility` (IEEE) | Megaconstellation brightness work refines visibility models | Supported, but `mallama2021starlink` is a preprint. |
| `li2023srsp` | Range scheduling is an oversubscribed combinatorial problem | Supported (review). |
| `ou2023drl`, `petelin2021ground` | Metaheuristic / RL approaches | Supported. |
| `wang2021agile`, `eddy2021mis` | EO scheduling literature | Supported. |
| `wang2020robust`, `wang2021robust` | Cloud as uncertainty in imaging tasking | Supported, directly. |
| `cormen2022introduction` | Weighted interval scheduling is a textbook dynamic program | **Weakly supported.** CLRS treats the weighted variant as an exercise to the activity-selection problem. The canonical treatment is Kleinberg and Tardos, *Algorithm Design* (2006), Sec. 6.1, already in `paper/refs.bib` as `kleinberg2006algorithm`. Recommended swap for the Springer version (length-neutral); not made because the IEEE version keeps a 2020-and-later reference set. |
| `muir2023interval` (IEEE) | Harder interval-scheduling variants attract exact methods | Supported. |
| `xie2024astrosa`, `zhang2024grris` | Observatories schedule around weather with queue schedulers | Supported. |
| `brown2021met`, `turner2022hrrr` | Forecast verification and value are mature fields | `brown2021met` supports verification; `turner2022hrrr` supports economic value. Adequate. |
| `vannitsem2021postprocessing` | Post-processing is needed before a forecast drives a decision | Supported. |
| `ebert2022rare` | HSS is a chance-corrected categorical score in wide use | Supported. |
| `hersbach2020era5`, `openmeteo`, `celestrak`, `skyfield` | Data and software provenance | Supported. |
| `stuhl2021refraction`, `mccants` (IEEE) | Refraction; standard magnitudes | Supported. |

No citation was found attached to a claim it contradicts.

## 3. Unsupported or weakly supported statements

| Location | Statement | Action |
|---|---|---|
| IEEE related work | "Consumer predictors compute pass times by dense sampling or root-finding, but rarely report or validate the refinement strategy." | Removed (C16): no source. |
| Both, introduction | "To our knowledge none [of the tools] allow the forecast to rank passes or drive a scheduling decision." | Retained with its hedge. Needs a documented tool survey to become a supported claim (see section 4). |
| Both, related work | "To our knowledge this machinery has not been applied to observer-side pass planning." | Retained with its hedge; see section 4. |
| Both, setup | GA "of the type common in the satellite-tasking literature" | Acceptable: the cited scheduling literature uses order-based GAs; a specific citation for the operator set used would strengthen it. |

## 4. Missing literature (recommendations, not added)

Adding references changes page counts, and the reviewers' first question will
be about positioning, so these are listed for the authors to decide.

1. **Foundational SGP4 sources.** The Springer short version cites no
   Spacetrack Report #3 (Hoots and Roehrich, 1980) or Vallado et al. (2006),
   "Revisiting Spacetrack Report #3". Both are in `paper/refs.bib` (`hoots1980spacetrack`, `vallado2006revisiting`). For a journal,
   their absence in an SGP4-based paper is the most likely reviewer remark on
   scholarship.
2. **Weighted interval scheduling.** Kleinberg and Tardos (2006), as above.
3. **Forecast value and decision theory.** The paper's central finding (value
   depends on the decision) is the classic cost-loss framing of forecast value
   (Murphy, 1977; Richardson, 2000). Richardson (2000) is in `paper/refs.bib` as
   `richardson2000skill` and cited by the full paper; Murphy (1977) is not in the
   project bibliography and would have to be added and verified. Neither short
   version cites either. A reviewer from meteorology will expect at least one.
4. **Observer-side tools.** A short, cited comparison with existing predictors
   (e.g. Gpredict, Heavens-Above, N2YO) would turn the "to our knowledge" claims
   into documented ones.
5. **Satellite observation scheduling under cloud for ground telescopes**
   (space situational awareness sensor tasking). This is the closest observer-side
   literature and is not discussed in either version.

## 5. Plagiarism risk

No similarity check was run; none is available in this environment, so no
claim is made that the text is free of overlap. The prose was written for this
project and the related-work section paraphrases rather than quotes. The
journal will run its own similarity check; the authors should also check the
text against their own earlier submissions (course report, hackathon material),
since self-overlap with unpublished reports is usually acceptable but should be
disclosed in the cover letter if the earlier material is public.

## 6. Reference style

* IEEE: `IEEEtran.bst`, numeric, citation-order numbering. Matches IEEE style.
* Springer: `sn-mathphys-num.bst` from the official template, numbers in square
  brackets, consecutive numbering in order of citation, DOIs printed as links.
  This matches the journal's stated citation rules.
