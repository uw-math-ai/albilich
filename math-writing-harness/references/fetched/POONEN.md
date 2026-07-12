# POONEN — Bjorn Poonen, "Practical Suggestions for Mathematical Writing" (fetched 2026-07-08, math.mit.edu/~poonen/papers/writing.pdf, dated Jan 6 2026, 65 rules, read in full)

## §1 Important things
1. If a claim does not follow immediately from the previous sentence alone, explain what it does follow from. Good: "Combining the previous two sentences shows that…", "By Lemma 8.3, …"
2. If a sentence contains more than one claim, make clear which reason justifies which claim (reason before/after a chain of equalities, or align* with a reason at the right of each line).
3. A reader reaching the period of a sentence should know why each claim up to that point is true. If a proof comes only after, say so ("…, as we now explain") or use lemma/proof environments.
4. It is not enough that words CAN be given the intended meaning; write so they cannot reasonably be given any other meaning. Eliminate even a minute of confusion.
5. Break up long arguments into lemmas, even single-use ones; minimize what the reader must keep in mind at once.
6. If a section has several results but only one is needed later, say so (frees the reader's memory).
7. Make quantifiers unambiguous. Bad: "We have x²+1 ∈ S for x ∈ R." (worse with comma). Good: "for all x ∈ R." / "for some x ∈ R."
8. Proofs should usually indicate where the hypotheses are being used.
9. When citing a book or article, include a theorem number or page number (omit only when citing the entire work).
10. Cite the published version instead of a preprint, if published (except when citing something only in the preprint).
11. When citing an arXiv preprint, include the version number or precise date; for other web preprints, URL + date.
12. Cite "forthcoming work" only if a publicly available preprint exists (AMS ethics: announcements can discourage others from working on the problem).

## §2 Title, abstract, introduction
13. Title, abstract, introduction, body: each describes the entire article, each less abbreviated than the previous; each written as if the reader will not look at what comes after.
14. The title must be long enough to convey the topic and specific enough to distinguish the article ("A class of polynomials" is a bad real title).
15. Omit "A note on"/"Remarks on" from titles.
16. The abstract should state the main results if they fit in a few lines (definitions often omitted for space).
17. The abstract should be self-contained; no citations or references to the body.
18. The introduction should get to new and interesting theorems as soon as possible; postponing standard definitions to a Notation section is fine.
19. Mathematics papers usually do not have a conclusions section.

## §3 Other things
20. Keep theorem statements short; definitions PRECEDE the theorem using them.
21. Keep sentences short; combine only when it clarifies logic or the sentences are closely related.
22. String several equalities into one chain (in correct order!) when possible; transitivity is easy to follow. Same for inequalities.
23. If a proof breaks into parts, do the easier parts first.
24. When claiming two objects isomorphic, specify the map explicitly (at least one direction) and claim THAT map is an isomorphism.
25. Start induction at n = 0 instead of n = 1 if easier.
26. "Clear" usually means the author couldn't explain it (sometimes because it's wrong!). If really clear, saying so is unnecessary; if not clear, give a few words of reason.
27. Minimize ", where…" constructions (explanation after use); define variables BEFORE they are needed.
28. The subject of a sentence cannot be words + a fraction of a formula. Bad: "the discriminant [display] Δ = b²−4ac." Good: "the discriminant Δ equals b²−4ac."
29. "We now prove the following proposition." adds nothing; text that explains meaning or purpose is useful.
30. Do not use abbreviations WLOG, iff, s.t. (blackboard only, if at all).
31. Do not use logical symbols ∃, ∀ unless writing about formal logic and inside a logical formula; write "there exists" etc. [CMOS 12.5]
32. Do not start a sentence with a symbol [CMOS 12.7]. Bad: "H denotes the Sylow p-subgroup of G." as a full sentence.
33. Avoid contractions ("don't") in formal writing.
34. Do not use proof by contradiction when a direct proof is just as easy.
35. Refer to theorems by NUMBER, not "the previous theorem"/"the proposition above". [NOTE: conflicts with CONRAD §6 which allows "by the previous theorem" lowercase — record both; prefer Poonen for papers, numbered references.]

## §4 LaTeX issues
36. Single numbering system for all theorem-like environments (\newtheorem{lemma}[theorem]{Lemma}), so no Theorem 1.1 AND Lemma 1.1 coexist; prevents citation errors.
37. \DeclareMathOperator{\Gal}{Gal} for upright operator names (Gal(L/K) not italic).
38. \hfill before \begin{enumerate} in theorem statements to fix first-item alignment.
39. f \colon X \to Y (not f : X \to Y) for correct spacing.
40. \usepackage{fullpage} to avoid manual margins.
41. \usepackage{microtype} just before \begin{document} (fewer bad line breaks).
42. \usepackage{colonequals}; \colonequals for := (spacing).

## §5 Nitpicks
43. "so that" conveys purpose (replaceable by "in order that"/"with the result that"); "such that" imposes a condition. Good: "We include 0 in N so that N contains the size of every finite set." Bad: "An abelian group is a group so that every two elements commute."
44. For plain implication write "A, so B" — not "A, so that B" or "A, and so B".
45. Semicolon (or colon if explanatory) joins two sentences; a bare comma does not; "therefore/hence/thus" don't change that. Coordinating conjunctions (and, but, so) CAN join with a preceding comma. "A, hence B" is wrong; "A, so B" and "A; therefore B" are correct.
46. Place "only" as close as possible to what it modifies [Kil07].
47. "Given an element g of G", not "Given g an element of G".
48. What follows "Let" is the variable being defined: "Let Z be the center of G", not "Let the center of G be Z".
49. Capitalize "Theorem" when referring by number: "By Section 3.4 and Theorem 5.6"; lowercase for named possessives: "By Faltings's theorem".
50. Displaying a formula does not change required punctuation: "By Theorem 3.2, we have [display]." (period after display; no colon before if grammar doesn't need it).
51. "Assume that G is a finite group." (add "that"); "Assume Hypothesis A."/"Assume n ≥ 1." are OK (noun units). Same for "Suppose". [Wes15]
52. "the 1980s", not "the 1980's" [CMOS 9.34].
53. "i.e." and "e.g." followed by a comma (American English); preceded by semicolon if joining full sentences.
54. Minimize parentheses: log x better than log(x); sin 2x; but sin(x+y) needs them.
55. Juxtaposition for multiplication: (n+1)(n+2), not (n+1)·(n+2) or ×; but 3·7 when both factors are numerals.
56. Omit filler "We remark that"/"Note that", EXCEPT when needed to avoid starting a sentence with a symbol.
57. With an end-of-proof symbol, don't also write "This concludes the proof."
58. Fractions in exponents/subscripts use slash: x^{3/2}, not stacked.
59. Sequences use parentheses: (a_i)_{i≥0}, not {a_i}_{i≥0} (like tuples vs sets).
60. "principal" = main (principal results, principal ideal); "principle" = rule/law (maximum principle).
61. Spelling: separable (not seperable); archimedean (not archimidian); homogeneous (not homogenous, in math contexts).
62. No hyphen after "non" in common words: nonempty, nonnegative, nonsingular, nontrivial, nonzero [CMOS 7.85].
63. Most numbers in math papers as numerals; exception: single-digit counting numbers may be words ("These two genus 2 curves are isomorphic").
64. Prefer "since" to "as" for causation ("As x does not tend to +∞, e^x is bounded" is egregious).
65. Do not use "per" for "by".

References cited: [CMOS] Chicago Manual of Style 16e; [Kil07] Kilpatrick on "only"; [Wes15] Douglas West, "The grammar according to West" (math.illinois.edu/~dwest/grammar.html — a further authoritative source worth consulting).
