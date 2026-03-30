# Nabaztag Paper

This directory contains a first scientific paper draft accompanying the Nabaztag project.

Files:

- `paper.md`: main manuscript draft in academic Markdown
- `main.tex`: LaTeX manuscript draft
- `references.bib`: bibliography starter file

Suggested next steps before submission:

1. add authors, affiliations, and acknowledgements
2. align the text with a target venue format
3. add references and prior work citations
4. add figures for architecture, rabbit interface, and interaction flow
5. add a short evaluation protocol or field study section if empirical results become available

## Build

Example build sequence with `latexmk`:

```bash
cd nabaztag-paper
latexmk -pdf main.tex
```

If the target venue uses another class file, keep `paper.md` as the editable source draft and adapt `main.tex` accordingly.
