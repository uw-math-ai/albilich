# Professors' Rule Sheets — Distilled Checkable Rules

These are the most "rubric-ready" sources: numbered, concrete, often with Bad/Good pairs.
Rules below are paraphrased in our own words, and the illustrative examples are **our own**
(written in the spirit of the sources, not copied). See `INDEX.md` for the originals.

Legend for checkability: **[LINT]** = deterministic; **[LLM]** = judgment call;
**[VERIFY]** = needs math checking.

---

## `CONRAD` — Keith Conrad, *Advice on Mathematical Writing*

1. **[LINT] Complete sentences.** All mathematics is written in sentences; a displayed
   equation is part of a sentence and takes punctuation.
2. **[LINT] No adjacent symbols from different expressions.** Insert words or punctuation
   between two symbols that aren't part of the same expression.
   - Bad: `If n ≠ 0 n² > 0.`  Good: `If n ≠ 0, then n² > 0.`
3. **[LINT] Bind loose ranges/quantifiers.** Don't leave a variable range dangling.
   - Bad: `Consider xₖ 1 ≤ k ≤ n.`  Good: `Consider xₖ for 1 ≤ k ≤ n.`
4. **[LLM] Make notation fit context.** Choose symbols that look natural.
   - Bad: `Let m be a prime.`  Good: `Let p be a prime.`
5. **[LINT] Define new notation before/at first use**, and say what kind of object it is.
   - Very bad: `Since n is composite, n = ab.`  Good: `Since n is composite, n = ab for
     some integers a, b with 1 < a, b < n.`
6. **[LINT] Reserve blackboard-bold sets.** `Z, Q, R, C` denote whole sets, not elements.
   - Bad: `Let C be a complex number.`  Good: `Let z be a complex number.`
7. **[LINT] Never use logic symbols (∀, ∃, ∧, ∨) as prose abbreviations** outside a logic
   paper. Write the words.
   - Bad: `The conditions imply a = 0 ∧ b = 1.`  Good: `…imply a = 0 and b = 1.`
8. **[LINT] No blackboard shorthand in formal writing** — avoid `WLOG`, `s.t.`, `iff`,
   `∴`, `∵` in the prose of a paper (spell them out).
9. **[LINT] Present tense for mathematical facts.** Facts are timeless.
   - Bad: `Someday I expect e + π will be irrational.`
     Good: `Someday I expect e + π will be *proved* irrational.`
10. **[LINT] Subject–verb agreement with sets.** "The set of real numbers **is**
    uncountable" (the *set* is uncountable), vs. "the real numbers **are** uncountable."
11. **[LINT] Spelling/usage traps:** its vs. it's; "discriminant" vs. "discriminate";
    "necessary" (one c, two s).
12. **[LINT] Italics conventions.** Single-letter variables/parameters/function names are
    italic; theorem/lemma statements are italic via the theorem environment — don't force
    italics manually. Numerals are never italic.

## `POONEN` — Bjorn Poonen, *Practical Suggestions for Mathematical Writing*

**Justification & logical bookkeeping**
1. **[LLM/VERIFY] Every non-immediate claim states what it follows from.** If a claim
   doesn't follow from the previous sentence alone, name the source ("By Lemma 8.3," or
   "Combining the previous two sentences,").
2. **[LLM] One reason per claim, clearly attached.** In a chain of equalities, make clear
   which justification explains which equality (put reasons before/after the chain or at
   the right of each `align*` line).
3. **[LLM] At every period, the reader knows why each claim so far is true.** If a claim's
   proof comes only later, flag that explicitly at the point of assertion.

**Sentences & structure**
4. **[LLM] Prefer single-idea sentences.** Combine sentences only when it clarifies logic.
   - Better: `Let x be a real number. Then x² + 1 ≥ 0.`
   - than: `We have x² + 1 ≥ 0, where x is a real number.`
5. **[LLM] Do not sacrifice clarity for brevity.**
6. **[LLM] Subdivide long proofs with lemmas** — even single-use lemmas — to minimize what
   the reader must hold in mind at once.
7. **[LLM] Outline remaining sections** so the reader has a map.

**The core reader-model insight (drives the Confused Reader critic)**
8. When you understand your own argument too well, you navigate proofs in **large chunks**;
   your reader combs through **one sentence (or less) at a time.** Judging your own clarity
   is therefore unreliable — an outside, context-starved reader is needed.

**Definitions & phrasing**
9. **[LINT] "so that" vs. "such that."** Use "such that" for a defining condition; "so
   that" for purpose/consequence.
   - Bad: `An abelian group is a group so that every two elements commute.`
   - Good: `…a group such that every two elements commute.`
10. **[LLM] Motivate conventions where it helps** ("We include 0 in ℕ so that ℕ contains
    the size of every finite set"), but don't add empty throat-clearing ("We now prove the
    following proposition" adds nothing).
11. **[LINT] Label multi-part theorem statements** consistently (a), (b), (c).

## `SU` — Francis Su, *Some Guidelines for Good Mathematical Writing*

1. **[LLM] Know your audience** — the most important consideration. What background,
   terminology, and "voice" (casual/professional, terse/loquacious) fit the reader?
2. **[LLM] Set an invitational tone.** Present tense, "we" not "I," gentle imperatives
   ("Let n be…", "Recall that…", "Consider…").
3. **[LINT] Use complete sentences**; punctuate displayed equations.
4. **[LLM] Use words to give equations context.** Contrast "Let A = 5," "Suppose A = 5,"
   "Therefore A = 5" — the words carry the logical role; "A = 5" alone is ambiguous.
5. **[LINT] Avoid shorthand in formal writing.**
6. **[LLM] Highlight structure.** Paragraphs group related ideas; the **first sentence of
   each paragraph** should let a skimmer follow the argument's flow.
7. **[LLM] Observe the culture.** Norms are conventional and era-dependent; match the
   field's current expression.
8. **[LLM] Don't confuse necessary with sufficient**, hypotheses with conclusions
   (a recurring failure mode; also see `MILNE`).
9. Enjoy the craft — writing is an occasion to reflect and refine ideas.

## `LEE` / `MAURER` — undergraduate-oriented guides (useful defaults)

- **[LINT] Math is written in sentences and paragraphs** (not a wall of one paragraph).
- **[LINT] `=` acts as a verb**; formulas obey grammar.
- **[LLM] Put important/long formulas on their own display line.**
- **[LLM] The introduction assumes the reader is unfamiliar** with the specific problem;
  state the problem, say why it's interesting, and preview what follows.
- **[LLM] State physical/simplifying assumptions explicitly.**
- **[LLM] Every paper needs a title and an abstract**; choose a title that names the paper's
  central concept where possible; keep the abstract informative but short.
- `MAURER`: number displayed equations rather than referring to "the third display on
  page 7"; line up multiline displays on their main connectives; definitions must be
  *motivated* (undergraduates especially need to know *why* a definition is needed).

---

### Bad/Good pairs are dual-purpose

Every Bad/Good pair above (and the ones you fetch from the originals) is simultaneously:
- a **few-shot example** for the relevant critic's prompt, and
- a **regression test case** for the eval harness (`eval/bad-good-pairs.md`).
Keep them tagged by rule KEY so a critic's precision/recall can be measured per rule.
