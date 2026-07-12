# Anti-Pattern Catalogs — Inverted into Critic Checks

These sources describe how to write *badly* (Milne, Serre) or how to spot a *bogus* result
(Aaronson). Each anti-pattern below is stated as the bad behavior, then inverted into the
**CHECK** a critic should run. Paraphrased; examples are our own.

---

## `MILNE` — J. S. Milne, *Tips for Authors* (sardonic)

Milne's framing: *"If you write clearly, then your readers may understand your mathematics
and conclude that it isn't profound. Worse, a referee may find your errors."* Every "tip"
is an anti-pattern.

| Anti-pattern (do NOT do) | **CHECK** the critic runs |
|---|---|
| Begin with pages of notation/conditions, never explaining what they mean or why they're needed. | Are non-obvious hypotheses/conditions **motivated** near where they're introduced? Flag unexplained condition dumps. |
| Never state what you're doing or why; hide the result until the end (if ever). | Does the intro **state the main result and its purpose** early and accurately? |
| Defer all nonstandard definitions to another obscure paper, or omit them. | Is every nonstandard term **defined in-paper or precisely cited**? Flag "see [X]" used for a *definition* the reader needs. |
| Use vague vogue words ("we address Hilbert's nth issue") that hide whether you solved anything. | Flag hedge/vogue phrasing that obscures the **actual claim strength** (solved? partially? conjectured?). |
| Use a term in the main theorem for which even you know no definition. | Every term in a theorem statement must resolve to a definition. **[LINT]-adjacent.** |
| Inconsistent, ornamented notation for parallel objects (Jordan's `a, M₃′, ε₂, ∏″₁,₂`). | Parallel objects get **parallel notation**. Flag gratuitous notational variety. |
| Begin and end sentences with symbols so sentence boundaries vanish. | **[LINT]** Flag sentence-initial symbols and symbol-adjacent-to-period. |
| Attach footnote superscripts to math symbols (mistaken for exponents). | **[LINT]** Flag footnote markers on symbols. |
| Write "so that" for "such that," "which" for "that"; prefer the ambiguous to the precise. | **[LINT]** which/that + so-that/such-that checks (mirrors `POONEN`, `CONRAD`). |
| Numbering chaos: Lemma/Theorem/Prop/Corollary each numbered on different schemes; formulas separately. | **[LINT]** Check a **single coherent numbering scheme**; flag corollaries numbered as functions of several variables. |
| If all else fails, write in a language most readers can't read. | (Meta) audience-accessibility check. |
| Quantifier-negation sloppiness ("all data sets do not have similar characteristics" for "not all…"). | **[LLM/VERIFY]** Check quantifier/negation order — a frequent *correctness* bug, not just style. |

## `SERRE` — J.-P. Serre, *How to Write Mathematics Badly*

Same inversion principle (lecture). Recurring points that add to the check list:

- Don't hide the main idea under technical generality introduced too early → **CHECK**:
  is there a readable statement of the main theorem before the machinery?
- Don't use the same letter for different things, or different letters for the same thing
  across sections → **[LINT]** symbol-reuse / symbol-drift across the document.
- Don't omit hypotheses in restatements → **[VERIFY]** restated theorems must carry the
  same hypotheses as their original statement.

## `AARONSON` — Scott Aaronson, *Ten Signs a Claimed Mathematical Breakthrough Is Wrong*

A heuristic **screen for generated/claimed results** — especially valuable when the input
is auto-research markdown that may overstate. Use as a fast triage the Referee runs *before*
deep proof-checking. Inverted into checks:

1. The paper doesn't build on / engage prior work → **CHECK** related-work grounding.
2. It solves a famous problem with disproportionately elementary tools → **flag for
   heightened scrutiny** (not auto-reject).
3. Central definitions are vague or shift meaning mid-paper → **[LINT/LLM]** definition
   stability check (overlaps `MILNE`).
4. No new idea is identifiable; the "proof" is a wall of manipulation → **CHECK** that a
   **key idea / difficulty spike** is articulated (overlaps `TAO-READ`).
5. Claims prove *too much* (would refute known results / prove a stronger false statement)
   → **[VERIFY] global-error check** (this is exactly Tao's "global error").
6. Notation-heavy with no worked example → **CHECK** for at least one concrete instance.
7. Boundary/degenerate cases silently ignored → **[VERIFY]** test tight-hypothesis and edge
   cases.
8. Hallucinated or non-existent citations → hand to the **Provenance Auditor** (see
   `ai-governance.md`); under current arXiv rules this alone can be disqualifying.

---

### How the panel uses this file

- **Skeptical Editor** owns the `MILNE`/`SERRE` overselling, motivation, definition-defer,
  and vogue-word checks (L3).
- **Pedant** owns the `[LINT]` items (sentence-initial symbols, numbering, which/that) (L4).
- **Referee** owns the `AARONSON` triage + `MILNE`/`SERRE` quantifier/hypothesis/global
  checks (L1), running the cheap triage first.
- **Provenance Auditor** owns citation existence/support (L1/L5).
