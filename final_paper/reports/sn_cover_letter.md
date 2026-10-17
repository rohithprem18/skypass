<!-- Draft cover letter for SN Computer Science. Fill in every [bracket] and
     delete this comment before pasting it into the submission form. -->

[Date]

The Editor-in-Chief
SN Computer Science
Springer Nature

Dear Editor,

We submit the manuscript "SkyPass: Weather-Aware Satellite Pass Scheduling for
Small Ground Stations and the Decision-Dependent Value of Cloud Forecasts" for
consideration as an Original Research article in SN Computer Science.

Small ground stations, such as university laboratories, amateur-radio clubs and
individual observers, plan satellite observations with separate tools for pass
prediction, visibility and weather, and resolve overlapping passes by hand. The
manuscript presents SkyPass, an integrated planner that carries public orbital
elements through SGP4 propagation, pass extraction, visibility scoring and
cloud-forecast calibration to an exact schedule. Conflict resolution is posed as
weighted interval scheduling under a nightly capacity budget and solved by a
dynamic program in O(nK) time after sorting.

The principal contributions are as follows.

1. A pass extractor that agrees with an independent implementation to 0.055 s
   while using 23.7 times fewer propagator evaluations than a dense scan.
2. An exact capacity-constrained scheduler that matched exhaustive search on all
   2,000 randomised instances, where a genetic algorithm of the kind common in
   the satellite-tasking literature reached 99.67% of the optimum at a far
   higher cost.
3. A retrospective evaluation against ERA5 reanalysis at six stations over
   60 nights, showing that the value of a cloud forecast depends on the decision
   it informs: it yields no benefit under a fixed nightly quota, but raises
   clear-sky observations by 37.6% when the station may choose its observing
   nights, and calibration against reanalysis raises the gain in every regime.

The work falls within the journal's scope in algorithms and data structures,
combinatorial optimisation, and modelling and simulation, and it is written for a
general computer-science readership. All code, archived element sets and raw
experiment outputs are openly available at
https://github.com/rohithprem18/skypass [add the Zenodo DOI if archived].

We confirm that this manuscript has not been published elsewhere and is not
under consideration by another journal or conference. Both authors have approved
the manuscript and agree to its submission. [An earlier form of this work was
described in an undergraduate project report (Project Work Phase 1, 19AI701,
Saveetha Engineering College), which has not been published.] The authors
declare no competing interests, and no funding was received for this study. The
use of a generative AI assistant is described in the Experimental Setup section,
as the journal's policy requires.

[Optional: We suggest the following independent reviewers: Name, institution,
institutional e-mail; Name, institution, institutional e-mail.]

Thank you for considering our manuscript. We look forward to your response.

Yours sincerely,

Rohith Prem S (corresponding author)
Department of Computer Science and Engineering
Saveetha Engineering College, Chennai 602105, Tamil Nadu, India
rohithprem91@gmail.com
[ORCID]

on behalf of the authors, Rohith Prem S and Dr. R. Selvakumar
