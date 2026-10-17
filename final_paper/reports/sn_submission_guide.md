# Submitting to SN Computer Science: step-by-step guide

Journal: **SN Computer Science** (Springer Nature), ISSN 2661-8907,
<https://link.springer.com/journal/42979>. Requirements below were read from the
journal's submission guidelines page on 17 Oct 2026.

## 1. Journal facts that affect you

| Item | What the journal says | What it means for SkyPass |
|---|---|---|
| Peer review | Single-blind, at least 2 reviewers | Reviewers see your names. The GitHub link and the acknowledgements can stay in the manuscript. |
| Article type | Original Research (also software architectures, surveys) | Choose **Original Research**. |
| Format | LaTeX accepted for mathematical content; Springer Nature template recommended | `final_paper/springer/` already uses the official `sn-jnl` class. |
| Abstract | Structured, 150-250 words: Purpose, Methods, Results, Conclusion | 249 words, in that order, without labels (your earlier choice). See section 4, item 1. |
| Keywords | 4-6 | 6. |
| Declarations | Heading "Statements and Declarations" required; papers without it are returned as incomplete | Present: Funding, Competing interests, Ethics, Data and code availability. |
| AI use | LLMs cannot be authors; use beyond copy editing must be described in the Methods | Statement is in Experimental Setup. You must confirm it is accurate. |
| Figures | Vector with embedded fonts, named Fig1, Fig2...; lettering ideally 8-12 pt, Helvetica/Arial preferred; no titles inside the artwork | Met after today's fixes, except lettering (7-8.5 pt, Computer Modern). These two are recommendations, not rules. |
| Charges | No page or colour charges; free submission. Open access ("Open Choice") is optional and paid | Choose the **subscription (non-OA) route** and you pay nothing. A third-party listing gives the APC as about EUR 2,590; confirm on Springer's site only if the college will pay. |
| Speed | Median about 41 days to first decision (journal-reported) | Expect 1.5-3 months to a first decision, longer with revisions. |
| Exclusivity | Must not be under consideration anywhere else | **Do not submit the IEEE version anywhere while this is under review.** |

## 2. Before you submit (blockers)

These must be done first. None of them is a writing task.

1. **Push the code.** The paper's Data and code availability statement points to
   `github.com/rohithprem18/skypass` and says it holds "the raw experiment outputs
   behind every reported value". The public repository is still at commit
   `9a288c4` (16 Sep 2026): it has no `final_paper/`, no experiment 9
   (`exp9_bootstrap.py`, `results/exp9_bootstrap.json`) and not the corrected
   generators. A reviewer who opens the link today will not find the evidence.
   Commit and push, then (recommended) make a GitHub release and archive it on
   Zenodo to get a DOI you can add to the data statement.
2. **Both authors approve the final PDF.** Submission implies every author has
   approved it. Send `final_paper/springer/skypass-sn.pdf` to Dr. R. Selvakumar
   and get written (e-mail) approval, including approval of the author order and
   of you as corresponding author.
3. **Confirm the declarations are true:**
   - Funding: "No funding was received for conducting this study." If the
     college gave any grant, seed money or equipment, name it.
   - Competing interests: none.
   - AI statement (Experimental Setup): it says an assistant (Claude, Anthropic)
     helped edit the text and wrote the scripts that build the manuscript. If AI
     also helped write the SkyPass code, the experiments or the figures, say so.
     Under-declaring AI use is the risk here, not over-declaring.
4. **Get ORCID iDs** for both authors (free, <https://orcid.org/register>). The
   journal asks for them; add them to the title page with `\orcid{...}` or enter
   them in the submission form.
5. **Check prior disclosure.** The Project Work report (19AI701) and the Tata
   InnoVent package contain this work. A course report is not prior
   publication, but mention it in the cover letter. If anything was published
   publicly (proceedings, a website), tell the editor.

## 3. Submitting, click by click

1. Open <https://link.springer.com/journal/42979> and click **Submit
   manuscript**. Create a Springer Nature account with your e-mail (an
   institutional address is better than Gmail for credibility; either is
   accepted).
2. Choose article type **Original Research**.
3. **Upload files**, each with the item type the form offers:

   | File (from `final_paper/springer/`) | Item type |
   |---|---|
   | `skypass-sn.tex` | Manuscript / LaTeX source (main document) |
   | `references.bib` | LaTeX supplementary / source file |
   | `sn-jnl.cls`, `sn-mathphys-num.bst` | LaTeX supplementary / source file |
   | `Fig1.pdf`, `Fig2.pdf`, `Fig3.pdf` | Figure |
   | `skypass-sn.pdf` | Manuscript PDF (reference copy), if the system offers it |

   The system builds its own PDF from the LaTeX. **Open the built PDF and check
   every page** before approving. If the build fails, upload the `.bbl` file as
   well (run `tectonic -X compile --keep-intermediates skypass-sn.tex` to get
   it) or contact the editorial office.
4. **Metadata form**
   - Title: *SkyPass: Weather-Aware Satellite Pass Scheduling for Small Ground
     Stations and the Decision-Dependent Value of Cloud Forecasts*
   - Abstract: paste it. If the form has separate Purpose / Methods / Results /
     Conclusion boxes, split it there (the four parts are already in that order).
   - Keywords: satellite pass prediction; SGP4; ground station scheduling;
     interval scheduling; forecast calibration; optical observation
   - Authors: Rohith Prem S (corresponding), Dept. of CSE; R. Selvakumar, Dept. of
     AI and ML; both Saveetha Engineering College, Chennai 602105, Tamil Nadu,
     India. Add ORCIDs.
   - Funding: none. Competing interests: none.
   - Data availability: same text as the manuscript.
5. **Suggested reviewers** (optional but useful). They must be independent of
   you (no shared institution, no joint papers) and you need an institutional
   e-mail for each. Candidates from the paper's own reference list (verify the
   current e-mail on each person's latest paper):
   - Xinwei Wang or Guohua Wu: satellite scheduling under cloud uncertainty
     (refs. 5, 9)
   - Dario Izzo or Giacomo Acciarini: SGP4 and propagation (ref. 2)
   - Stéphane Vannitsem: statistical post-processing of forecasts (ref. 13)
   - Barbara Brown: forecast verification (ref. 12)
6. **Cover letter**: paste `sn_cover_letter.md` after filling in the brackets.
7. **Open access**: choose the standard (subscription) option unless the college
   has agreed to pay the APC.
8. Approve the built PDF and submit. Save the manuscript number from the
   confirmation e-mail.

## 4. Author decisions still open

1. **Structured-abstract labels.** The journal asks for the abstract divided
   into Purpose / Methods / Results / Conclusion. The labels were removed at your
   request; the text follows that order. If the editorial office returns the
   paper for this, adding the four labels would push it to 253 words, so about
   five words must be cut at the same time.
2. **Name format.** You are listed as given name "Rohith Prem", surname "S".
   Indexing services will cite you as "S RP". If you prefer a full surname
   (for example your father's name in place of the initial), change it now:
   names cannot change after acceptance, and the same form should be used in
   every future paper.
3. **Guide's e-mail.** Confirm `selvakumarr@saveetha.ac.in` is correct and
   active; the system will e-mail him to confirm co-authorship.
4. **Shipped tool vs evaluated method.** The paper evaluates a planner that
   calibrates the forecast and uses a window budget. The released CLI and web
   app use the raw forecast and a per-night schedule (`pipeline.plan()`,
   `webapp/server.py`). A reviewer who runs the tool may notice. Either add
   calibration and the budget mode to the tool before pushing, or say in the
   data statement that they currently live in `experiments/exp4_weather_value.py`.

## 5. After submission

- **Screening (1-2 weeks):** ethics and similarity check. The paper has not been
  run through a plagiarism checker here; the college's Turnitin or iThenticate
  access can be used beforehand.
- **Review (about 6 weeks to first decision):** answer every reviewer point in a
  response letter: quote the comment, give your reply, and state where the
  manuscript changed. Keep all numbers flowing from `make_tables.py`.
- **Acceptance:** sign the copyright transfer (subscription route), check the
  proofs within 48 hours, and only correct typesetting errors at that stage.
- **Preprint:** Springer Nature allows a preprint on arXiv; declare it in the
  submission form if you post one.

## 6. What was checked and fixed on 17 Oct 2026

**Verified correct**
- All 147 inlined result macros are identical to `generated/numbers.tex`, which is
  built from `results/*.json`.
- Table 1 matches `results/exp1_accuracy.json` to every digit.
- Funnel counts, Svalbard and per-station claims match `exp6_pipeline.json`;
  ageing figures match the `exp8_tle_age.json` bins; every bootstrap interval
  and the "calibration raises the gain in every regime" claim match
  `exp9_bootstrap.json` (calibrated beats raw at all four budget levels).
- All 13 DOIs resolve on Crossref to the cited title, authors, volume, pages and
  year. Skyfield 1.54 and sgp4 2.27 match the installed versions.
- Compiles with 0 errors, 0 overfull boxes, 0 undefined references; 12 pages;
  17/17 references cited; figures and table cited in order.
- Title page, keywords, declarations heading and AI disclosure placement meet the
  journal's rules.

**Fixed**
- Negative numbers printed with a hyphen ("-1.5%") now print a true minus sign.
  Fixed in `experiments/make_tables.py`, so it persists for both papers.
- Fig. 1 enlarged from 0.53 to 0.72 of the text width; its smallest lettering
  went from about 5 pt to about 6.8 pt.
- Fig. 3: removed the title inside the artwork (the journal asks for titles only
  in captions) and enlarged the bar labels from 6.5 to 7.5 pt.
- Fig. 2: panel (b) title changed from the informal "observations that actually
  worked" to "share of passes under clear sky".
- "certified SGP4 core" changed to "reference SGP4 core" (SGP4 has no
  certification).
- Svalbard claim dated precisely ("in the planned week, 29 August to
  5 September") because the demonstration run extends into September.
- AstroSA reference: "python" now keeps its capital P.
- Stale source comment pointing to the deleted `paper/springer/` removed.

The IEEE copies of the figures were not regenerated; the figure changes affect
only `final_paper/springer/`.
