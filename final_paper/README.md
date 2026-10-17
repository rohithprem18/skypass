# SkyPass: final papers

The only manuscripts in the project: corrected, submission-prepared papers
produced by an evidence audit against `results/*.json` and the code.

| Folder | Format | Pages | References |
|---|---|---|---|
| `ieee/` | IEEEtran conference, 2 columns | 6 | 30 |
| `springer/` | Springer Nature `sn-jnl` (SN Computer Science), 1 column | 12 | 17 |
| `reports/` | Audit deliverables | | |

Earlier versions (the 13-page IEEE and 29-page Springer papers, the uncorrected
short versions, the Overleaf bundle and the Springer template) were moved out of
the project on 15 Oct 2026 to `../SkyPass_old_papers_backup/`.

## Uploading

Each manuscript folder is self-contained. Zip the folder's *contents* (not the
folder) and upload to Overleaf or the journal system; compile with pdfLaTeX.

* `ieee/`: `skypass.tex`, `refs.bib`, `figures/` (5 PDFs, Times lettering),
  `generated/` (result macros and the accuracy table).
* `springer/`: `skypass-sn.tex` (single file, macros inlined as Springer
  requires), `references.bib`, `sn-jnl.cls`, `sn-mathphys-num.bst`,
  `Fig1.pdf`-`Fig3.pdf` (Computer Modern lettering, printed at true size).

The compiled `skypass.pdf` / `skypass-sn.pdf` in each folder are local
(Tectonic/XeTeX) builds for reading; regenerate them on the target system.

## Reports

| File | Contents |
|---|---|
| `research_audit_report.md` | Initial assessment and prioritised weaknesses |
| `claim_evidence_matrix.md` | Every major claim traced to its result file |
| `literature_and_citation_audit.md` | Crossref verification of all references; support and gaps |
| `experimental_validation_report.md` | Tests run, recomputations, bootstrap, reproducibility |
| `springer_compliance_checklist.md` | SN Computer Science requirements (from its guidelines page) and IEEE-wide checks |
| `change_log.md` | Every correction with evidence and status |
| `final_peer_review.md` | Three simulated reviews and their resolution status |
| `submission_readiness_report.md` | Final classification and remaining blockers |

## Regenerating numbers

Every number in both manuscripts is a macro generated from `results/`:

```bash
python experiments/make_tables.py   # builds generated/, then updates both papers
python experiments/check_paper.py   # citations, cross-references, macros, figures (IEEE)
```

`make_tables.py` writes `generated/numbers.tex` and the tables, copies what the
IEEE paper `\input`s into `ieee/generated/`, and replaces the inlined macro block
in `springer/skypass-sn.tex` (Springer forbids `\input`).

Figures: `python experiments/make_figures.py --font times --out <dir>` for IEEE,
`--font cm --wide 6.0 --out <dir>` for Springer (then rename to `FigN.pdf`).
