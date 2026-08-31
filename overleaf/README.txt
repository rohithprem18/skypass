SkyPass — Overleaf bundle
=========================

Everything needed to compile the paper. Nothing here refers to a file outside
this folder, so it can be uploaded as-is.

HOW TO USE
----------
1. Zip this folder (select the contents, not the folder itself, if your zip
   tool nests it).
2. Overleaf → New Project → Upload Project → choose the zip.
3. Overleaf should pick skypass.tex as the main document automatically. If it
   does not: Menu → Main document → skypass.tex.
4. Set the compiler to pdfLaTeX (Menu → Compiler). This is Overleaf's default.
5. Recompile. The bibliography needs two passes; Overleaf handles that itself.

WHAT IS HERE
------------
skypass.tex        The paper. IEEEtran conference class.
refs.bib           39 references, cited numerically.
generated/         numbers.tex plus 14 result tables. These are produced by
                   experiments/make_tables.py in the main repository, so every
                   figure quoted in the text resolves through a macro rather
                   than being typed by hand. Do not edit them directly; re-run
                   the experiments instead.
figures/           The 11 vector figures the paper includes, as PDF.
skypass.pdf        Reference build, for comparing against Overleaf's output.

NOTES
-----
* IEEEtran is part of Overleaf's TeX Live installation, so no .cls file is
  bundled. If your Overleaf project cannot find it, add \usepackage{IEEEtran}
  is NOT the fix — IEEEtran is a document class, and the line at the top of
  skypass.tex is already correct.
* \graphicspath is set to {figures/} in this copy. In the main repository it
  points to ../figures/ instead, because the paper lives one level down there.
  If you copy skypass.tex back into the repository, that line must change back.
* The build emits underfull-box warnings. Those are typographic (LaTeX
  reporting loose spacing in justified columns), not errors, and the original
  build produces the same ones.

VERIFIED
--------
This folder was compiled standalone before delivery: 13 pages, the same page
count and effectively the same file size as the reference build in the main
repository.
