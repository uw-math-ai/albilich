# HOUSE — Project house rules for high-quality math papers (imported 2026-07-09 from the operator's WRITING_RULES.md, "Exceptional Isomorphisms" project; authoritative for this harness — HOUSE rules OUTRANK conflicting general advice)

Hand-tuned rules from revising research-level AI-generated manuscripts. The recurring theme: kill
"artificial manuscript choreography" — prose that narrates task completion instead of explaining
mathematics.

## Abstracts
1. Open with the mathematical object and context, not "This note does..." (unless that sentence immediately states a new result).
2. State the main theorem precisely; no scope-fog ("in the class considered here", "under suitable assumptions") unless the assumptions are named in the same sentence.
3. Notation sparse; formulas only when indispensable; short main constructions may appear inline; the abstract is not a proof checklist.
4. Proof ideas at high compression only: the geometric reason and the algebraic device, not the lemma sequence.

## Theorem scope
5. Define the class of objects BEFORE the theorem; no scope hidden in "more generally" or "for which the relevant objects are defined".
6. If a theorem depends on a known presentation, say exactly which and where it enters.
7. After fixing a convention, use the short term consistently — never re-expand the full descriptive phrase.
8. Base schemes, coefficient rings, functor categories consistent throughout; never introduce a broader class than the theorems use.

## Terminology & first mentions
9. First mention of a technical term: "X is/are ..." with concrete mathematical description BEFORE the term is used in any statement or argument; attribution at first mention for eponymous constructions; compact appositive definitions suffice for standard-but-specialized terms.
10. Never first-mention a term by asserting a property of it. Define, then state.
11. No anaphoric shortcuts ("such a construction", "in this case") before the underlying data/identification has been stated.
12. **Respect mathematical chronology**: never attribute a definition to a later paper that only generalized/reformulated it; use "introduced/later associated/generalized/formulated" only per the true historical relation.

## Sentence-level prose
13. **No one-sentence paragraphs** (also check accidental LaTeX paragraph breaks); paragraphs have a topic sentence plus development.
14. Complete sentences, standard commas, ordinary syntax.
15. **Avoid colons and semicolons outside math mode** — modern mathematical prose prefers separate sentences or connecting phrases. (Conflicts with AMS-STYLE §12.7 semicolon license; HOUSE wins here.)
16. **Avoid parenthetical asides in prose** — integrate the qualification or delete it.
17. No sentence openings with notation; object or logical relation first, then the symbol.
18. **No vague pronouns** ("it", "this", "these", "they") where repetition of the noun is more precise.

## Background sections
19. Every section opens with "In this section, we ..." stating in mathematical terms what the section does — embedded in a real paragraph, not a one-sentence roadmap. (Conflicts with STOP-SLOP's meta-commentary ban; HOUSE wins for math papers.)
20. **Background reads as established mathematics, not project planning.** Name the formalism and sources directly.
21. Introduce terminology before use; define only the version the paper uses; delete unused machinery even if true.

## Citations
22. **Argument-first citation style**: state the mathematical fact, then cite. Never "we use X notation" unless notation is the subject.
23. Cite a source for the theorem/construction it supplies — never as a general source for unrelated standard facts; no citation clusters in the abstract.

## "We" discipline
24. "We" for novel authorial acts only: we prove / define / formulate / construct — and REQUIRED near a genuinely new object or result (no hiding novelty in passive prose).
25. No "we" for standard background: direct impersonal sentences instead. Not "we recall/we record/we now show" by habit. "The present note proves..." often beats "we prove..." in abstracts/intros. "We have" only to avoid opening with notation.
26. "Recall" ONLY for material stated earlier in the same paper, never for literature background.

## Notation
27. Alphabetical order where no mathematical hierarchy is intended (examples, names, bibliographic clusters).
28. No notation without significant use; keep notation out of prose when words are clear; notation shows the determining data, but drop indices once a convention is fixed; never notation that under-represents the data determining the object.

## Proof prose (the anti-choreography core)
29. **Proofs explain why relations hold; they never narrate task completion.**
30. No mid-proof/mid-section foreshadowing (start-of-paper and start-of-section only).
31. **Banned procedural phrases**: "the necessary input", "the remaining calculation", "with this rank control", "it remains", "the proof rests on three points", "needed below", "the following facts", "we now record", "the mechanism is simple".
32. Replace checklist transitions with mathematical transitions that state the implication being used.
33. Keep mathematical levels distinct: state geometric identities geometrically before applying algebraic/cohomological/categorical functors.

## Final passes (the hunt list)
34. Vague scope language: "considered here", "suitable", "relevant", "in this setting".
35. Procedural language (list in 31).
36. References integrated into the argument, not listed as imported ingredients.
37. Read abstract, introduction, section openings, theorem statements, conclusion ALOUD; they must sound like mathematical prose, not an implementation plan.

## Revision-scope discipline (for the revising agent, not the text)
38. Edits stay within the stated scope; a targeted objection to one phrase is not permission for a global cleanup; distinguish inorganic choreography ("we place A beside B") from conventional infrastructure ("The rest of this note is organized as follows" — PRESERVE unless asked); decide per-sentence whether the identified defect is present before rewriting.
