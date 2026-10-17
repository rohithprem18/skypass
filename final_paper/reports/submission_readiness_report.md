# Submission readiness report

Final assessment of `final_paper/springer/` (SN Computer Science) and
`final_paper/ieee/` (IEEE conference, venue not yet chosen), after the audit,
corrections and a second quality-control pass.

## Classification

| Manuscript | Classification |
|---|---|
| Springer, SN Computer Science (12 pp) | **Near submission-ready.** No critical scientific or integrity issue remains open. The remaining items are limited and listed below; two of them (publishing the code, confirming the AI statement) are blocking but are author actions, not research work. |
| IEEE (6 pp) | **Near submission-ready**, subject to choosing a venue and deciding the figure-legibility trade-off. |

This is a judgement about correctness and completeness against the evidence and
the verified venue requirements. It is not a prediction of acceptance.

## What the final quality-control pass verified

| Check | Springer | IEEE |
|---|---|---|
| Compiles, 0 errors, 0 overfull boxes, 0 undefined references or citations | Yes | Yes |
| Every cited key in the bibliography, every entry cited | 17 / 17 | 30 / 30 |
| Every figure and table cited in text, figures cited in order | Yes | Yes |
| No `??`, no drafting markers, no em-dashes, no bold run-in labels | Yes | Yes |
| Every number a generated macro from `results/` | Yes (147 inlined) | Yes (`generated/numbers.tex`) |
| Abstract, results and conclusion report the same findings | Yes: quota gives nothing; budget gives +19.0% EV and +37.6% clear-sky with intervals; calibration raises the gain (point estimates); raw forecast worse than ignoring weather only under the quota | Same |
| Station counts consistent (7 for skill, 6 for value) | Yes | Yes |
| Limitations stated: one season, six stations, few-cluster bootstrap, cloud as proxy, photometry, LEO-only ageing, single instrument | Yes | Yes (condensed) |

## Blockers (must be done before submitting)

1. **Publish the code that the paper describes.** Nothing has been committed
   since `9a288c4`. The repository linked in the paper does not contain
   experiment 9, its results, the corrected generators, or these manuscripts.
   Commit and push, and preferably archive a tagged release on Zenodo so the
   data statement can cite a DOI. (Not done here: commits and pushes need your
   instruction.)
2. **Confirm the AI-use statements.** Both publishers require disclosure.
   Draft wording is in the Springer Experimental Setup and the IEEE
   Acknowledgements. Confirm it describes how AI was actually used across the
   whole project (writing, code, experiments, figures) and adjust it.
3. **Confirm the declarations.** No funding, no competing interests: only the
   authors can confirm these.

## Author decisions (not blocking, but affect review)

| Decision | Options | Recommendation |
|---|---|---|
| Springer length | 12 pages now. The journal sets no limit. Reaching 10 would need dropping the funnel figure and about 150 words, or shrinking figures back below legible size. | Keep 12. |
| Structured abstract labels | Removed at your request; the journal asks for Purpose / Methods / Results / Conclusion. | Enter the labels in the submission system's abstract fields if prompted. |
| IEEE figure legibility | Figs. 3, 5, 6 print at about 3.5 pt lettering. Fix needs one figure removed or a seventh page. | Drop Fig. 6 (funnel; its numbers are in the text) and regenerate Figs. 3 and 5 at column width. |
| Literature additions | Spacetrack Report #3 and Vallado et al. (2006); one forecast-value reference (Richardson 2000 is already verified in `paper/refs.bib`); Kleinberg and Tardos for interval scheduling. | Add to the Springer version (about half a page). These are the likeliest scholarship remarks from reviewers. |
| Venue | SN Computer Science (broad CS) or Astronomy and Computing (specialist). | SN Computer Science fits the scope; the paper's weight rests on the empirical weather finding. |
| ORCID | Add if available. | Add. |

## Remaining evidence gaps (documented, not fixable by editing)

| Gap | Effect on claims |
|---|---|
| One season, six stations | The clear-sky interval at the headline budget is wide (+3.1 to +80.4%). Generalisation beyond this setting is stated as an expectation, not a result. |
| Few-cluster bootstrap | Intervals approximate and probably too narrow; stated in both papers. |
| Calibrated vs raw difference not tested | Stated as point estimates. |
| Weather cache and Space-Track data not redistributed | Reproduction depends on Open-Meteo continuing to serve the archive and on a Space-Track account; stated in the data statement. |
| No tool survey | The two "to our knowledge" claims stay hedged. |
| No similarity check | Plagiarism risk cannot be certified; the journal will run its own check. |
| 30% clear-sky threshold not varied | Sensitivity of the 37.6% figure to the threshold unknown. |
| Shipped tool differs from the evaluated method | The evaluated planner calibrates the forecast and uses a window budget; the released CLI and web app use the raw forecast with no budget option (`pipeline.plan()`, `webapp/server.py`). The papers describe the evaluated method. Either implement calibration and the budget mode in the tool before release, or state in the paper that they are experiment-side. |

## Files

| Path | Status |
|---|---|
| `final_paper/springer/` | Upload-ready: `skypass-sn.tex`, `references.bib`, `sn-jnl.cls`, `sn-mathphys-num.bst`, `Fig1-3.pdf` |
| `final_paper/ieee/` | Upload-ready: `skypass.tex`, `refs.bib`, `figures/`, `generated/` |
| `final_paper/reports/` | `research_audit_report.md`, `claim_evidence_matrix.md`, `literature_and_citation_audit.md`, `experimental_validation_report.md`, `springer_compliance_checklist.md`, `change_log.md`, `final_peer_review.md`, this report |
| `results/exp9_bootstrap.json`, `results/exp9_console.txt` | New experiment output |
| `experiments/make_tables.py`, `experiments/make_figures.py` | Generator corrections (shared) |
| `paper/`, `paper/v2/`, `paper/springer/` | Prose unchanged; the full-length versions still carry the defects corrected here |
