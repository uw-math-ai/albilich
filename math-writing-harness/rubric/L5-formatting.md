# L5 — Formatting & Venue Compliance

Mechanics and submission requirements. **Owner critic:** Pedant (LaTeX + math-typography
hygiene) + Provenance Auditor (venue `[META]`, AI governance). Much of this is parameterized
by a **venue profile**. **Default severity:** `minor` for hygiene; `major`/`blocker` for
hard submission requirements of the chosen venue.

Sources: `AMS-HB`, `AMS-STYLE`, `GOVERNANCE`, `AMS-NOTICES`, `PAK-CLEAR`, `MAURER`, `KLR`,
`MILNE`, `TAO`.

---

## LaTeX hygiene (deterministic) — `AMS-HB`, `PAK-CLEAR`

- `L5-TEX-01` [lint] **Macros defined in the preamble** (`\newcommand`, not `\def`), one
  macro per recurring notation, used for EVERY occurrence (enables global notation changes
  and collision checks — comment out the macro and recompile). autofix: assisted.
  (`PAK-CLEAR` 34, `TAO` 31)
- `L5-TEX-02` [lint] **No author macros in title, author names, section/theorem headings,
  abstract, or references** — these travel without the preamble. autofix: assisted.
  (`AMS-HB` 3, 7)
- `L5-TEX-03` [lint] **No hard-coded font changes; no redefinition of existing commands; no
  manual line/page breaks; unused macros/packages and commented-out text removed.** autofix:
  safe/assisted. (`AMS-HB`)
- `L5-TEX-04` [lint] **Theorem environments via `amsthm`** with deliberate `\theoremstyle`;
  a single coherent numbering scheme (by-section or sequential — consistent, gap-free,
  duplicate-free; cross-references all resolve). Per-type counters that produce "Theorem 1"
  next to "Lemma 1" next to "Definition 1" are the classic trap (`KRANTZ`: "maddening").
  autofix: assisted. (`AMS-HB` 9, `AMS-STYLE` 23, `MILNE`)
- `L5-TEX-05` [tool] **Source compiles cleanly** (all class/style/bib files present, no
  errors, no overfull-margin displays). severity: `major`. autofix: manual. (`AMS-HB`)
- `L5-TEX-06` [lint] **\cite / \ref / \eqref used for every reference** (never hard-coded
  numbers; \eqref for equations → roman "(2.4)"); internal links resolve. autofix: safe.
  (`AMS-HB` 13)

## Enunciation & proof formatting — `AMS-STYLE` Ch. 4

- `L5-ENUN-01` [lint] **Enunciation style matches category:** theorem-style (bold head,
  italic body) for Theorem/Lemma/Proposition/Corollary/Conjecture…; definition-style (bold
  head, roman body) for Definition/Example/Question…; remark-style (italic head, roman
  body) for Remark/Notation/Claim/Case/Step…; proof-style ("Proof." italic head). autofix:
  assisted. (house-style parameterizable)
- `L5-ENUN-02` [lint] **Numbered enunciations are proper nouns:** "Theorem 2.1" spelled out
  and capitalized; abbreviations (Thm., Def.) only inside bracketed citations
  ("[11, Thm. 2.1]"). autofix: safe. (`AMS-STYLE` 27, 51, `KLR` 19)
- `L5-ENUN-03` [lint] **No two unnumbered enunciations of the same category**; attribution
  in lightface roman parens after the heading ("Lemma 2.2 (Hamilton and Burr, [7]).");
  credit theorems at the statement site ("\begin{theorem}[Robinson 1949]"). autofix:
  assisted. (`AMS-STYLE` 28, 31, `POONEN-SPK` 13)
- `L5-ENUN-04` [lint] **Proofs end with a QED box flush right**; proof beginnings/ends are
  unambiguous; no □ covering an unproved claim (cross-listed L1-LOCAL-07). autofix: safe.
  (`AMS-STYLE` 29, `MAURER` 6)
- `L5-ENUN-05` [lint] **A "Claim" with a full proof gets promoted to theorem-style**; code
  algorithms and mathematical algorithms use their separate formats. autofix: assisted.
  (`AMS-STYLE` 30, 32)

## Displays & math typography (deterministic) — `AMS-STYLE` Ch. 13, `MAURER`, `KLR`

- `L5-DISP-01` [lint] **Display what is long, tall, important, or referenced;** no
  display-style fractions inline; no broken in-text expressions that a display would fix;
  cases constructions always displayed; matrices > 2 rows displayed. autofix: assisted.
  (`MAURER` 25, `AMS-STYLE` 135, 140-141)
- `L5-DISP-02` [lint] **Displays break BEFORE operators; operators never end a display
  line; multiline alignment on the verbs** (= ≤ column), conjunctions aligned inside the
  RHS; fences spanning lines keep matching sizes; never break a fraction; in-text math
  breaks AFTER an operator outside fences (dual convention). autofix: assisted.
  (`AMS-STYLE` 153-165, `MAURER` 25)
- `L5-DISP-03` [lint] **Equation numbers: only where referenced (Halmos's label rule —
  "irrelevant labels waste a small part of the reader's attention"), on the venue's side
  (AMS: left), never added to unnumbered displays; letters-as-numbers keep their font.**
  Cross-references in roman parens "(3.2)". autofix: assisted. (`AMS-HB` 11,
  `AMS-STYLE` 144-148, `HALMOS` §16, `MAURER` 26)
- `L5-DISP-04` [lint] **Dots discipline:** \ldots between comma-separated items ("0, …,
  n−1"), \cdots between operators/relations ("x₁ + ⋯ + xₙ"); literal "..." fixed. autofix:
  safe. (`AMS-STYLE` 121-123)
- `L5-DISP-05` [lint] **Fence discipline:** ⟨⟩ never <>; every opener closed; display fences
  sized to contents (but not to swallow scripts); "such that" bar vs absolute-value bar
  disambiguated. autofix: safe/assisted. (`AMS-STYLE` 124-128)
- `L5-DISP-06` [lint] **Operator size/position:** ∑/∏/⋃/⋂ big-form for family-indexed
  collectives, small-form as binary operations (position between operands is the test, not
  the subscript); limits beside in text, above/below in display; Σ-the-letter ≠ ∑-the-sum.
  autofix: assisted. (`AMS-STYLE` 129-133, 112)
- `L5-DISP-07` [lint] **Spacing:** thin space after unfenced function names ("dim V");
  \, between juxtaposed Φ-factors (Pak's Φ(2a+c) Φ(c−2a) example — unspaced products read
  as one symbol); quad/two-quad between coexisting equations and before display-internal
  prepositions ("for i < j"); spacing layers mirror grouping (tight inside parens, wide
  outside). autofix: safe. (`AMS-STYLE` 111, 149-152, `PAK-CLEAR` 36, `MAURER` 22)
- `L5-DISP-08` [lint] **Fractions:** slashed form for simple in-text fractions with
  parenthesized compound numerators/denominators — (y₂−y₁)/(x₂−x₁), brackets outside
  parens; built-up form for anything complicated; prefer n(n+1)(2n+1)/3 over built-up
  inline. autofix: assisted. (`MAURER` 24, `AMS-STYLE` 134-137, `KLR` 47)
- `L5-DISP-09` [lint] **Multiline display semantics:** both-sides format = "same operation
  on both sides"; right-side-only chain = "each expression from the previous"; no comma
  after right-side-only lines; cases lines comma-separated; commutative diagrams may end
  unpunctuated (then the intro text ends with a colon). autofix: assisted. (`MAURER` 27,
  `AMS-STYLE` 119, 138-139, 143)
- `L5-DISP-10` [llm] **Page architecture:** neither solid-prose walls nor symbol hash —
  "break it up, but not too small; use prose, but not too much; intersperse enough displays
  to give the eye a chance to help the brain." Zinsser paragraph discipline: short
  paragraphs, but no midget-paragraph chop. autofix: manual. (`HALMOS` §17, `PAK-CLEAR` 6)

## Top matter & metadata — `AMS-HB`, `AMS-STYLE` Ch. 2

- `L5-META-01` [lint] **Title in venue capitalization** (AMS: sentence case), no math where
  avoidable, no macros/footnotes in it; running-head short title provided; title spelling
  matches body. autofix: assisted. (`AMS-HB` 1-3, `AMS-STYLE` 1-3)
- `L5-META-02` [lint] **Abstract stands alone:** no \cite-by-number (self-contained
  bracketed refs instead), no references to the paper's numbered elements, no numbered
  displays, no custom macros; length within venue budget (~150/300 words or 0.3-0.5
  lines/page). autofix: assisted. (`AMS-HB` 7, `AMS-STYLE` 5-8, `PAK-CLEAR` 10)
- `L5-META-03` [lint] **MSC 2020 codes** (≥1 primary, full codes) + keywords (lowercase,
  comma-separated) where the venue requires. autofix: assisted. (`AMS-HB` 5-6,
  `AMS-STYLE` 9-10)
- `L5-META-04` [lint] **Author block conventions:** spaced initials ("V. A. Sohinger"),
  hyphenated-initial periods ("J.-P. Serre"), serial comma among ≥3 authors; one
  affiliation per author in byline order; grant thanks in footnotes ("The second author was
  partially supported by…", past tense), colleague thanks in Acknowledgments (unnumbered,
  spelled "Acknowledgment(s)"). autofix: assisted. (`AMS-STYLE` 4, 11-14)
- `L5-META-05` [lint] **Heading conventions:** sentence-style caps; section heads no
  terminal period, subsection heads run-in with period; no displays in heads; math in heads
  stays math-font; numbered with arabic numerals; special sections (Acknowledgments,
  References) unnumbered. autofix: safe. (`AMS-STYLE` 16-22)
- `L5-META-06` [lint] **Page numbers on all pages** (drafts included). autofix: safe.
  (`MAURER` 33)

## Figures & tables — `AMS-HB`, `AMS-STYLE`, `PAK-CLEAR`, `LEE`

- `L5-FIG-01` [lint] **Caption above tables, below figures; \label after \caption; callouts
  "Figure 2.1"/"Table 3.2" spelled out; figure placed in the callout's section (same/next
  page); no "above/below" references to floats.** autofix: assisted. (`AMS-HB` 14,
  `AMS-STYLE` 36, 60, 70)
- `L5-FIG-02` [lint] **Figures numbered, referenced, and each explained in the text** — say
  WHAT to look at and WHY it supports the claim; axes labeled with units and scale;
  essential features stated in words (cross-listed L1-LOCAL-13). autofix: manual. (`LEE`
  27-28, `MAURER` 13)
- `L5-FIG-03` [llm] **Figures small and many rather than huge and few** (3-5 cm readable;
  copies-with-increasing-detail for complex pictures; half-page figures → appendix/web).
  Venue formats (EPS/PDF), resolution floors, color-to-grayscale legibility per profile.
  autofix: manual. (`PAK-CLEAR` 37, `AMS-HB` 20)

## References list — `AMS-HB`, `PAK-CLEAR`

- `L5-REF-01` [lint] **One reference style, held consistently** (amsplain/amsalpha or venue
  style); alphabetical by author; concise but findable (abbreviated first names OK; keep
  titles); standard journal abbreviations; arXiv IDs/links for unpublished items; [A+13]
  for ≥5 authors, [Con17+] for unpublished, [Tra15a/b] for same-author-year. autofix:
  assisted. (`PAK-CLEAR` 25, `AMS-HB` 17-18)
- `L5-REF-02` [tool] **Bibliography data accurate enough to match MathSciNet/DOI records**
  (AMS replaces references with MathSciNet-enhanced versions — wrong MR numbers propagate);
  no bloated/inconsistent auto-generated entries; author-name spellings consistent across
  entries. autofix: assisted. (`AMS-HB` 16, `PAK-CLEAR` 25)
- `L5-REF-03` [lint] **Every bibliography entry is cited in the text, and vice versa.**
  autofix: safe (report). (`MILNE`)

## Venue submission requirements (`[META]`, parameterized) — `AMS-NOTICES`, `GOVERNANCE`

- `L5-VENUE-01` [meta] **Anonymization** if double-blind: names, affiliations, identifying
  acknowledgments removed; separate title page. severity: `blocker` when required. autofix:
  assisted.
- `L5-VENUE-02` [meta] **Length cap** respected (e.g., Notices: 8-12pp target/15 hard by
  type; "What is…?": 2-4pp). severity: `major`. autofix: manual. (`AMS-NOTICES` 8-14)
- `L5-VENUE-03` [meta] **Reference budget** respected (Notices: ≤20 by type; ≤5 for "What
  is…?"). severity: `minor`. autofix: manual. (`AMS-NOTICES`)
- `L5-VENUE-04` [meta] **Self-citation discipline** — no excessive/coordinated
  self-citation. severity: `minor`. autofix: manual.
- `L5-VENUE-05` [meta] **Overlap/plagiarism risk** surfaced (venues run iThenticate); no
  verbatim reuse without quotation (cross-listed L1-CITE-07). severity: `major`. autofix:
  manual.
- `L5-VENUE-06` [meta] **Data/code availability** deposited + cited with DOIs where
  applicable. severity: `minor`. autofix: manual.
- `L5-VENUE-07` [meta] **Permissions** for reused copyrighted material (author's
  responsibility; start early). severity: `major`. autofix: manual. (`AMS-HB` 19)
- `L5-VENUE-08` [meta] **Register matches venue:** research-journal register permits
  "recall/it is well known"; general venues (Notices-class) ban them along with unexplained
  jargon; expository venues want example-dense structure. Driven by the venue profile's
  `register` field. severity: `minor`→`major`. (`AMS-NOTICES` 5-6)
- `L5-VENUE-09` [meta] **Review/survey genre gate:** for arXiv CS (and spreading), surveys/
  position papers need prior peer-review acceptance + DOI in metadata; any survey must
  contain substantive discussion of open problems, not an annotated bibliography.
  severity: `blocker` where the policy applies. (`GOVERNANCE` 5, B7)

## AI disclosure & authorship (`[META]`) — `GOVERNANCE`

- `L5-AI-01` [meta] **AI is not listed as author/co-author anywhere** (byline, metadata,
  acknowledgments-as-author). severity: `blocker`. autofix: manual. (`GOVERNANCE` B4)
- `L5-AI-02` [meta] **AI-use disclosure block generated per venue:** system name(s) +
  purpose + where used; placement per venue (arXiv: reported "consistent with subject
  standards for methodology"; IEEE: acknowledgments with sections identified; ACM: tiered
  by volume — appendix with prompts for large use, footnote for small; Wiley/Elsevier:
  submission disclosure; Nature: Methods). Grammar/copy-edit-only use is exempt across all
  venues. severity: `blocker` (must exist for the human gate). autofix: assisted.
  (`GOVERNANCE` 1, 7-12, 17)
- `L5-AI-03` [lint] **Residue-clean** (mirrors L1-CITE-03; run every round): no AI
  self-references, knowledge-cutoff phrases, prompt fragments, placeholder text, chat
  scaffolding, instruction echoes. severity: `blocker`. autofix: **safe** (strip) + re-flag
  for human confirmation. (`GOVERNANCE` B2)
- `L5-AI-04` [meta] **Human-responsibility gate:** a named human confirms verification of
  every claim before any PDF/submission artifact is produced — "full responsibility for all
  its contents, irrespective of how the contents were generated." No silent auto-ship.
  severity: `blocker`. autofix: manual. (`GOVERNANCE` B5)
- `L5-AI-05` [meta] **No generative-AI images** for Springer-family venues (profile flag).
  severity: `blocker` where applicable. (`GOVERNANCE` 15)

## Paper deliverable (final_paper)

Deterministic register checks for the standalone LaTeX article the harness ships
as its `final_paper` artifact (authored under the paper contract). Implemented in
`phase2/writing/linter.py` (`run_paper_lint`); enforced at patch time and in the
scheduler's paper gate.

- `L5-PAPER-01` [lint] **No markdown residue in the LaTeX source:** no markdown
  heading lines (leading `#` + space or `##`), no triple-backtick code fences, no
  `* ` bullets at line start, no `[text](url)` links, no `**bold**` spans —
  outside verbatim environments. severity: `blocker`. autofix: assisted.
- `L5-PAPER-02` [lint] **No internal system register in the main text** (before the
  first `\appendix`): no `art_*` identifiers and no word-boundary occurrences of
  "manifest" (excluding "manifestly"), "ledger", "artifact", "proof-state",
  "verifier report", "writing debt", or "state revision"; these belong only in the
  Run archive paragraph of Appendix A. severity: `blocker`. autofix: assisted.
- `L5-PAPER-03` [lint] **Standalone article structure present:** `\documentclass`,
  `\begin{abstract}`, at least one theorem environment (`\begin{theorem}` or
  `\begin{theorem*}`), `\begin{proof}`, `\appendix`, a bibliography
  (`\begin{thebibliography}` or `\bibliography`), and `\end{document}`.
  severity: `blocker`. autofix: assisted.

---

### Venue profile (config the harness reads)

```yaml
venue: "J. Example Math"
review_model: double_blind        # single_blind | double_blind | open
register: research                # research | expository | general (drives L5-VENUE-08)
length_cap_pages: 30
reference_cap: { research: null, survey: 40, note: 10 }
figure_formats: [pdf, eps]
msc_required: true
anonymize: true
title_case: sentence              # sentence | title
eqnum_side: left
quote_punctuation: logical        # us | logical
allow_iff_wlog: false             # L4-SHORT-01 arbitration
singular_they: true               # L4-USAGE-16 arbitration
semicolons: allow                 # allow | discourage (Pak)
ai_disclosure_location: acknowledgments
ai_images_allowed: false
data_availability_required: true
survey_needs_prior_review: false  # L5-VENUE-09
```

Always **re-fetch the target venue's live author guidelines and AI policy** before final
submission — these change (GOVERNANCE header rule), and the profile is only a cache.
