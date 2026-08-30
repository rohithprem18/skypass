"""Sanity-check the paper: citation keys, cross-references, undefined macros.

Run before compiling. Catches the mistakes that otherwise surface as silent
"??" marks or bold "?" in the rendered PDF.

Usage:
    python paper/check_refs.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main():
    tex = read(os.path.join(HERE, "skypass.tex"))
    bib = read(os.path.join(HERE, "refs.bib"))

    # Only files the paper actually \input{}s count. Scanning the whole
    # generated/ directory would let a table that is never included still
    # satisfy a \ref{} to its label, hiding a genuinely missing \input.
    gen_dir = os.path.join(HERE, "generated")
    generated = ""
    included = []
    for m in re.findall(r"\\input\{([^}]+)\}", tex):
        p = os.path.join(HERE, m if m.endswith(".tex") else m + ".tex")
        if os.path.exists(p):
            generated += read(p)
            included.append(m)
    orphans = []
    if os.path.isdir(gen_dir):
        inc = {os.path.basename(m).replace(".tex", "") for m in included}
        orphans = sorted(f[:-4] for f in os.listdir(gen_dir)
                         if f.endswith(".tex") and f[:-4] not in inc
                         and f[:-4] != "numbers")
    full = tex + generated

    ok = True

    # --- citations ------------------------------------------------------
    cited = set()
    for m in re.finditer(r"\\cite\{([^}]*)\}", full):
        cited.update(k.strip() for k in m.group(1).split(","))
    defined = set(re.findall(r"@\w+\{([^,]+),", bib))
    missing = sorted(cited - defined)
    unused = sorted(defined - cited)
    print(f"citations: {len(cited)} cited, {len(defined)} defined in refs.bib")
    if missing:
        ok = False
        print(f"  ERROR cited but undefined: {missing}")
    if unused:
        print(f"  note: {len(unused)} unused bib entries (harmless): {unused}")

    # --- cross-references ------------------------------------------------
    refs = set(re.findall(r"\\(?:eq)?ref\{([^}]+)\}", full))
    labels = set(re.findall(r"\\label\{([^}]+)\}", full))
    dangling = sorted(refs - labels)
    print(f"cross-refs: {len(refs)} referenced, {len(labels)} labels")
    if dangling:
        ok = False
        print(f"  ERROR referenced but no label: {dangling}")

    # --- generated macros -------------------------------------------------
    numbers = os.path.join(gen_dir, "numbers.tex")
    if os.path.exists(numbers):
        macros = set(re.findall(r"\\newcommand\{\\(\w+)\}", read(numbers)))
        # Macro uses look like \Foo followed by a non-letter.
        used = set()
        # The negative lookbehind skips the word after a "\\" line break,
        # which is otherwise mistaken for a macro use (e.g. "Satellite\\Transit").
        for m in re.finditer(r"(?<!\\)\\([A-Z][A-Za-z]*)(?![A-Za-z])", tex):
            used.add(m.group(1))
        latex_builtins = {
            "IEEEauthorblockN", "IEEEauthorblockA", "IEEEoverridecommandlockouts",
            "IEEEkeywords", "SI", "BibTeX", "Delta", "Comment", "Require",
            "State", "While", "EndWhile", "If", "ElsIf", "EndIf", "For",
            "EndFor", "OPT", "E", "Bisect", "GoldenMax",
        }
        undefined = sorted(u for u in used - macros - latex_builtins
                           if u[0].isupper() and u not in latex_builtins
                           and not u.startswith("IEEE"))
        # Filter to things that look like our generated macros (CamelCase words)
        undefined = [u for u in undefined if re.fullmatch(r"[A-Z][a-z]+[A-Za-z]*", u)]
        print(f"macros: {len(macros)} generated")
        if undefined:
            ok = False
            print(f"  ERROR used in paper but not generated: {undefined}")
    else:
        print("  note: generated/numbers.tex missing "
              "(run experiments/make_tables.py)")

    # --- figures ----------------------------------------------------------
    figs = set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", full))
    figdir = os.path.join(os.path.dirname(HERE), "figures")
    for f in sorted(figs):
        if not os.path.exists(os.path.join(figdir, f)):
            ok = False
            print(f"  ERROR missing figure: figures/{f}")
    print(f"figures: {len(figs)} referenced")
    if orphans:
        print(f"  note: generated but never \\input: {orphans}")

    # --- inputs -----------------------------------------------------------
    for m in re.findall(r"\\input\{([^}]+)\}", tex):
        p = os.path.join(HERE, m if m.endswith(".tex") else m + ".tex")
        if not os.path.exists(p):
            ok = False
            print(f"  ERROR missing \\input: {m}")

    print("\nOK" if ok else "\nPROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
