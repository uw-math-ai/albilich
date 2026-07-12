# TAO-READ — Terence Tao, reading-side taxonomy articles (fetched 2026-07-08; the error/confusion taxonomies that power the Confused Reader and Referee critics)

## On "local" and "global" errors (and how to detect them)
1. A proof is a DAG of statements and deductions. **Local error**: a specific step (or cluster) is invalid (false implication, circularity, ambiguity where different steps use different readings of the same expression). **Global error**: the argument would imply a further consequence known/strongly suspected false.
2. Ambiguity as local error: expression B readable as B₁ or B₂; step 1 valid only for B₁, step 2 only for B₂ — each step looks fine; the chain is broken. Hence "the importance of getting key terms defined precisely."
3. Circularity as local error: A justified by B and B by A — both implications individually true, joint conclusion unsupported.
4. **A counterexample to the claimed implication is the strongest global error**: "one instantly knows that the chain must be invalid, even if one cannot immediately pinpoint where the precise error is" — a non-constructive guarantee that a local error exists somewhere.
5. Structural probing: if the proof of A ⟹ E would work verbatim for a parallel claim A′ ⟹ E′ that is FALSE, the proof is globally flawed. **A proof that "mysteriously never uses in any essential way a crucial hypothesis" signals a structural flaw** (either error, or removable hypothesis).
6. Asymmetry: local errors can often be patched (especially in fault-tolerant proofs); global errors "invalidate not only the proposed proof as it stands, but also all reasonable perturbations" — counterexamples defeat all patches.
7. Efficiency: "to find a local error in an N-page paper, one basically has to read a significant fraction of that paper line-by-line, whereas to find a global error it is often sufficient to skim the paper" (test strength jumps, probe special cases, compare with known results). → Verifier scheduling: run global-error checks FIRST.
8. Design instruction: **structure proofs to be fault tolerant** (a failed step shouldn't collapse the paper); global pitfalls are avoided by strategy, not structure.
9. When TESTING an argument (vs building it), "it is perfectly acceptable to use heuristics, hand-waving, intuition, or other non-rigorous means" — an objection need not be watertight; it indicates either an invalid proof or a miscalibrated intuition (and paradoxical-but-true resolutions improve the intuition).

## On "compilation errors" in mathematical reading
10. Taxonomy of reader-side compilation failures: undefined/mysterious terms; unexplained logical steps; typos with cascading effects; cryptic comments that later turn out to carry essential information; implicit logical connections (statements juxtaposed without connectives); missing hypotheses buried in dense text. "A single typo or undefined term can cause one's comprehension of the paper to grind to a complete halt."
11. Reader resolution strategies (the Confused Reader's repair repertoire — each one is ALSO a writing antipattern when required): read a line or two ahead; read to the end of the proof; search forward to where the result is invoked; PDF search on the notation.
12. Assume authorial fallibility: if A yields B′ (not the stated B) and later steps need B′, "the most likely diagnosis is that the author actually meant to write B′ in both places."
13. Absent connectives are information: if no "thus/therefore/consequently" links A to B, B is probably derived from another source — reread nearby text. (Writing-side dual: KLR/Poonen "write the little words.")
14. Projection heuristics for hard papers: specialize dimension; treat all error terms as negligible (or dually, trust the main term and audit only error terms); specialize to a near-counterexample ("often quite instructive"); each projection removes ~half the difficulty, and "the difficulty of reading a paper usually increases in a super-linear fashion with the complexity."
15. Get into the author's head: "A good author will interleave the mathematical text with commentary that is designed to do exactly this"; in extreme cases diagram all logical dependencies on a blackboard to expose the key steps.

## On key "jumps in difficulty" (strength of statements)
16. Theorem strength: strong conclusions, weak hypotheses/axioms, or both; measured against the class of problems the theorem is meant to help solve (field-specific: error terms in analytic number theory; class of initial data in PDE).
17. Strength orderings (heuristics): universal > "for many x" / "for almost every x" > existential; general objects > special objects (with the generality/conclusion tradeoff); non-asymptotic > asymptotic; exact > approximate; hard/poorly-understood objects > easy/well-understood ones (integers > reals; nonlinear > linear; prime-factorisation-sensitive > non-arithmetic).
18. Reading strategy: locate "portions of the argument where the strength of the statements increases significantly. Such amplifications often contain an essential trick or idea which powers the entire argument."
19. **Flaw detection: "If the proof ends up being flawed, it is quite likely that at least one of these flaws will be associated with a step where statements became unexpectedly stronger by a suspiciously significant amount."** → Referee heuristic: audit the strength-jump steps line-by-line first.
20. Strength is context-dependent (in an induction on dimension, any statement in dimension d+1 counts as stronger than any in dimension d; the d→d+1 conversion passages are the key to the strategy).

## On implicit notational conventions
21. Letters carry type connotations (x real, z complex, n natural, ε small positive analysis quantity): "a mathematical argument involving a complex number x, a natural number z, and a real number n would read very strangely"; "a quantity ε which was very large or negative would cause a lot of unnecessary cognitive dissonance."
22. Inequality orientation: unknown/controlled quantity on the LEFT, known/controlling on the RIGHT — "x < 5 is preferable to 5 > x"; bound non-negative quantities, not non-positive ones (|x| < 5, not −|x| > −5).
23. Term ordering: main term first, error terms later ("x < 1 + ε preferable to x < ε + 1") — ordering conveys which terms are main vs error.
24. These conventions have no exhaustive listing (picked up by reading the subject) and "serve a useful purpose by conveying additional contextual data beyond the formal logical content."
