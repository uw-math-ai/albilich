# MAURER — Stephen B. Maurer, "Advice for Undergraduates on Special Aspects of Writing Mathematics" (PRIMUS 1(1) 1991, 9-17; fetched 2026-07-08 via Swarthmore Works/Wayback, 19pp read in full) + "Common Errors in Writing Mathematics" handout (3pp, from his Short Guide page)

Note: the full "Short Guide to Writing Mathematics" manuscript is deliberately NOT publicly distributed (author restricts circulation to personal contact); the PRIMUS article is its published core and is expressly reproducible for teaching. His framing: "mathematics has many special formats that are not mere technical conventions but instead serve important purposes" — every rule below comes with a WHY.

## Reader model & apparatus
1. Know your reader: assume a student with your background who doesn't know this topic; points hard for you will be hard for them — explain with whatever approach finally worked for you. "Just throwing down some cryptic calculations won't work!"
2. Readers re-read: they refer back to definitions/theorems/examples repeatedly, so key elements must be findable — highlight and number them.
3. Title: every paper has one, informative without being too long; beware titles hinging on concepts defined only inside the paper (they convey nothing).
4. Introduction: every paper has one (a paragraph suffices in short papers); the reader "deserves to be informed of what she is getting into and why she should care"; give a rough idea of key concepts (admit it's rough) and what you'll do with them.
5. Sections for papers > 4-5 pages; intro briefly describes each section; **each section starts by reminding the reader what it's about, how it fits, why it's there** — guideposts for the reader AND a self-test for the author ("Writing them will force you to think hard about — and then maybe revise! — what you are trying to do").

## Theorems & levels of confirmation
6. Highlight theorems (indent/vertical space): "formal statements of theorems serve as touchstones, like having an outline within the text body." Indicate clearly where each proof begins and ends.
7. **Prove/verify/show/illustrate are distinct levels of confirmation**: "prove" = airtight argument harking back to definitions; "verify" a theorem = prove it, but verifying a numerical claim is weaker; "show" is looser; "illustrate" = examples. Computing (d/dx)4x² = 4(d/dx)x² after stating the constant-multiple rule ILLUSTRATES it; proving it from the definition proves a special case. Definitions cannot be proved (they are conventions) — only illustrated. "Sometimes good examples will do more to help the reader understand and believe a result than a complete proof will."

## Definitions
8. Math defines both words AND notation (notation because "if you use a new concept frequently, you need a shorthand way to refer to it or you will tie yourself in verbal knots").
9. In-line definitions highlight the definiendum (boldface preferred; italic/underline acceptable); display-format definitions reserved for the most important ones (derivative yes, polynomial no).
10. **After defining w: (a) never use an English synonym w′ as if it had the same precise meaning** (defining "slope" then writing "steepness" sends the trained reader hunting for a definition of steepness — they assume two different refinements are intended); **(b) never use w itself in its loose English sense** ("critical point" defined as f′=0 forbids "points where concavity changes are critical to graphing").
11. Local vs global definitions: local ones ("Let f(x) = x²", rebindable a few paragraphs later) need no highlighting; **the item being defined always goes on the LEFT of the equals sign** ("Let x² = f(x)" is wrong — a "let"-equality assigns right to left, unlike symmetric equality).

## Examples & figures
12. A good expository paper has MORE examples than definitions and theorems; lengthy/key examples displayed and numbered; sample problems mark where the solution begins and ends.
13. Figures numbered, inserted shortly after first reference (or all at the end — but then say so at first reference), usually captioned with a content-bearing caption ("The steeper the line, the greater the slope").

## Big little words (the logic-bearing vocabulary)
14. **"Let" vs "suppose"**: "let" sets forth a convention that is up to us (usually a symbol); "suppose" introduces temporary hypotheses. "Suppose f′(x) > 0 for x < a" (case analysis) is correct where "Let f′(x) > 0" would be wrong — "we don't really have control over the sign of f′(x)."
15. **"Thus"/"so" assert logical consequence of the PREVIOUS clause**: if the next sentence would still make sense and be true without the previous one, it may not begin with thus/so. Correct: "Let x = 1 and y = 2, so x + y = 3." Incorrect: "Let f(t) be the temperature at time t. Thus f′(t) = lim…" (temperature has nothing to do with why the derivative is defined that way).

## Credit & citation (the mathematics "philosophy of references")
16. Direct and almost-direct quotes must be credited; paraphrase generally need not be — because mathematics "is regarded as having an existence independent of the words used to describe it." Don't cite your textbook for the Chain Rule or the definition of derivative.
17. Descriptive theorem names (Chain Rule) are common property; **sequential names (Theorem 6, Limit Rule II) are text-specific — using one requires a reference with page number, and better: just restate the rule.**
18. Recent results: the original paper MUST be referenced. Classical results (300 years old): no original-publication references outside history papers.
19. Borrowed examples: credit only if exact words or exact numbers are reused — "in general you shouldn't be using problems verbatim anyway … if you have internalized it, you can recreate it, no doubt with different numbers."
20. Single dominant source: acknowledge once near the beginning ("In writing this paper, I have drawn heavily on Goldstein et al. [1]").

## Typography of mathematics
21. Math letters italic (or, in plain media, spaced) to disambiguate from prose ("So the answer is 4pm" — only italics says 4·p·m, not 4 o'clock).
22. Spacing as structure: tight spacing inside inner groups, wide spacing between outer layers — Δy = f(x+h) − f(x); "mathematical expressions often have several layers."
23. **Font consistency: mathematics is font-sensitive and case-sensitive** — the same letter in different fonts/cases means different things (x data value, x̄ average, X random variable); never drift fonts for one symbol. Never capitalize a variable to start a sentence — recast ("Quantity a is positive because…").
24. Fractions: shilling form a/b in-line for simple fractions; parenthesize compound numerators/denominators — (y₂−y₁)/(x₂−x₁); brackets outside parens: [f(x+h) − f(x)]/h; **sufficiently complicated fractions must be built-up, never shilling** (his monster example declared unwritable in-line "even though it is correct").

## Displays
25. Display any long/tall/important expression (three reasons: emphasis; tall symbols don't fit in-line; expressions don't bear line breaks). Breaking y′ = d/dx(x² + 3x) after "+" is bad form, after d/dx terrible, after "=" bad according to some.
26. Number a display iff referred to from afar ("the third display on page 7" is unusable and breaks under repagination).
27. Multiline displays align on the main connective (=, ≤, ⟹). Both-sides-per-line format (2x+1 = 2+3 / 2x = 4 / x = 2) means "the same thing done to both sides"; right-side-only format (x²+2x < x²+2x+1 / = (x+1)²) means "each expression obtained from the previous EXPRESSION" — the formats carry different semantics; no comma after lines of right-side-only chains.
28. **Displays are clauses of sentences and take punctuation**; Maurer: commas negotiable, "I do feel strongly about the period" — the period signals "stop and digest; figure out for yourself why the display is legitimate"; its absence says "keep reading." **End-of-display punctuation is a reader cue, not decoration.** (He notes ~half of US publishers use the no-punctuation convention — record as convention fork.)
29. **Explain your displays**: elementary algebra needs no commentary, but complicated calculations need words before/between/after the lines, OR bracketed side-comments per line ([def. of f(x)] / [expand] / [combine terms] / [divide]); long lines put the comment on the line below. "To display the four lines of algebra without any explanation is unacceptable to me."
30. **Displays should contain verbs** (usually =): "f′(x) = lim…" beats a bare "lim…" expression, and a displayed Definition block beats both — the reader referred back to it sees WHAT KIND of statement it is (the three-version derivative example: bare expression < equation < labeled Definition).

## The two balancing mistakes (§15)
31. Mistake 1 — too few symbols: name recurring objects (let f(x) = x²; "for any function f(t)…"); when working toward a precise formula, state it EARLY, even before all symbols are explained — "otherwise you bog down in vague verbiage."
32. Mistake 2 — too many symbols: several lines of computation without commentary.
33. Number all pages.

## Common Errors handout (function/equation/expression discipline)
34. **Equation vs expression vs function**: an equation states two things are equal (has a verb — =, ≤, …); an expression is symbolism without a verb; a function is a process taking inputs to outputs. "A function is an equation" is FALSE — a function is DEFINED BY an equation.
35. f denotes a function; f(3) is a value — "do not refer to the function f(3)"; "the function f(x)" is technically wrong but accepted (dummy variable); best: "the function f" or bare "f(x)".
36. There is no "equation of f" — there is a DEFINITION of f ("the statement that starts with Let"). Prefer "to evaluate f(2x−1), substitute 2x−1 for the dummy variable x in the definition of f."
37. "Given the function x + 10" is wrong (x+10 is an expression); write "Let f(x) = x + 10. Evaluate f(4)." — "the notation carries the day. Notice that the best version is also the shortest."
38. "Solve for f(3)" is wrong — evaluation is not solving (solving = isolating an unknown, as in "find x if f(x) = 3"). "Complete the function" is wrong — say "simplify."
39. "Plug y−1 into g" is already done by writing g(y−1); what remains is substituting into the right side of the DEFINING equation.
40. "Function notation," not "functional notation" ("functional" already means something else).
