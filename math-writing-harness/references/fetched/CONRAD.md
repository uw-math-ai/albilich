# CONRAD — Keith Conrad, "Advice on Mathematical Writing" (fetched 2026-07-08, kconrad.math.uconn.edu/blurbs/proofs/writingtips.pdf, 10pp, read in full)

Format credit: the Bad/Good format is inspired by Knuth-Larrabee-Roberts [1].

## §1 Notation
1. Do not begin sentences with a symbol.
   - Bad: "2^√2 is irrational." Good: "The number 2^√2 is irrational."
   - Bad: "Let n be an even number. n = 2m for some m ∈ Z." Good: "… Thus n = 2m for some m ∈ Z." / "…, so n = 2m for some m ∈ Z."
   - Bad: "One solution is f(x) = sin x. f(x) is periodic." Good: "… In this case, f(x) is periodic."
2. Two symbols not part of the same expression should not be adjacent without words or grammatical marks between them.
   - Bad: "If n ≠ 0 n² > 0." Good: "If n ≠ 0 then n² > 0."
   - Bad: "Consider x_k 1 ≤ k ≤ n." Good: "Consider x_k for 1 ≤ k ≤ n." / "… where 1 ≤ k ≤ n." / "… for k = 1, …, n."
3. When introducing notation, make it fit the context; often common sense.
   - Bad: "Let m be a prime." Good: "Let p be a prime."
   - Bad: "Let X be a set, and pick an element of X, say t." Good: "…, say x."
   - Bad: "Pick two integers, say a and x." Good: "say a and b." / "say a and a′."
4. Always define new notation (is it a number? a function? of what type?) and be clear about its logical standing.
   - Very bad: "Since n is composite, n = ab." Bad: "…, n = ab for some integers a and b." Good: "…, n = ab for some integers a and b greater than 1." [Every integer is a product, since n = n·1, so n = ab alone introduces no constraint.]
   - Bad: "If a polynomial f(x) satisfies f(n) ∈ Z, does f(x) have integer coefficients?" Good: "… satisfies f(n) ∈ Z for every n ∈ Z, …"
5. Do not give multiple meanings to a variable in a single argument.
   - Bad: "suppose a and b are even. Then a = 2m and b = 2m, for some integer m." [proves sum of two evens is a multiple of 4 — nonsense]. Good: "a = 2m and b = 2n, for some integers m and n."
6. Avoid overloading meaning into notation.
   - Bad: "Let x > 0 ∈ Z." Good: "Let x be an integer, with x > 0." / "Let x be a positive integer."
7. Z, Q, R, C denote the sets of ALL integers/rationals/reals/complexes; never an individual number.
   - Bad: "Let C be a complex number." Good: "Let z be a complex number."
8. NEVER use logical symbols ∀, ∃, ∧, ∨ in writing, except in a technical paper on logic. Write the words.
   - Bad: "The conditions imply a = 0 ∧ b = 1." Good: "…imply a = 0 and b = 1."
   - Bad: "If ∃ a root of the polynomial then there is a linear factor." Good: "If there is a root …"
9. ∀ means "For all"/"For every", not "All"/"Every" (when read aloud in the bad usages).
   - Bad: "∀ square matrices with nonzero determinant are invertible." Good: "All square matrices with nonzero determinant are invertible."
   - Bad: "In the complex plane ∀ complex number has a square root." Good: "… every complex number has a square root."
   - Bad: "…then they agree at ∀ points." Good: "… at all points."
10. Avoid silly abbreviations, misuse of standard notation, and blackboard-only abbreviations (WLOG, s.t., iff).
    - Bad: "When n is ∫, 2n is an even number." Good: "When n is integral/an integer, …"
    - Bad: "Let z be a C." Good: "Let z be a complex number." / "Choose z ∈ C."
    - Bad: "WLOG, we can assume x > 0." Good: "Without loss of generality, we can assume x > 0."
    - Bad: "There is a point x s.t. f(x) > 0." Good: "… such that f(x) > 0."
11. If a piece of notation is superfluous, don't use it.
    - Bad: "Every differentiable function f is continuous." Good: "Every differentiable function is continuous." [Keep A in "A square matrix A is invertible when det A ≠ 0" because A is used again in det A.]

## §2 Equations and expressions
1. Don't confuse *equation* (anything of the form A = B) and *expression* (notation not involving a relation; x² − 3x + 4 is an expression, not an equation).
2. Display important equations on their own line; label (2.1) only if referred to later; nearby references may say "by the above equation."
3. Multi-step computations (especially >2 steps) go in stacked form, aligned on the relation, with the left side NOT repeated on each line.
   - Bad: repeated "(x+1)³ =" on each stacked line. Good: single left side, aligned "=" continuation lines.
4. Equations do not stand by themselves: they are part of a sentence and punctuated accordingly. Period if the equation ends the sentence; comma if a natural pause follows; sometimes no punctuation. Never a lone period on the next line.
   - (Also: italicize the term being defined, e.g. *critical point*; some books use bold.)

## §3 Parentheses and commas
1. Avoid irrelevant parentheses: "(x+y)(x−y) = x² − y²" not "= (x² − y²)"; "factor of a₁a₂⋯aₙ" not "(a₁a₂⋯aₙ)"; "factor of p − 1" not "(p − 1)". Superscript exponents with correct parenthesization: "(−1)^(n−1)" not "−1^(n−1)" ambiguity [Taylor series example].
2. Use parentheses to disambiguate subtraction vs negative sign: Very bad "(a+b) − c = −ac − bc"; Bad "(a+b) · −c"; Good "(a+b)(−c) = −ac − bc."
3. Commas mark brief pauses; read text mentally to catch badly placed commas.
   - Bad: "The condition we want is, a = 2b." Good: "The condition we want is a = 2b."
   - Bad: "The set is infinite, we pick a large finite subset of it." Good: two sentences.
4. "If …, then …" is fine; "Let …, then …" with a comma is bad English.
   - Very bad: "Let n be an even number, then n = 2m for some m ∈ Z." Good: "Let n be an even number. Then …" / "…, so n = 2m …"

## §4 Use helpful words
1. Tell the reader where you are going: "We will prove this by induction on n." "We argue by contradiction." "Now we consider the converse direction." "The inequality a ≤ b is strict: a < b. Indeed, …"
2. Use key reasoning words: since, because, on the other hand, observe, note. At the same time, vary word choice to avoid monotony (may require rewriting a paragraph).
   - Bad: chain of "Then … Then … Then …" Good: "Then, by successively applying the result we proved to a⁴, a², and a, we see that a is even."

## §5 English grammar
1. Punctuate ordinary sentences correctly (commas, periods, colons, semicolons, apostrophes). "it's" = "it is"; "its" = possession.
   - Bad: "It's clear that f(x) has a real root since it's degree is odd." (second it's wrong) Good: "… since its degree is odd."
2. Avoid sentence fragments and run-ons.
   - Bad: "How to describe rotations in R³." Good: "We will explain how to describe rotations in R³."
   - Bad (run-on): "The new concept we will use is a Markov chain, it is a process where…" Good: split, or "…, which is a process where…"
3. Verb tenses consistent; mathematical facts in present tense ("always valid").
   - Bad: "In 1873, Hermite proved that e was transcendental." Good: "… proved that e is transcendental."
   - Bad: "Some day I expect e + π will be irrational." Good: "… will be proved irrational."
4. Singular/plural noun-verb agreement: "The set of real numbers is uncountable" (the set is), or "The real numbers are uncountable."
5. Spelling: its/it's; "necessary"; "discriminant" vs "discriminate"; "counterexample" (one word); "straightforward" (one word).
6. Don't repeat the same long word in a sentence or start successive sentences with the same phrase.
   - Bad: "It is possible to show that all possible rational numbers can be enumerated." Good: drop one "possible."
7. Paragraph boundaries: don't END a paragraph with the lead-in to the next ("For example, √2 is irrational" belongs at the START of the paragraph that explains it).
8. Use parallel structure.
   - Bad: "…rational and irrational numbers, as well as into algebraic numbers and transcendental numbers." Good: "… algebraic and transcendental numbers."
9. Don't repeat definitions unnecessarily (π defined once).
10. Avoid informal language: "mind-boggling" → "surprising"/"striking."

## §6 Types of mathematical results
- Theorem = main result; lemma = used to prove a theorem, not independently interesting; corollary = follows from a theorem. Order: Lemma, Theorem, Corollary. A string of lemmas leading to no theorem looks strange.
- Numbered result references are capitalized: "by Theorem 2.1", "from Lemma 6.3" — but "by the previous theorem", "in the next lemma" (lowercase). Same for "Section 2" vs "the next section".
- Proofs start with *Proof* and end with □. A proof environment must FOLLOW an official statement of what is being proved.
- "The number √2" not "the √2".
- Don't put part of a proof within a theorem statement. Bad: "Theorem. The number √2 is irrational, and it can be proved by contradiction."

## §7 Definitions
- A definition is a description of a new word, not a theorem; the defined term goes in italics (or bold).
- A "definition" asserting a computed fact (e.g. "the limit of {aₙ+bₙ} is A+B") is a RESULT, not a definition.
- Properties of the defined object belong AFTER the definition, not inside it (e.g. closure under addition doesn't belong in the definition of rational).
- Examples belong after the definition, not inside the definition environment.

## §8 Fonts
- Single-letter variables italic (math mode): "Let p be a prime", not roman p. Every individual mathematical letter in prose is math-mode italic.
- Single function letters italic: f(x), e^x — not roman f(x); F_n not roman.
- Numbers are NEVER italic: x² − 3x + 1 (roman digits); a ≠ 0; "…the prime from Theorem 2.1" (the 2.1 roman even in italic theorem text).
- Theorem/lemma/corollary statements are italicized BY THE ENVIRONMENT; do not force italics manually.
- Multi-letter function names roman: sin θ, cos α, log t (use the LaTeX commands).
- Definitions/examples not in italics except the term being defined.

## §9 LaTeX tips
- Escape %/underscore/~ in URLs properly; use tex.stackexchange.
- Left double quotes: `` not " (else "here" comes out wrong).
- Multiplication is · or juxtaposition (x·y or xy); × in limited circumstances; NEVER x∗y or x*y.

Reference [1]: Knuth, Larrabee, Roberts, "Mathematical Writing", MAA 1989.
