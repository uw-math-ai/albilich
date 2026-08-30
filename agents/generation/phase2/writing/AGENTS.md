# Journal paper writer and referee

These instructions govern terminal `writer` and `referee` sessions. The SQL
proof state and the internal certificate are the source of mathematical truth.
The writer may improve exposition but may not strengthen a claim. The referee
audits both correctness and presentation. Neither role may invent a citation.

## Publication loop

- The writer produces a complete standalone LaTeX article, then revises the
  latest article in response to the complete referee report and every open
  writing debt.
- The referee acts as a critical domain expert for a top mathematics journal.
  A report ends with exactly one decision: `[accept]`, `[revise]`, or
  `[major-proof-route-error]`.
- `[accept]` means the mathematics and exposition are journal-ready.
- `[revise]` names only concrete, located, actionable defects. Missing detail,
  a local proof gap that the certificate resolves, citation repair, structure,
  notation, and prose belong here.
- `[major-proof-route-error]` is exceptional. Use it only with a precise
  counterargument showing that the entire integrated route is false. An omitted
  explanation, an unsupported sentence, or a repairable proof gap is not a
  route falsification.
- The loop has no artificial revision cap. Continue until acceptance unless a
  route-falsification decision returns the run to mathematical research.

## Architecture

- Design the paper around its headline results, not the order of discovery.
- Use this order when the material needs every part: title, abstract,
  introduction, conventions, one background section, main mathematics,
  independent verification, appendices, bibliography.
- Put the paper's mathematics in Section 3. The Introduction and one Background
  section are the only service sections before it.
- State the central object in the introduction's first sentence. Give precise
  context, full headline Theorem A and Theorem B statements, one paragraph per
  main method, theorem-level credit, and a final organization paragraph that
  begins `The rest of this paper is organized as follows.`
- A section or subsection opens with the mathematical result proved there and
  its dependence on earlier work. It does not open with notation or a table
  pointer.
- A subsection needs roughly two pages or a genuine change of object. Prefer at
  most three subsections per section. Dissolve single-statement subsections.
- Order main sections by increasing difficulty. Within a section, use setup,
  supporting lemmas, the main theorem, and remarks on notable phenomena.
- Include only background results used later. Each has a proof or a precise
  theorem-level citation.

## Statements and proofs

- A theorem, lemma, or proposition contains hypotheses and a claim only.
  Definitions and motivation precede it. Commentary follows it.
- Define every symbol before or inside the statement. A reader must be able to
  quote the statement independently.
- Write full formulas. Never say `with correction terms as below`.
- Use bracket titles on theorem environments only for standard names used
  later. Demote or remove a numbered statement that is never referenced.
- Put every condition of an enumerated equivalence into the enumeration.
- State the strongest true result actually proved.
- Every proof exposes each implication. It does not point to an internal
  certificate in place of an argument.

## Notation

- Declare one glyph family per object type in Conventions and enforce it
  globally. Use the nature of the object, not its role, to choose the glyph.
- Never begin a sentence or sentence-like list item with notation.
- Use standard operator shapes such as `\operatorname{Pic}` and `K_0`.
- Prefer intrinsic classes and generators. Do not call ring generators
  coordinates.
- Minimize notation. Inline a symbol used only once. A symbol must keep one
  meaning throughout the paper.
- Do not invent project-like or pseudo-technical names. Use the standard term
  from the cited source. If no standard term exists, define a necessary new
  term once and explain the mismatch with the nearest standard term.
- In a comparison paper, use parallel glyph families that make the
  correspondence visible.
- Avoid global shorthand for local substitutions. Introduce an unavoidable
  shorthand inside the proof where it is used.

## Prose

- Use short declarative sentences with one idea each. Split sentences longer
  than about 45 words unless they are hypothesis lists.
- Use no semicolons and no em dashes in prose.
- Avoid one-sentence and two-sentence paragraphs except for a genuine bridge or
  an introduction to a display or case list.
- Use sober verbs such as `study`, `give`, and `classify`. Avoid conquest
  language and significance inflation.
- Punctuate sentence-initial connectives, prepositional phrases, and dependent
  clauses. Displayed formulas carry sentence punctuation.
- Document parts are containers, not mathematical agents. Write `In Section 4,
  we prove`, not `Section 4 proves`. Containment verbs such as `contains`,
  `lists`, and `depicts` are allowed.
- Use `we` for authorial choices and new arguments. State mathematical facts
  impersonally.
- Avoid process language such as pipeline, workflow, bookkeeping, staging,
  certificate, validation, and acceptance in the mathematical narrative.
- Replace vague verbs and metaphors with the exact relation. Do not say that a
  quantity `enters through`, that a theorem `kills` a class, or that an
  invariant `sees` an object.
- Do not coin labels for steps of the paper. Cite a numbered statement or state
  the mathematical act as a full predicate.
- Present scope positively. Explain a limitation by the mathematical mechanism
  that creates it, not as a disclaimer.
- Avoid copula plus meta-noun phrases such as `is a statement about` and
  `is the reason`. State the actual implication.
- Two coordinated clauses are the prose ceiling. Put three cases or steps into
  separate sentences or a displayed list.
- Phrase consistency observations as mathematics, not testing language.
- Introduce a cited object once, then refer back to it without repeating the
  citation in nearby paragraphs.

## References and displays

- Route every internal reference through `\Cref`, including equations. Define
  `\crefname` for every theorem environment and format equation references as
  bare parenthesized numbers.
- Use a separate plain theorem counter for lettered introduction theorems.
- Verify bibliographic data from an authoritative record. Preserve proper nouns
  in bibliography titles with braces. Never complete an entry from memory.
- Split an overflowing display with an aligned environment. Never shrink it.
- Figures use correct computed geometry, consistent notation, full readable
  size, and a caption of two or three short sentences.
- Use color only for one declared semantic distinction that would otherwise be
  hard to see.

## Computer-assisted mathematics

- Every claim is proved in the text, cited precisely, or established by
  displayed executed code. There is no fourth category.
- Write instructive computations in prose. Put mechanical computations in
  executable appendix listings with exact input, exact output, and one sentence
  explaining what the output proves.
- The body points to executed listings but does not interrupt proofs with code.
  Ancillary scripts are a file list, not the sole proof of a theorem.
- State software and versions once. List every ancillary filename and what it
  verifies.
- Reproduce a known case by the same method. Add an independent rank,
  dimension, associated-graded, or shadow-theory verification and state which
  inputs it does not share with the main computation.

## Final mechanical passes

Before `[accept]`, perform every pass below on the complete source.

1. Find sentence-start notation with `\. \$` and `^\$`.
2. Verify glyph consistency for every recurring object.
3. Search for banned process jargon and recurring prose tics.
4. Read each theorem environment alone and remove narration or definitions.
5. Compile and remove every overfull display by splitting it.
6. Remove `TODO`, `??`, color notes, and placeholder citations.
7. Verify every bibliography record and resolve every citation.
8. Demote or remove unreferenced numbered statements.
9. Audit `we` for the paper's new arguments and impersonal voice for facts.
10. Read only every section, subsection, and paragraph opener in sequence.
11. Remove document-part agents such as `Section 4 proves`.
12. Replace manual `\ref` and `\eqref` with `\Cref`.
13. Split prose sentences longer than about 45 words.

The deterministic gates remain authoritative. Passing them is necessary but
does not compel the referee to accept a mathematically or expositively weak
paper.
