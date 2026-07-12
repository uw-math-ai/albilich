# TAO — Terence Tao, "On writing" hub + sub-articles (fetched 2026-07-08 from terrytao.wordpress.com/advice-on-writing-papers/; all writing sub-articles fetched; reading-side taxonomy in TAO-READ.md)

Hub epigraph: "There are three rules for writing the novel. Unfortunately, no one knows what they are." (Maugham). "Everyone has to develop their own writing style, based on their own strengths and weaknesses, on the subject matter, on the target audience, and sometimes on the target medium."

## Use the introduction to "sell" the key points
1. State key points prominently in the introduction — never buried in footnotes, remarks, or mid-paper lemmas.
2. The author bears responsibility for communicating merits, novelties, implications; **if the referee fails to grasp the key points, the introduction lacks publication quality** (not the referee's fault).
3. Compare and contrast with existing literature; demonstrate why results/techniques are new, interesting, or surprising in that context.
4. Highlight new difficulties resolved that were absent in previous work; include counterexamples showing the results can't be improved by dropping hypotheses or strengthening conclusions; indicate where simpler literature methods prove inadequate.
5. State (or paraphrase) the main results; outline how and where they are proven. If the main result is too technical, state a simpler special case; informal statements allowed if **clearly marked informal**.
6. Title and abstract get to the point immediately — first impressions carry substance and novelty.

## Describe the results accurately
7. **"A paper should neither understate nor overstate its main results."** Surprising/breakthrough results: note explicitly with comparison to prior results, examples, conjectures.
8. Unsatisfactory aspects (hypotheses too strong, conclusions weaker than expected) "should also be stated honestly and openly."
9. Transparent uncertainty phrasing: "We do not know if hypothesis H is actually necessary"; "It can be shown that…". Note remaining open questions.
10. Famous-conjecture motivation requires "a candid evaluation of the extent to which your work truly represents progress toward that conjecture, so as to avoid the impression of 'false advertising' or 'name-dropping.'"
11. Asserting a non-trivial statement without proof or citation must be flagged as such.
12. Descriptive section titles ("Proof of the decomposition lemma", "An orthogonality argument") — never "Step 2" or "Some technicalities."

## Organise the paper
13. Stream-of-consciousness order (results in discovery order) is "generally a very bad idea."
14. Peripheral results → remarks/footnotes/discussion; necessary-but-alien or dull-computation material → appendix.
15. New section at each major turning point; closely related facts in a single section.
16. **Each major milestone formalized in a self-contained, prominently located proposition/theorem, placed EARLY (before its technical proof details); no punch line delayed to the last page.**
17. Lemma statement+proof near where the lemma is used; technical components pushed toward the back to ease the learning curve; reward the front-section reader with easy, tangible progress.
18. Expect significant reshuffling from the first draft; for large papers diagram the paper's logic (boxes = lemmas/theorems, arrows = deductions; blackboard beats paper).

## Motivate the paper
19. Orwell's four questions per sentence: What am I trying to say? What words will express it? What image or idiom will make it clearer? Is this image fresh enough to have an effect?
20. Reader always aware of near-term and long-term objectives, how current arguments advance them, how crucial they are.
21. Explain why each step's claims are plausible — or exactly why and how surprising.
22. Heuristic/motivational reasoning welcome but **clearly marked as informal** (remarks/footnotes), separate from rigorous reasoning.
23. Every section starts with a brief purpose paragraph; key sections state their milestone near the start + why it matters + a proof-sketch of the section's plan.
24. Before the most general result, discuss a less technical special case or "toy" result for flavor; explaining how a reinterpretation of existing proofs enables generalization "can be enormously clarifying."

## Use good notation
25. Notation should emphasize the most important parameters/features and downplay routine ones (≪, ≲, O() when constants don't matter; avoided when they do).
26. Global notation defined in a notation section near the front or in the introduction; local notation defined near use; **notation introduced inside a lemma's proof is localised to that proof — recalling it outside is bad form.**
27. Stay consistent with the literature's notation; when citing work with different notation, restate the key cited results translated into the current paper's notation.
28. No "cute"/"clever" notation; **never name new terms after yourself** (adopt the eponym only after others make it common usage).
29. **Three-use rule**: an expression used ≥3 times deserves notation; used once, it doesn't. Invest in notation to make crucial theorem statements clean.
30. Bland names ("good", "bad", "Type I/II") for peripheral/technical terms; colorful names sparingly, only for central concepts.
31. TeX macro per tentative notation, used exclusively, so late renaming is one edit.
32. Rigorous components: precise, unambiguous notation. Non-rigorous components: ambiguity flagged with scare quotes / "roughly speaking" / "essentially." Abuse of notation permitted if pointed out.
33. a/bc is ambiguous — parenthesize or \frac; \frac (conspicuous) for important fractions, / for minor ones; ÷ avoided entirely.
34. Quietly reinforce conventions ("the vector space V"); modulate terminology to emphasize the relevant aspect of an object.

## Give appropriate amounts of detail
35. **Dwell at length (plenty of English) on the most important, innovative, crucial components; be brief on routine, expected, standard ones.** (Littlewood: let the reader "catch on at once to the momentary point and take details for granted.")
36. Well-known lemma already in the literature: don't reprove it. Conversely, material YOU know well but the field doesn't must be expounded in detail "even if these details are 'obvious' to you."
37. Obscure lemma from prior work: state it in full with precise citation — not "by a lemma in [my previous 100-page paper]". If crucial, sketch its proof or remark on its significance.
38. Calibrate to experts in the field: components must be interesting to them, not just to yourself.

## Don't over-optimise
39. Perfectionism hits diminishing returns; strengthening a lemma can lengthen its proof and obscure its role.
40. Don't optimize for hypothetical future users — only when a known subsequent paper relies on it.
41. Shortness by removing "all examples, remarks, whitespace, motivation, and discussion" is a poor tradeoff. **"Optimising the readability of the paper is always a good thing (except when it is at the expense of rigour or accuracy)."**

## Create lemmas
42. Encapsulate intermediate facts as lemmas to signal reusability: sub-steps buried inside a proof "can be safely forgotten"; the lemma statement is the reusable unit. Experts can read the statement, find it plausible, and move on.
43. "For the experts" remarks after lemma proofs: alternate proofs, refinements, special cases, connections.
44. Localise special-purpose notation inside lemma proofs (information hiding); lemma statements explicitly recap running hypotheses/assumptions/conventions.
45. **Write lemma statements to be "easy to use, rather than easy to prove"** — natural verifiable hypotheses, manifestly useful conclusions; push details INTO the lemma to simplify the surrounding argument.
46. Two technical lemmas useful only together → combine into one lemma whose proof encapsulates the technicality; long proofs → promote to a proposition with its own section, deferred with "We will prove this proposition in Section X."

## Write a rapid prototype first
47. First a skeleton: key lemmas/propositions/theorems/definitions with omitted or informal proofs; big picture (logical organisation) before details; fuzzy statements enable easy reorganisation.
48. Second pass: make statements precise; carefully write key portions to verify the structure works; routine proofs last; defer decisions that don't affect the big picture (write "let δ := ???").
49. Stub ideas as they arise rather than developing them mid-section; introduction written LAST; version control for collaborations.

## Write professionally
50. Johnson (quoted): "Wherever you meet with a passage which you think is particularly fine, strike it out."
51. The majority of the paper objective and factual; informal remarks/opinions clearly labeled and placed in footnotes or a remarks section.
52. "Overly philosophical, witty, obscure or otherwise 'clever' comments should generally be avoided" — they may not seem clever in ten years and can irritate the very readers you want.
53. Required apparatus: properly formatted title, abstract, introduction, bibliography; math papers have no "Conclusions" section (use "Further remarks"/"Open questions"); references current, covering all recent related work, cited in text "giving an accurate assignment of credit, provenance, and precedence."
54. TeX/LaTeX is the standard format; spelling and grammar checked ("careless or incorrect use of English … conveys the impression that the paper itself is also careless and incorrect"); but don't over-polish — it's a paper, not literature.
55. **Every argument central to the main results must be backed by rigorous proof (or rigorous numerics)** — unless already in the literature or very standard, in which case cite and describe the necessary modifications.

## Write in your own voice
56. Adopt universal methods of great writers, never their individual manner; develop a consistent personal voice — mimicry reads as offensive, not flattering.
57. **Never copy paragraphs from prior papers except as attributed direct quotation ("As Bourbaki [17, p. 146] writes…")** — otherwise paraphrase, update, simplify, and add insight; if tempted to copy without adding novelty, just cite ("See [27, Section 4]").
58. Legitimate reproduction: historical tracking, rescuing arguments from obscure/unavailable papers, motivating later parts — always attributed ("The proof here is loosely based on that in [5]"; "This discussion is inspired by a related discussion in [10]").
59. If you can't explain a subject except by copying prior work, "internalise the subject further."
60. Priority-uncertainty caveats: "to the author's knowledge, this observation is new."
61. No quotation-dropping from famous mathematicians to look impressive; motivation should not rest primarily on appeal to authority — a handful of citations demonstrating interest suffices.
62. Collaborations: harmonize styles through editing rounds; consult coauthors before major edits of their text.

## Take advantage of the English language
63. "Just because you CAN write statements in purely mathematical notation doesn't mean that you necessarily SHOULD" — English conveys contextual cues notation cannot.
64. Modulate emphasis to signal how a statement interacts with the argument: word choice signals equal/complementary/auxiliary importance; connectives ("also", "but", "since") show fit; subject choice decides whether objects or properties are the actors.
65. No fancy/obscure vocabulary — it "can be mistaken for technical mathematical terminology"; "the primary purpose of mathematical writing is to communicate and inform, not to impress."
66. Terse notation IS right for tedious standard formal computations — flag them as standard beforehand so the reader expects no surprises.

## Proofread and double-check before submission
67. Submit a final draft, not a first draft; errors found after submission tie up months; trivial spelling errors convey an unprofessional first impression; quality is the author's job, not the editor's/referee's.
68. **Citations get particular scrutiny**: an important relevant reference mentioned only tangentially, cited inaccurately, or omitted alienates exactly the experts likely to referee; "when in doubt, don't hesitate to look up primary sources to double check that the citations are being handled properly."

## Hub one-liner
69. "Make your past self your target audience" — write for the person you were before you did this work.
