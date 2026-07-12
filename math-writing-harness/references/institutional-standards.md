# Institutional & Journal Standards — Distilled

Mechanics, submission rules, and audience expectations from societies and publishers.
Paraphrased; see `INDEX.md` for authoritative originals (which you MUST consult for the
exact requirements of any specific target venue — these vary and change).

Legend: **[LINT]** deterministic · **[LLM]** judgment · **[META]** submission/process.

---

## `AMS-HB` / `AMS-STYLE` — AMS Author Handbook & Style Guide

**LaTeX & macros**
- **[LINT] Define macros in the preamble** with `\newcommand` (not `\def`); once defined,
  use the macro for *every* occurrence of that expression.
- **[LINT] Do not use author-defined macros in author names, titles, section/theorem
  headings, or references** — use standard commands only. Don't hard-code font changes;
  use TeX coding (e.g. proper italic/bold commands).
- **[LINT] Remove unused macros/packages and commented-out text** before submission.
- **[LINT] Do not redefine existing LaTeX / AMS-LaTeX / AMS-TeX commands.**
- **[LINT] Do not insert manual line/page breaks** — pages break differently in production.
- Use the AMS `proof` environment and `amsthm` theorem declarations rather than rolling
  your own. A theorem "type" = a `\theoremstyle` + a `\newtheorem`.
- `hyperref` is added by production staff; don't fight it.

**Metadata & front matter**
- **[LINT] Assign MSC codes** (2020 Mathematics Subject Classification) for primary and
  secondary subjects via `\subjclass[2020]`. See `MSC` in INDEX.
- Top-matter (title, authors, abstract, keywords) goes after `\begin{document}` in the
  tagged fields.

**Graphics**
- **[LINT] Graphics must not extend into the margins**; conform to AMS graphics guidelines;
  supply EPS/PDF/TIFF as required (some journals ask you *not* to build figures in LaTeX).

**Theorem-like environments & numbering**
- Three predefined styles: `plain` (italic body, extra space), `definition` (roman body),
  `remark`. Choose deliberately and consistently. → complements the `MILNE` numbering check.

**Permissions & reuse**
- **[META]** Obtain permission for reused copyrighted material; public-domain works still
  get credited. Begin permissions early (AMS advises ≥8 weeks before final submission).

## `AMS-NOTICES` — audience/accessibility (expository & general-audience writing)

For anything aimed beyond a narrow specialty:
- **[LLM] Avoid field-jargon** not standard to the general mathematical community.
- **[LLM] Ban reader-losing phrases:** "Recall that X" and "It is well known that X" signal
  to a reader who has never met X that they're already lost; "Clearly X" / "Obviously X"
  strands the reader if X isn't clear to *them*. → concrete `[LINT]`-able phrase blocklist
  with `[LLM]` context check.
- **[LLM] Start gently for non-specialists**; the first paragraphs sell the story and the
  first pages stay intelligible to a general member.
- **[META] Length/reference targets vary by article type** (feature vs. "What is…?" vs.
  survey) — encode per-venue length and max-reference budgets.

## `WILEY` / `SPRINGER` — representative publisher rules

- **[META] Single- vs. double-anonymized review:** if double-blind, the author must
  **anonymize** the manuscript and all associated files (remove names, affiliations,
  identifying acknowledgments; separate title page).
- **[META] Plagiarism/overlap screening** (e.g. iThenticate/CrossCheck) is run on
  submissions. → the harness should surface overlap risk before submission.
- **[META] Self-citation discipline:** excessive or coordinated self-citation is
  discouraged.
- **[META] Data/artifact availability:** deposit datasets/code in recognized repositories
  where applicable; cite them with DOIs.
- **[META] Source-file hygiene:** submit clean LaTeX source + all class/style/bib files
  needed to compile without errors, plus a PDF for review.
- **[META] Manuscript length caps** and figure-format requirements are venue-specific.

---

### What the harness does with this file

- **Pedant (L4/L5)** runs the `[LINT]` LaTeX-hygiene, macro, numbering, and phrase-blocklist
  checks, and the `AMS-NOTICES` jargon/"recall that"/"clearly" checks when the audience
  contract is "general."
- **Provenance Auditor / Formatting critic (L5)** runs MSC presence, anonymization (if the
  target venue is double-blind), self-citation, and source-hygiene `[META]` checks.
- **Human gate (Stage 5)** collects the `[META]` items that can't be auto-fixed
  (permissions, data deposition, venue length caps) into the audit report as a checklist,
  parameterized by the chosen **target venue profile**.
- **Venue profiles** should be a small config (per journal): review model, length cap,
  reference cap by article type, figure formats, MSC required?, anonymization required?
