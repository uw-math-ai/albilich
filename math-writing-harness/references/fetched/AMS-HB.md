# AMS-HB — AMS Author Handbook, Journal Classes edition (fetched 2026-07-08, Nov 2021, 32pp PDF; author-facing checkable rules extracted — pure LaTeX-mechanics chapters (graphics file formats, submission logistics) noted but not itemized)

## Top matter (Ch. 2 §4)
1. **Title capitalization (AMS journals): sentence case** — capitalize only the first word, the first word after a colon, and proper nouns.
2. Provide a short running-head form of the title unless the title is very short: \title[short]{full}.
3. **No author-defined macros in the title. Avoid math in titles** (only Computer Modern / amsfonts+amssymb / mathrsfs survive the production system in titles).
4. Top-matter tags in fixed order (title, author, contrib, address, curraddr, email, urladdr, dedicatory, date, thanks, translator, subjclass, keywords, abstract, maketitle). \subjclass and abstract are REQUIRED.
5. Subject classification: MSC 2020 full codes (two-digit codes insufficient); at least one primary (major topic); secondaries for ancillary results, motivation/origin, intended applications.
6. Keywords: comma-separated, only first word and proper nouns capitalized.
7. **Abstract**: placed before \maketitle in AMS classes; multiple paragraphs and unnumbered display material allowed; suggested cap ≈150 words (short papers) / ≈300 words (long papers); **no author-defined macros, no \cite, no \ref in the abstract** (it must stand alone — it circulates without the paper).

## Document body (Ch. 2 §5)
8. Five heading levels: part, specialsection, section, subsection, subsubsection — use for logical sectioning; tag for maximum web linking (\label/\ref/\cite/\eqref).
9. Theorems: use amsthm styles (plain, definition, remark) via \newtheorem, all declared in the preamble; the LaTeX `theorem` package is incompatible.
10. Displayed equations: break and align per Swanson (Mathematics into Type) pp. 44-48; must not exceed the publication's page width; multi-line displays use amsmath structures.
11. **Equation numbers at the left margin** (AMS default): predictable location, no interference with the QED box. Other numbering styles will be changed in production (risking inadvertent errors).
12. **Roman (upright) type rules**: numbers, punctuation, parentheses/brackets/braces, and label symbols set roman EVEN inside italic theorem statements. Distinguish roman-because-mathematical ("a group of class 2") from roman-because-text (a label, a year). Every mathematical expression, however short, must be coded as math ($…$). Roman text inside theorems: \textup{…}. Operator names: \log, \lim, \DeclareMathOperator for new ones.
13. Cite with \cite (roman, publication-dependent style); equation references with \eqref → "(2.4)" all roman with parentheses.

## Floats & captions (Ch. 2 §6)
14. **Caption above a table, below a figure.** Caption headings ("Table 3.1.", "Figure 7.") are supplied automatically. \label must come AFTER \caption. Reference in text via \ref.
15. AMS classes center table/figure content automatically — \centering is unnecessary; third-party caption packages usually mismatch AMS style.

## References (Ch. 2 §7)
16. Journal references get replaced/enhanced from MathSciNet (amsrefs format) — bibliography data must be accurate enough to match MathSciNet records; incorrect MR numbers propagate incorrect references.
17. BibTeX: amsplain (numeric labels; preferred for articles) or amsalpha (author-year-constructed labels); alphabetical by author; language field for translated titles; author-year (natbib) style ordinarily only for historical papers.
18. Standard journal abbreviations from Abbreviations of Names of Serials (ABMR).

## Permissions (Ch. 2 §8) + graphics (Ch. 3), briefly
19. Author is responsible for obtaining permissions for reproduced material.
20. Graphics: EPS preferred; bitmap resolution floors; fonts in figures compatible with document fonts; multi-part figures labeled; color must satisfy print/grayscale legibility (checkable at L5 only if figures present).
