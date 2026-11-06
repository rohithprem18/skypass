# SkyPass: final papers

The only manuscripts in the project: corrected, submission-prepared papers
produced by an evidence audit against `results/*.json` and the code.

| Folder | Format | Pages | References |
|---|---|---|---|
| `ieee/` | IEEEtran conference, 2 columns | 6 | 30 |
| `springer/` | Springer Nature `sn-jnl` (SN Computer Science), 1 column | 18 | 30 |
| `springer_v2/` | Springer LNCS conference layout (`llncs`), 155 x 235 mm page | 18 | 30 |
| `reports/` | Audit deliverables | | |

Earlier versions (the 13-page IEEE and 29-page Springer papers, the uncorrected
short versions, the Overleaf bundle and the Springer template) were moved out of
the project on 15 Oct 2026 to `../SkyPass_old_papers_backup/`.

## Uploading

Each manuscript folder is self-contained. Zip the folder's *contents* (not the
folder) and upload to Overleaf or the journal system; compile with pdfLaTeX.

* `ieee/`: `skypass.tex`, `refs.bib`, `figures/` (4 PDFs, Times lettering; the
  architecture diagram is inline TikZ), `generated/` (result macros and the
  accuracy table).
* `springer/`: `skypass-sn.tex` (single file, macros inlined as Springer
  requires), `references.bib`, `sn-jnl.cls`, `sn-mathphys-num.bst`,
  `Fig1.pdf`-`Fig13.pdf` (Computer Modern lettering; Fig1-4 and Fig7 are colour
  TikZ diagrams from `experiments/diagrams/`).

* `springer_v2/`: `skypass-lncs.tex`, `references.bib`, `llncs.cls`,
  `splncs04-cited.bst` (the Springer style with sorting removed, so references
  are numbered by first citation), `Fig1.pdf`-`Fig13.pdf`. Same text and numbers
  as `springer/`, in the layout of the authors' LNCS reference paper. It suits a
  Springer conference; SN Computer Science itself needs `springer/`.

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

Figures: `python experiments/make_figures.py --font times --wide 3.45 --out <dir>` for IEEE
(compact single-column charts),
`--font cm --wide 5.15 --col 2.5 --uniform 7 --out <dir>` for Springer (then rename to
`FigN.pdf`; `--wide 4.8 --col 2.35 --uniform 6.5` for `springer_v2/`).
