# SERRE — Jean-Pierre Serre, "How to write mathematics badly" (fetched 2026-07-08; full Calle transcript of the 2003 Harvard Basic Notions lecture, 16pp, read in full)

Satirical anti-guide ("I feel I am an expert in how to write mathematics badly … by taking the opposite we might manage to do better"). Each item below is the inverted positive rule, with Serre's example.

## Titles, theorem statements, notation
1. Title must be informative — the anti-title "A proof of a theorem of Euler" (or of so-and-so) gives no information at all.
2. Don't call the sole theorem "Main Theorem" while writing as if there were many; don't state theorems in unexplained private notation ("Theorem. An fpph ATT is regular." — misprint for fppf included, and "regular" has "about two dozen different definitions"). Define notation precisely BEFORE the theorem.
3. Watch overloaded standard terms ("regular"): if a term has many established meanings, say which one is meant.

## References
4. Uncheckable references are the cardinal citation sin: a bare pointer to a 600-page book with no page number; "the complete works of Euler" ("They have not been published yet entirely"); SGA/EGA without location; and the unbeatable "cf. [H]" → "[H] D. Hilbert, private communication."
5. Give references to books WITH the page number. And verify the reference actually contains the claimed statement — Serre's referee anecdote: a formula attributed to one of his own books wasn't there, and was in fact WRONG (he built a counterexample). Wrong-attribution = wrong-formula risk.

## Proofs
6. Don't front-load full proofs of easy Lemmas 1-2 and then compress all real difficulty into Lemma 3 dispatched with "It is a computation," "It follows from the definitions" — or the unbeatable naked □. Proof effort must be distributed where the difficulty is; the QED symbol must not paper over an unproved step.
7. **Mistakes live in the non-written part**: "The proof is wrong, but everything you have written is correct … they give an argument, then they stop. They believe that with what they have proved, that implies the theorem, but the implication they did not detail. And that's where the mistake was." → Verifier rule: audit the implicit final implication from "what was shown" to "what was claimed."
8. "Every proof has some kind of cheating inside … the question is, what do you leave out?" Writing entirely rigorously is impossible; knowing what to omit is the art. (Identifications: N ⊂ Z ⊂ Q ⊂ R is literally false set-theoretically — card(3) is 3 in N, ℵ₀ in Z/Q, 2^ℵ₀ in R; Q → A_Q vs Q_p → A_Q embeddings incompatible — one must SAY which identification is in mind when it matters.)
9. Bourbaki-proof definition: "a proof is something which is accepted by experts, and a Bourbaki proof is accepted by non-experts. And of course I favor the second choice." Don't deflect criticism with "of course it's not a Bourbaki proof."
10. "To prove Theorem 2 is similar" / mutatis mutandis — Serre dislikes it very much; often it hides the need for the correct common statement.

## Grammar as logic
11. **The definite-article cheat (a/the)**: "Theorem 1. There exists an isomorphism f: X→Y…" followed by "Theorem 2. f is continuous" — Theorem 1 only asserts Isom(X,Y) ≠ ∅; "The map of Theorem 1" is "absolutely meaningless." Switching from indefinite to definite article claims things never proven. Fix: construct the object FIRST, then state its properties ("it is better to construct the animal first, and then give its properties"), or announce the construction ("We construct in paragraph 2 an f having this property").
12. The (a)/(b) ambiguity: "Theorem. (a) There exists f, (b) f is …" — does it mean SOME f satisfies (b), or EVERY f from (a)? The author must disambiguate (speakers "chicken out" into "one can prove f has (a) and (b)").
13. "There exists a bijection" when no specific bijection is constructed means only "these two sets have the same cardinal" — don't state existence when you mean (and need) a canonical/specific object (Langlands-lectures anecdote).
14. **Commas may not do work they are not paid to do**: "If A, B, C." — first comma means "and," second means "hence." Spell it out: "If A and B are true, so is C" (it could equally parse as "If A, then B and C").
15. **No symbols for verbs**: the Inventiones theorem that was one long formula ending "∈ Q" — the entire mathematical content was the ∈, invisible in the symbol string. The verb of a theorem must be findable (write "is rational").
16. Never begin a sentence with a symbol (the screaming-typewriter rule).
17. Typography dots collide: "f(x) = sin(x)·cos(x). cos(x) being continuous…" — sentence-period vs product-dot confusion; insert words ("the function cos(x)").

## Analysis-specific honesty
18. **"The constant" discipline**: |Af| ≤ C|f| after "Let f…" — "Let" nails f to the blackboard, so a priori C depends on f; authors don't say what C depends on. Correct: Vinogradov ≪ with SUBSCRIPTS listing every dependence (≪_A etc.).
19. **O-notation discipline**: f(x) = O(g(x)) means TWO constants (C and x₀ with |f(x)| ≤ C|g(x)| for x ≥ x₀); state the limit direction (x → +∞); "the constant implicit in the O-notation" is meaningful only if x₀ is explicit — in Chebotarev-type effective bounds "x₀ is as difficult to choose as the constant. … a typical way of cheating in analytic number theory which I think causes a lot of mistakes."

## Field-specific cheats
20. Homological algebra: claiming "all the diagrams are commutative" / "two naturally defined arrows are equal" without proof (Eilenberg to Serre: "you have not proved it's the same map. Might be the opposite."). "The spectral sequence of X → Y" — the definite article presupposes a specific construction; different constructions (Leray vs Grothendieck-Tôhoku) give isomorphic terms "but not with an obvious arrow" (the U×V orientation puzzle: two natural choices).
21. Topology: pictures in proofs — "for the author … 'absolutely splendid, I understand everything.' And for the reader, it takes a thousand explanations." State which features of the picture are essential (does it matter that it wiggles three times? that the curves don't touch?).

## Spelling, abbreviations, words
22. its/it's; "principle bundle" ("a principle which varies with a parameter … has a moral fiber") — spellcheck cannot catch it; a dictionary says it's a word.
23. Abbreviation ambiguity: "an ell. curve with. c.m." — the dot makes "with." an abbreviation (of "without"?!, per Kodaira anecdote). Avoid abbreviations that can be misresolved.
24. ∀, ∃ in prose: "It doesn't take very long for replacing them by 'for all' and 'exists.'"
25. "iff" is "ugly English, but good mathematics" (unambiguous) — still, auto-expand it to "if and only if" (and French "ssi" → "si et seulement si").

## Q&A wisdom
26. Ideas vs details: "If you give me a proof with all the details, I can find the ideas behind — that's very difficult. If you give me the ideas and not the details, I may get completely stuck on some of the details." Serre prefers MORE detail on paper: too long → flip the page; too short → "you may spend a lot of time trying to reconstruct it."
27. Statements-first organization (long introduction with all statements, proofs after) can be clearer — but only if the introduction's notation is defined there ("Very often you find in introduction Theorem 3.1 … and the notation has not been introduced").
28. Copy-paste is the modern failure mode: "it's too easy now to take a piece you have written at some point and put it with another one and your notations don't agree." (Directly relevant to LLM-generated text.)
