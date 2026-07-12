# KLR — Knuth, Larrabee, Roberts, "Mathematical Writing" (fetched 2026-07-08; 119pp Stanford CS 209 course notes, 1987; §1 minicourse read in full + Lamport, van Leunen, Halmos-lecture, and Final Truths sections read; middle sections on refereeing/manuals/illustrations skimmed via ToC — lecture-anecdote material, lower rubric value; Lamport's two tabular handouts are scanned images with no extractable text)

## §1 The minicourse: Knuth's 27 points (the core checkable rules)
1. **Symbols in different formulas must be separated by words.** Bad: "Consider S_q, q < p." Good: "Consider S_q, where q < p."
2. **Don't start a sentence with a symbol.** Bad: "x^n − a has n distinct zeroes." Good: "The polynomial x^n − a has n distinct zeroes."
3. Don't use …, ⇒, ∀, ∃, ∋ in prose; replace with words (except in works on logic).
4. The statement just before a theorem/algorithm must be a complete sentence or end with a colon. Bad: "We now have the following\nTheorem. H(x) is continuous." Good: "We can now prove the following result.\nTheorem. The function H(x) defined in (5) is continuous." (Better still: a suggestive motivation tying the theorem to the discussion.)
5. **Theorem statements should be self-contained**, not depending on assumptions in preceding text (note the restatement in point 4 adds "defined in (5)").
6. "We" avoids passive voice and means "you and me together" (a dialog between author and reader), never a formal "I". "I" avoided unless the author's persona is relevant.
7. Sentences have rhythm; read your text and reword what doesn't flow ("merge patterns" vs "merging patterns"; many ways to say "therefore" but often only one has the correct rhythm).
8. **Don't omit "that" when it helps parsing**: "Assume that A is a group," not "Assume A is a group." But never "We have that x = y" — "We have x = y." And no padding ("because of the fact that").
9. Vary sentence structure to avoid monotony, but use parallelism for parallel concepts (Strunk & White #15: "Formerly, science was taught by the textbook method; now it is taught by the laboratory method."). Keep "sticky" words (unusual/polysyllabic) spaced well apart; avoid "this"/"also" in consecutive sentences.
10. **Don't write homework-style**: never a bare list of formulas — tie concepts together with running commentary.
11. **State things twice, in complementary ways**, especially definitions (define formally AND characterize informally). All variables must be defined, at least informally, when first introduced.
12. Motivate what follows; keep the reader uppermost in mind: What does the reader know so far? What does the reader expect next and why? Others' work may be called "interesting/remarkable" (better: let results speak or give reasons); **describing your own work, be humble — no superlatives of praise, explicit or implicit.**
13. **The "blah" test**: readers skim formulas on first reading — sentences must flow when all but the simplest formulas are replaced by "blah."
14. Never the same notation for two things; consistent notation for the same thing everywhere (not "A_j for 1 ≤ j ≤ n" here and "A_k …" there). Choose index conventions (i up to m, j up to n) and typographic conventions (lowercase elements, uppercase sets) and stick to them.
15. Avoid subscript proliferation: don't write X = {x₁,…,xₙ} if you'll need subsets (forcing x_{i₁},…,x_{i_m}); don't name elements unless necessary — refer to "elements x and y of X."
16. Display important formulas on their own line; number all the most important ones (even if unreferenced) when remote reference is possible.
17. Sentences must parse unambiguously left to right. Bad: "Smith remarked in a paper about the scarcity of data." "In the theory of rings, groups and other algebraic structures are treated."
18. Spell out small numbers used as adjectives ("two passes") but not as names ("Method 2", "increased by 2", "the leftmost 2").
19. Capitalize Theorem 1, Lemma 2, Algorithm 3, Method 4.
20. (Self-demonstrating maxims) Watch prepositions sentences end with; dangling participles; fragments; pronoun agreement; unnecessary commas; split infinitives.
21. Spelling list: implement, complement, occurrence, dependent, auxiliary, feasible, preceding, referring, category, consistent, descendant (noun), its/it's; "nonnegative" and "nonzero" are not hyphenated.
22. "Which" only after a comma or preposition or interrogatively; otherwise "that." ("Don't use commas that aren't necessary.") Also less vs fewer.
23. **No colon before a displayed equation when the text reads through it grammatically** ("If C and P are subsets of Nⁿ, let: L(C,P) = …" — the colon is wrong).
24. **The opening paragraph should be your best paragraph, its first sentence your best sentence.** Worst opening form: "An x is y." Bad: "An important method for internal sorting is quicksort." Good: "Quicksort is an important method for internal sorting, because…"
25. Commas/periods inside quotation marks per convention, EXCEPT when quoting a specific string of symbols: Always end your program with the word "end". Punctuation strictly logical with parentheses/brackets: period inside parens iff the whole sentence is inside. Bad: "This is bad, (although intentionally so.)"
26. No long noun-strings as adjectives ("the packet switched data communication network protocol problem"); no unnecessary jargon — "Even specialists in a field get more pleasure from papers that use a nonspecialist's vocabulary." (Linderholm ∀∃-garble vs Knuth's fundamental-theorem prose as worked Bad/Good pair.)
27. Humor: only jokes that also require understanding a technical point; must survive second and third readings. Don't overuse exclamation points.

## Lamport lecture (§31) + handouts
28. "Bad writing comes from bad thinking, and bad thinking never produces good writing." Venue calibration: journal articles polished and timeless; conference papers rougher; tech reports for work not ready for the world (throw nothing away).
29. A "conceit" (organizing metaphor) can catalyze a paper but must not intrude; beware jokes ("How funny will it be ten years later?").
30. **"It is better to have one solid example than a dry, abstract, academic paper"; it is never a mistake to have too simple an example. "Examples keep you honest"** — Lamport's own published theory needed major revision when its intended example failed.
31. Fix the idea, not the sentence; think structure, not format; macro-ize complex notation while drafting.
32. Structured/tabular ("statement-reason") proofs expose logical structure; writing a proof in that form clarifies even a proof to be PRESENTED in paragraph style. (Halmos counter-position §43: prefers prose proofs, symbols "insidious"; both agree outline form can help — record as an explicit style conflict.)
33. First sentences: "avoid passive wimpiness," be simple and direct, "get right down to business" — and sustain it ("When you come to sentence number 2079, you've got to keep socking it to them").

## Mary-Claire van Leunen sections (§26, §37-39) + Final Truths (§44)
34. Which/that history and rule: "that" = defining/restrictive, "which" = non-defining/non-restrictive (Fowler → Strunk & White). Operational form (Lamport's): "If it sounds all right to replace a 'which' by a 'that', replace it." Wicked whiches irritate trained readers (Knuth); van Leunen: the rules hold for "shirtsleeve prose"; Lamport: an occasional wicked which avoids a string of thats. Tone verdict: "Tone consists entirely of making these tiny, tiny choices. If you make enough of them wrong … the reader who doesn't have to read will stop."
35. "Hopefully" as sentential adverb: raises hackles in many readers, distracting them — avoid it (Knuth's operative rule), whatever its linguistic merits.
36. Coincident punctuation: where two commas coincide, write one; comma+period → period. "Truly, coincident punctuation is not a problem."
37. Generic pronouns: 'he or she' clumsy with repetition; van Leunen: "The traditional solution is 'they'." (Halmos preferred generic 'he'; modern standard = singular they / recasting. Record as evolved-consensus.)

## Paul Halmos guest lecture (§43)
38. The two master rules: **"Do organize" and "Do not distract."** Organization is most of his writing time; "the plot of an exposition is rarely a straight line" — branches must be woven. (Break the rules deliberately only to jar the reader.) Final words: "Anything that helps communication is good. Anything that hurts is bad."
39. **Prefer direct proofs to proofs by contradiction** whenever available (linear-independence worked example: "Suppose … not all zero … contradiction" → "If the linear relation holds, the coefficients are all zero"). Knuth's gloss: contradiction is how you FIND a proof; stream-of-consciousness proofs are not the best exposition.
40. Don't echo unusual words: two uses of the same striking word in unrelated passages become associated in the reader's mind and cause unwarranted connections.
41. Numeral vs word disambiguation: use '1' (symbol) when speaking of the numeral, 'one' risks pronoun reading ("What are we to do when x is one?"; Birkhoff-MacLane's "Any positive integer which is not one or a prime…").
42. Beyond "we": prefer imperative/indicative recasts — "We can now prove the following result:" → "A consequence of all this is the following result." / "Consequence: A implies B." / "Replace x by 7 throughout." ('We' is not a crime but adds an irrelevant dimension.) First person singular: avoid in formal technical writing.
43. Quotation-mark punctuation: Halmos urges logical placement always (vs Knuth's rule 25 convention-except-strings) — recorded conflict; both agree parenthesis punctuation is strictly logical.

## Final Truths (§44) — Knuth's closing calibrations
44. "The style has to be your own. You will write things that someone else will never write."
45. 'the proof above' preferred to 'the above proof' (editors enforce it; 'below' never precedes its noun).
46. Familiar unhyphenated compounds in-field ("random number generator", "floating point arithmetic") may stay unhyphenated despite ambiguity rules — audience calibration.
47. Typesetting: prefer slashed form n(n+1)(2n+1)/3 over built-up display fractions inline.
48. Exclamation points only for actual exclamations; Halmos's escape hatch: "(!)" in parentheses for surprise — once per chapter at most.
49. Split infinitives: sometimes the best emphasis; rewrites can sound forced (Floyd/Knuth agree the blanket rule is unwise).
50. Sentence-final prepositions: fine ("You have no case, give up") EXCEPT when the sentence already accommodates the preposition mid-structure ("Avoid such prepositions, which such sentences end with").
51. That-omission is fine when a nominative pronoun keeps syntax clear ('He said he was going'); in complicated technical sentences keep 'that'.
52. **The 'then' rule (Knuth's final form)**: in newspaper prose drop it; **in mathematical contexts where the post-comma phrase is a mathematical statement, definitely keep 'then'** — "our brains only have time to do simple parsing when reading for speed."

## Meta
- Recommended shelf (§0): Strunk & White; van Leunen, A Handbook for Scholars; Gillman, Writing Mathematics Well; Flanders (Monthly 1971); Boas (Monthly 1981); AMS How to Write Mathematics (Halmos essay).
- The exercise (§2-3): a sophomore's all-symbols proof (⇒, ∋, Spse) vs its prose rewrite — canonical Bad/Good eval pair for the "no homework style" rule.
