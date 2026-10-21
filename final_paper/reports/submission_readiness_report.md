# Submission readiness report

Final assessment of `final_paper/springer/` (SN Computer Science) and
`final_paper/ieee/` (IEEE conference, venue not yet chosen) for release v2.0.0
(21 Oct 2026), which adds the learned cloud nowcast and brightness model to both
manuscripts.

## Classification

| Manuscript | Classification |
|---|---|
| Springer, SN Computer Science (18 pp) | **Near submission-ready.** No critical scientific or integrity issue is open. The remaining items are author confirmations and decisions, listed below. |
| IEEE (6 pp) | **Near submission-ready**, subject to choosing a venue and confirming its page limit. |

This is a judgement about correctness and completeness against the evidence and
the verified venue requirements. It is not a prediction of acceptance.

## What the final quality-control pass verified

| Check | Springer | IEEE |
|---|---|---|
| Compiles, 0 errors, 0 undefined references or citations, no `??` | Yes | Yes |
| Every cited key in the bibliography, every entry cited | 30 / 30 | 30 / 30 |
| Every figure cited, figures first cited in numerical order | Yes (13) | Yes (5) |
| No em-dashes, no bold run-in labels | Yes | Yes |
| Every number a generated macro from `results/` | Yes (204, inlined) | Yes (`generated/numbers.tex`); `check_paper.py` OK |
| Abstract length | 247 words | 238 words |
| Abstract, results and conclusion report the same findings | Yes: quota gives nothing; budget gives +19.0% EV and +37.6% clear-sky; calibration raises the gain (point estimates); learned segmentation 1.2 pp cloud-fraction error against 3.5 pp for the tuned ratio rule; learned photometry 0.83 against 1.51 mag for unseen satellites, no gain over time | Same |
| Station counts consistent (7 for skill, 6 for value) | Yes | Yes |
| SCORE acknowledgement and NSF disclaimer verbatim | Yes | Yes |
| Unit tests | 71 passed | |

## Blockers (must be done before submitting)

1. **Confirm the AI-use statements.** Both publishers require disclosure. Draft
   wording is in the Springer Experimental Setup and the IEEE Acknowledgements.
   Confirm it describes how AI was used across the whole project (writing, code,
   experiments, figures, the learned components) and adjust it.
2. **Confirm the declarations.** No funding, no competing interests: only the
   authors can confirm these.

The code blocker of earlier versions is resolved: v2.0.0 is committed and tagged
in the public repository.

## Author decisions (not blocking, but affect review)

| Decision | Options | Recommendation |
|---|---|---|
| Springer length | 18 pages; the journal sets no limit. | Keep. |
| Structured abstract labels | Removed at your request; the journal asks for Purpose / Methods / Results / Conclusion. | Enter the labels in the submission system's abstract fields if prompted. |
| WSISEG data licence | The dataset repository states no licence; it is cited and not redistributed. | If an editor asks, write to the dataset authors for permission. |
| SCORE contact | SCORE's usage notes suggest contacting its team, and considering co-authorship with the observers, for publications that rely substantially on its data. | Your decision; at minimum an e-mail to the SCORE team before submission. |
| Venue | SN Computer Science (broad CS) or Astronomy and Computing (specialist). | SN Computer Science fits; the ML additions strengthen the systems angle. |
| Duplicate submission | The two manuscripts share results. | Submit one, or extend substantially for the journal. |
| ORCID | Add if available. | Add. |

## Remaining evidence gaps (documented, not fixable by editing)

| Gap | Effect on claims |
|---|---|
| One season, six stations | The clear-sky interval at the headline budget is wide (+3.1 to +80.4%). Generalisation is stated as an expectation. |
| Few-cluster bootstrap | Intervals approximate and probably too narrow; stated in both papers. |
| Calibrated vs raw difference not tested | Stated as point estimates. |
| Sky camera: one camera, planning value unmeasured | The segmentation accuracy is measured; its value to the planner and transfer to other cameras are stated as untested. |
| Brightness model drift | Measured (temporal split); the sphere stays the default and the papers say so. |
| Weather cache, Space-Track, SCORE and WSISEG data not redistributed | Reproduction depends on the providers continuing to serve the data; stated in the data statement. |
| No similarity check | The journal will run its own. |

## Files

| Path | Status |
|---|---|
| `final_paper/springer/` | Upload-ready: `skypass-sn.tex`, `references.bib`, `sn-jnl.cls`, `sn-mathphys-num.bst`, `Fig1.pdf`-`Fig13.pdf` |
| `final_paper/ieee/` | Upload-ready: `skypass.tex`, `refs.bib`, `figures/` (4 PDFs), `generated/` |
| `final_paper/reports/` | Audit deliverables; `change_log.md` P11-P13 record the v2 changes |
| `results/exp10_cloudcam.json`, `results/exp11_brightness.json` | New experiment outputs |
