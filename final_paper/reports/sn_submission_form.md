# SN Computer Science: copy-paste sheet for Editorial Manager (v2 manuscript)

Use with `final_paper/springer/` as currently committed on `main`. Article type:
**Original Research**. Everything below matches the manuscript's title page:
author order, affiliations and the corresponding author must be entered exactly
as listed here.

## 1. Files to upload (20)

Delete any files left in the draft from an earlier attempt (old `Fig1-3`, old
`.tex`) before uploading these.

| File | Item type |
|---|---|
| `skypass-sn.tex` | Manuscript (LaTeX source) |
| `references.bib` | LaTeX supplementary / source file |
| `sn-jnl.cls` | LaTeX supplementary / source file |
| `sn-mathphys-num.bst` | LaTeX supplementary / source file |
| `Fig1.pdf` ... `Fig13.pdf`, including `Fig5a`, `Fig5b`, `Fig8a`, `Fig8b` (15 files) | Figure |
| `skypass-sn.pdf` | Manuscript PDF / reference copy, if offered |

Do not upload `skypass-sn.blg` (a build log).

## 2. Title

SkyPass: A Machine Learning and Exact Optimisation Framework for Weather-Aware
Satellite Pass Scheduling at Small Ground Stations

Running title: Machine Learning and Exact Optimisation for Weather-Aware Scheduling

## 3. Abstract (236 words)

If the form has separate boxes, split at the markers; otherwise paste it as one
paragraph without the markers.

[Purpose] Observation planning at a small ground station is split across
unconnected tools that predict passes, judge visibility and leave cloud and
conflicts to the operator. This work examines whether an integrated planner with
learned components increases the number of passes observed under clear sky.

[Methods] SkyPass carries orbital elements through SGP4 propagation, pass
extraction, visibility scoring, cloud-forecast calibration against reanalysis and
exact conflict resolution by a dynamic program linear in the candidates and the
nightly limit. Two learned components replace hand-built approximations:
segmentation of whole-sky camera images as a sub-hourly cloud nowcast, and
gradient-boosted trees that predict apparent magnitude from pass geometry,
trained on 17,216 measured magnitudes.

[Results] Pass extraction agrees with an independent implementation to 0.055 s
using 23.7× fewer propagator evaluations, and the scheduler matched exhaustive
search on all 2000 instances. Over 60 days, a station required to observe every
night gained nothing from the forecast, whereas one free to choose its nights
raised realised yield by 19.0% (expected value) and 37.6% (clear-sky count), and
calibration raised the gain in every regime. Learned segmentation estimated each
image's cloud fraction to within 1.2 percentage points, against 3.5 for the best
colour-ratio rule, and the learned photometry cut the magnitude error for unseen
satellites from 1.51 to 0.83 mag but did not transfer to a later period with new
designs.

[Conclusion] Forecast value depends on the decision it informs; the learned
components help where their training data match deployment.

## 4. Keywords (6)

satellite pass prediction; ground station scheduling; interval scheduling;
forecast calibration; cloud segmentation; machine learning

## 5. Authors

Enter the authors in this order (the manuscript lists Dr. R. Selvakumar first):

1. Dr. R. Selvakumar. Title: Dr.; given name: R.; family name: Selvakumar;
   position: Associate Professor. selvakumarr@saveetha.ac.in. Department of
   Artificial Intelligence and Machine Learning, Saveetha Engineering College,
   Chennai, Tamil Nadu, India.
2. Rohith Prem S (**corresponding author**; the submitting account). Given name:
   Rohith Prem; family name: S. rohithprem91@gmail.com. Department of Computer
   Science and Engineering, Saveetha Engineering College, Chennai, Tamil Nadu,
   India.

Add ORCID iDs if you have them (optional but recommended).

## 6. Declarations (form questions)

- Funding: No funding was received for conducting this study.
- Competing interests: The authors have no competing interests to declare that
  are relevant to the content of this article.
- Ethics approval / consent: Not applicable; the study involves no human
  participants, human data or animals.
- Data availability: SkyPass is open source under the MIT licence at
  https://github.com/rohithprem18/skypass, with the element sets used and the raw
  experiment outputs behind every reported value. Third-party data (Open-Meteo,
  Space-Track, SCORE, WSISEG) are retrieved from their providers by the released
  scripts and are not redistributed.
- Previously published / under consideration elsewhere: No. Answer "No" only
  while the IEEE version is not under review anywhere; submitting both at once is
  duplicate submission.
- Open access: choose the standard (subscription) route; no fee.

## 7. Cover letter

Dear Editor,

We submit the manuscript "SkyPass: A Machine Learning and Exact Optimisation
Framework for Weather-Aware Satellite Pass Scheduling at Small Ground Stations"
for consideration as an Original Research article in SN Computer Science.

Small ground stations plan satellite observations with separate tools for pass
prediction, visibility and weather, and resolve overlapping passes by hand. The
manuscript presents SkyPass, an integrated planner that carries public orbital
elements through SGP4 propagation, pass extraction, visibility scoring and
cloud-forecast calibration to an exact schedule, with two learned components: a
whole-sky camera cloud nowcast and a satellite brightness model.

The principal contributions are as follows.

1. A pass extractor that agrees with an independent implementation to 0.055 s
   while using 23.7 times fewer propagator evaluations than a dense scan.
2. An exact capacity-constrained scheduler, formulated as weighted interval
   scheduling and solved by dynamic programming, that matched exhaustive search
   on all 2,000 randomised instances.
3. A retrospective evaluation against ERA5 reanalysis showing that the value of a
   cloud forecast depends on the decision it informs: it yields no benefit under
   a fixed nightly quota, but raises clear-sky observations by 37.6% when the
   station may choose its observing nights.
4. Two learned components evaluated against classical baselines: image
   segmentation that estimates cloud fraction to within 1.2 percentage points
   (3.5 for the best colour-ratio rule), and a gradient-boosted magnitude model
   that reduces the error for unseen satellites from 1.51 to 0.83 mag, with its
   failure to transfer to newer satellite designs reported explicitly.

The work falls within the journal's scope in algorithms, combinatorial
optimisation, machine learning, and modelling and simulation. All code and raw
experiment outputs are openly available at https://github.com/rohithprem18/skypass.

We confirm that this manuscript has not been published elsewhere and is not under
consideration by another journal or conference. Both authors have approved the
manuscript and agree to its submission. An earlier form of this work was
described in an undergraduate project report (Project Work Phase 1, 19AI701,
Saveetha Engineering College), which has not been published. The authors declare
no competing interests, and no funding was received for this study. The use of a
generative AI assistant is described in the Experimental Setup section, as the
journal's policy requires.

Thank you for considering our manuscript.

Yours sincerely,

Rohith Prem S (corresponding author)
Department of Computer Science and Engineering
Saveetha Engineering College, Chennai, Tamil Nadu, India
rohithprem91@gmail.com
