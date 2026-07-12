# Canonical Essays & Books — Distilled Principles

Paraphrased in our own words. See `INDEX.md` for URLs to authoritative originals.
Bracketed keys map rules back to sources.

---

## `HALMOS` — Halmos, *How to Write Mathematics*

Foundational doctrine that nearly everything downstream builds on.

- **Have something to say.** The single most important ingredient of good exposition
  is a clearly delineated subject that hangs together. If the idea is important enough,
  much else can be forgiven.
- **Write for someone.** Decide precisely who the reader is (a diary note, a letter to a
  friend, a research announcement for specialists, an undergraduate text) — the target
  audience governs every other decision. Even for ephemeral work, write as if for the ages.
- **Design notation before you write.** Halmos built large tables of alphabets and fonts,
  upper and lower case, to anticipate every symbol collision *in advance*. Notation is
  architecture, not an afterthought. → harness: the Planner's living **notation table**.
- **The "spiral plan."** Write a section, then the next, then go back and improve the
  earlier one; understanding accumulates and forces revision. → harness: iterative rounds.
- **Prefer the least obtrusive style.** Simple declarative sentences; the neutral,
  factual voice; avoid ostentatious "one has thus proved…"; the imperative is often
  effective and time-saving ("To find P, multiply q by r").
- **Use words and symbols each for what they do best.** Do not rely purely on symbols.
- Repetition and omission are tools: repeat deliberately to emphasize; omit deliberately
  to signal that a step is routine.

## `KLR` — Knuth, Larrabee & Roberts, *Mathematical Writing*

Transcripts of Knuth's Stanford course; before/after manuscript surgery.

- Separate concerns of **"form"** (parentheses, capitalization, fonts, punctuation) from
  **"content"** (wording, sentence construction, tense). → harness: distinct critics.
- **Not all formulas are equations** — a formula may be a relation, definition, statement,
  or theorem; name it correctly.
- Distinguish **mathematical notation from programming notation** (fine to write `p[r]` in
  code; use a subscript in a formal paper).
- Avoid excessive subscripts and superscripts; redesign notation rather than stacking it.
- **Tense:** present tense for facts still true; past tense is acceptable for "facts" that
  turned out to be in error.
- The `we` convention: "we" can bind author and reader together as a team; with multiple
  authors, either embrace the ambiguity or disambiguate ("one of the authors (DEK)").
- Exercises and out-of-context statements are where ambiguity is deadliest — be extra
  precise wherever the reader lacks surrounding context. → harness: the Confused Reader.
- Keep a shelf of reference works (dictionaries, usage guides) and cite sources faithfully.

## `TAO` — Terence Tao, *On writing*

Both advice and an annotated index to the whole field.

- **Sell the key points in the introduction**, but describe the results *accurately*.
- Invest in **organizing and motivating** the paper and in **selecting good notation**.
- Give an **appropriate amount of detail** — but **do not over-optimise** the paper.
- **Factor the paper into small pieces** by making plenty of lemmas.
- **Write a rapid prototype first** to reduce total writing/organizing time.
- Write **professionally, in your own voice**; a useful trick is to make your *past self*
  the target audience.
- **Take advantage of the English language**; don't lean purely on symbols.
- The **ratio of results to effort** should sit at a *local maximum* — neither padded nor
  cryptic.
- **Submit a final draft, not a first draft.** Proofread and double-check before submission.
- Use **common sense**; rigid rules can't cover every paper.

### `TAO-READ` — the reading-side taxonomy (the spec for an adversarial critic)

- **"Compilation errors":** places where a reader literally cannot proceed because the text
  won't "compile" in their head. → the Confused Reader operationalizes this.
- **Local vs. global errors:** a *local* error is a single step that doesn't follow; a
  *global* error is one where the argument as a whole proves too much, contradicts known
  results, or does not actually use a stated hypothesis. → the Referee runs both modes.
- **Jumps in difficulty:** finding and explaining the hardest step is often the key to the
  whole argument. → critics should locate and demand justification at difficulty spikes.

## `PAK-CLEAR` — Igor Pak, *How to Write a Clear Math Paper*

- **Clarity is not a tradeoff — it is everything.** The golden rule, paramount.
- Clarity is *not only* phrasing; it is doing the legwork (e.g., fixing notation
  everywhere) even when the "arithmetic" of your time vs. a few confused readers seems to
  favor laziness. Do the 30 minutes. Every time.
- Most readers are non-native English speakers reading math in English; simple, clear,
  even "substandard" prose that everyone understands beats elegant prose that fewer follow.
- Distinguish the many standard LaTeX fonts and use them consistently; train yourself to
  tell them apart.
- **Citation precision matters** (see `professor-rulesheets.md` for Pak's "see [X]" vs.
  "[X]" vs. "in [X]" distinctions — each signals a different provenance claim).

## `PAK-STORY` — Igor Pak, *How to Tell a Good Mathematical Story*

- **There is always a story**; if it doesn't write itself, you must construct one.
- **Hard line for a generation pipeline:** on facts, results, mathematical implications,
  prior work, and references you must be **100% correct — no flexibility, including
  historical claims.** If you don't know a reference, find it; never write guesses and hope.
  → harness: this is the faithfulness/provenance invariant.
- **The story is never personal.** Not "I was drinking boba tea on my balcony when…" —
  the story must be about the *area*, retellable by mathematicians who never met you.
- Not every side example belongs; cutting can strengthen. A side example that can't stand
  alone goes in an appendix (arXiv) at most, never co-submitted to a journal.

## `ROTA` — Gian-Carlo Rota, *Ten Lessons*

- "You are more likely to be remembered by your expository work." Exposition is not lesser.
- Related maxims widely quoted: every lecture/paper should make **one** point; state it
  and restate it.

## `HIGHAM` / `KRANTZ` — reference handbooks

- Comprehensive book-length treatments of notation, English usage for mathematics, LaTeX,
  figures, and the mechanics of revision. Use as authoritative fallback for any style
  question not settled by the shorter rule sheets. `KRANTZ` is freely available on arXiv.

---

### Extraction targets for Stage 0 (rubric compilation)

From this file, the compiler should emit rules of three checkability classes:

- **Judgeable-by-LLM:** audience fit (`HALMOS`, `TAO`), motivation quality (`TAO`),
  over-optimisation (`TAO`), story presence & impersonality (`PAK-STORY`), one-point focus
  (`ROTA`), results-to-effort local maximum (`TAO`).
- **Mechanically lintable:** notation defined-before-use & used-consistently (`HALMOS`,
  `KLR`), tense of mathematical facts (`KLR`), excessive sub/superscripts (`KLR`),
  font consistency (`PAK-CLEAR`).
- **Requires verification:** none directly here — but `TAO-READ`'s local/global taxonomy
  defines *how* the Referee should attack proofs.
