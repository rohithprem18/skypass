# Venue compliance checklist

## Selected venue: SN Computer Science (Springer Nature)

**Why this venue.** The journal's aims and scope (retrieved 13 Oct 2026 from
link.springer.com/journal/42979/aims-and-scope) cover "all the disciplines of
computer science including various inter-disciplinary aspects" and list
*Algorithms and Data Structures*, *Modeling and Simulation* and *Mathematical
Programming and Combinatorial Optimization*. It accepts "Original Research, as
well as relevant hardware and/or software architectures". SkyPass is an applied
algorithms and systems paper (exact interval scheduling, a validated propagation
pipeline, a retrospective evaluation), which fits. It is a broad journal, so the
paper has to be readable by non-specialists in astrodynamics and meteorology.

A narrower alternative with a more expert readership is *Astronomy and
Computing* (Elsevier), which would expect more depth on the observing side; the
choice is the authors'.

**Source of requirements.** The journal's submission guidelines page
(link.springer.com/journal/42979/submission-guidelines), downloaded on
13 Oct 2026. Earlier attempts to read it were blocked; this time it was
reachable, so the items below are checked against the journal's own text,
not against generic Springer defaults.

| Requirement (journal text) | Manuscript status | Result |
|---|---|---|
| Manuscripts with mathematical content may be submitted in LaTeX; the Springer Nature LaTeX template is recommended. | `sn-jnl` class from `Springer_Nature_LaTeX_Template/`, class line and package list copied from the template's `sn-article.tex`. | Met |
| Provide all editable source files. | `skypass-sn.tex`, `references.bib`, `sn-jnl.cls`, `sn-mathphys-num.bst`, `Fig1-3.pdf`. One `.tex` file, no `\input`. | Met |
| Title page: title; author names; affiliations (institution, department, city, state, country); corresponding author with active e-mail. | Present. | Met |
| ORCID of the authors, if available. | Not present. | **Author action**: add `\orcid{}` if the authors have ORCIDs. |
| Structured abstract, 150-250 words, sections Purpose / Methods / Results / Conclusion. | 242 words in that order, but as one unlabelled paragraph: the authors asked for no bold run-in labels. | **Deliberate deviation.** If the editorial office requires the labels, add them back (four words) or enter them in the submission system's structured-abstract fields. |
| 4-6 keywords. | 6. | Met |
| Statements under the heading "Statements and Declarations"; submissions without them are returned as incomplete. | Heading present, with funding, competing interests, ethics/consent, and data and code availability. | Met (V3); content needs author confirmation |
| Competing interests disclosed. | "The authors have no competing interests to declare that are relevant to the content of this article." | **Author confirmation** |
| Funding disclosed (names of funding organisations in full). | "No funding was received for conducting this study." | **Author confirmation** (e.g. any institutional seed grant) |
| Ethics approval / consent: only for human or animal research. | "Not applicable." | Met |
| Author contributions statement recommended (not required). | Removed at the authors' request. | Optional; omitted |
| LLM use is not authorship; use beyond copy-editing should be documented in the Methods. | Draft statement in Experimental Setup (V2). | **Author confirmation of wording and extent** |
| Data transparency: data, materials and code should support the published claims. | Statement corrected to match what the repository actually holds (R1). The public repository is behind the local working tree (see blockers). | **Blocker until pushed** |
| Citations as numbers in square brackets, list numbered consecutively. | `sn-mathphys-num`: [1], [2] ... in order of first citation. | Met |
| Reference list only of published or accepted works. | One web service, one software package (allowed as online documents); no unpublished works in the Springer list. | Met |
| DOIs as full links, if available. | 13 of 17; the 4 without are books, a web service and software. | Met (V4) |
| Journal names abbreviated per ISSN LTWA, or full titles if unsure. | Full titles. | Met (permitted fallback) |
| Tables numbered in Arabic numerals with captions. | 1 table. | Met |
| Figures numbered in Arabic numerals, cited in consecutive order. | Figs. 1-3, first cited in order. | Met |
| Figure files named "Fig" + number. | `Fig1.pdf`, `Fig2.pdf`, `Fig3.pdf`. | Met (V5) |
| Vector graphics with fonts embedded. | PDF figures with embedded Computer Modern font subsets. | Met |
| Lettering legible at final size; no faint lines. | Lettering 6.5-8 pt at print size after regeneration (was about 3 pt). | Met (V6) |
| "To add lettering, it is best to use Helvetica or Arial." | Figures use Computer Modern to match the body, as the authors asked. This is a recommendation, not a rule. | Deliberate deviation |
| Captions identify all elements of the figure. | Budget figure caption now names the value model and the oracle. | Met (V7) |
| Figure lettering contrast at least 4.5:1. | Black and dark grey text on white; bar annotations dark on white. | Met |
| Acknowledgements in a separate section. | `\bmhead{Acknowledgements}` (template position). | Met |
| No length limit stated. | 12 pages. The 10-page target was the authors' own. | Not a journal requirement |

### Items that cannot be checked from here

* The journal's peer-review model (single- or double-blind). If double-blind,
  the repository URL and acknowledgements would identify the authors.
  The guidelines page does not state it.
* Article processing charges under the hybrid model (only relevant for open access).
* Whether the cover letter must disclose the earlier course report or hackathon
  material (recommended: disclose).

## IEEE version: no venue selected

`final_paper/ieee/` is a 6-page IEEEtran conference paper, but no specific IEEE
conference has been named, so only IEEE-wide requirements can be checked.

| Requirement | Status |
|---|---|
| IEEEtran `conference` class, two columns. | Met |
| Abstract 150-250 words, no citations or equations. | 222 words; none. Met |
| Index Terms. | Present. Met |
| IEEE reference style. | `IEEEtran.bst`. Met |
| AI-generated content disclosed in the Acknowledgements, naming the system and sections (IEEE author guidelines on AI-generated text). | Draft statement added. **Author confirmation.** |
| Figures legible at print size. | **Not met.** Three wide figures (Figs. 3, 5 and 6 in the IEEE numbering) were laid out for a two-column span and print at about half scale (lettering about 3.5 pt). Fixing this within 6 pages needs one figure removed or a seventh page; this is an author decision (see readiness report). |
| Page limit. | 6 pages, typical for IEEE conferences. Confirm against the chosen conference. |
| PDF eXpress / font embedding. | Not checked: requires the conference's PDF eXpress ID. |
