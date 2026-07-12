# AMS-STYLE — AMS Style Guide: Journals (Letourneau & Wright Sharp, Oct 2017) (fetched 2026-07-08, 160pp PDF; Ch. 4, 12, 13 read in full — copyeditor mechanics distilled to author-checkable rules)

The AMS's internal copyediting manual for its journals (base authority: Chicago Manual of Style 16th ed.; *Mathematics into Type* for math typesetting). Rules below are recast from copyeditor instructions ("mark…", "stet…") into checkable constraints on the author's manuscript. "Stet if consistent" becomes "either form acceptable; must be consistent within the paper." Items tagged (AMS house style) are AMS-journal conventions that other venues may not share; untagged items are good general practice. Bad/Good pairs are quoted from the guide (✗ = marked incorrect there, ✓ = correct); pypdf extraction artifacts in math have been repaired to readable inline form.

## Ch. 2 — Top matter and end matter (author-checkable subset)

1. Title: capitalize only the first word, the first word after a colon, and proper nouns (as it will appear in contents/indexes; the journal format may render it all-caps). (AMS house style)
2. Title: math variables lowercase in the text must stay lowercase in the title; spelling/hyphenation/dashes in title, running heads, abstract, and section heads must match the body.
3. No footnotes in the title or the author line.
4. Author line: space between initials ("V. A. Sohinger", not "V.A. Sohinger"); period after each initial of an abbreviated hyphenated name ("Y.-N. Lee", "J.-P. Serre"); comma before "and" with three or more authors ("Author One, Author Two, and Author Three").
5. The abstract must stand alone: no citations of the paper's bibliography by number, no references to the paper's numbered elements (theorems, equations), and no numbered displays (unnumbered displays, multiple paragraphs, and lists are fine).
6. Abstract citations must be rewritten as self-contained bracketed references, e.g. "Matsusaka and Osanai [Proc. Amer. Math. Soc. 145 (2017), pp. 1383–1392]" for articles; for books give title (italic), publisher, location, year. (AMS house style)
7. Any acronym spelled out in the abstract must be spelled out AGAIN at first use in the body; first-person active voice is acceptable in the abstract (do not reword to passive).
8. Suggested abstract length: ~150 words for short papers, ~300 for long ones (not strictly enforced). (AMS house style)
9. MSC footnote format: "2010 Mathematics Subject Classification. Primary 68Q25, 68R10; Secondary 68U05." — at least one Primary; no verbal descriptions of the codes. (AMS house style)
10. Key words footnote: first word and proper nouns capitalized, all else lowercase, comma-separated, ends with a period. (AMS house style)
11. Grant footnotes: refer to "The second author" (never the author's name, since footnotes on author names are not permitted); past tense ("was partially supported by…"); funder acronyms (NSF, ERC) need not be spelled out. Thanks to colleagues/referees go in the Acknowledgment section, not the grant footnote.
12. The section is spelled "Acknowledgment" (no "e" after "g"); head is "Acknowledgment" for one, "Acknowledgments" for several; the section is unnumbered. (AMS house style)
13. Acknowledgments: first person plural is fine, but keep the voice parallel — ✗ "The authors acknowledge the help of Dennis Staudinger and Alex Hands. We also thank T. Setser for valuable comments." (mixes "the authors" and "we").
14. Affiliations: one per author, in byline order, repeated even if shared; spell out U.S. states and Canadian provinces; country last for non-U.S.; AMS prefers "Department of Mathematics" over "Mathematics Department". (AMS house style)
15. Dedication (if any): italic, centered, no terminal period. (AMS house style)

## Ch. 3 — Section and subsection heads

16. All headings use sentence-style capitalization: first letter capped, rest lowercase except proper nouns; also capitalize the first letter after a period or colon within a heading ("3. Results: The discrete Heisenberg group"). (AMS house style)
17. Section heads take NO period at the end; subsection heads ALWAYS end with a period and the text runs in on the same line (unless another heading or enunciation follows).
18. Subsubsection heads: arabic number roman, title in italics, followed by a period, text run in ("3.1.1. Basic properties of outer Lp.").
19. Math is permissible in heads but displays are not; math in a head stays in math mode (not bolded/fonted to match the head); no underscoring in any head.
20. A citation inside a subsection head goes at the end, in parentheses, before the period: "1.1. Applications ([1])."
21. Sections are numbered with arabic numerals 1, 2, 3; subsections within sections (3.1, 3.2); subsubsections 3.1.1, 3.1.2. Roman-numeral section numbers should be converted to arabic (roman numerals allowed only for Parts of very long manuscripts).
22. An introduction numbered 0: delete the "0" from the head but do NOT renumber other sections or equations (equation numbers (0.1) etc. stand). Acknowledgments, Note added in proof, About the author, and References sections are never numbered.
23. Check numbering for gaps and duplications; any consistent numbering system is allowed (sequential (1),(2) or by-section (1.1),(1.2)), but it must be consistent and all cross-references correct.
24. Cite multiple sections as "see sections 2.3 and 4.2", NOT "see section 2.3 and section 2.4"; every section callout must include the word "section" (or "§" if used consistently); AMS prefers lowercase "section" (initial-cap allowed only if used consistently). (AMS house style)
25. Title/heading line breaks (display titles): break before prepositions, articles, or conjunctions, or logically around phrases; avoid a single word on the last line.

## Ch. 4 — Enunciations

26. Four enunciation styles. Theorem style (bold "Theorem 3.1." head, ITALIC text): Theorem, Lemma, Sublemma, Proposition, Corollary, Conjecture, Criterion, Assertion, Axiom, Hypothesis, Reduction, Algorithm (mathematical). Definition style (bold head, ROMAN text): Definition, Example, Exercise, Problem, Question, Condition, Convention, Assumption, Fact, Property, Terminology, Model, Application, Affirmation, Discussion, Scholium. Remark style (ITALIC head + roman number, roman text): Remark, Note, Notation, Claim, Case, Subcase, Step, Observation, Comment, Conclusion, Summary, Answer, Base. Proof style (italic "Proof." head, roman text): Proof, Subproof. (AMS house style)
27. Numbered enunciations are proper nouns: spell them out in full ("Theorem 2.1", "Definition 2.1", "Remark 3") — abbreviated forms ("Thm. 2.1", "Def. 2.1", "Rem. 3") are not allowed EXCEPT inside a bracketed citation ("[11, Thm. 2.1]").
28. Unnumbered enunciations are acceptable only when few; never two unnumbered theorems (or two of any one category) in a single work.
29. Proofs end with a QED box, flush right on the last line of the proof; it may fall on its own line after a full line of text, a display, or a list.
30. Enunciations of non-theorem categories normally carry no proof; a claim (or similar) that carries a proof may need to be promoted to theorem style — flag such cases.
31. Attribution/citation in parentheses after a numbered enunciation heading is lightface roman, parentheses included: "Lemma 2.2 (Hamilton and Burr, [7])." — contrast with subsection heads, where the head (but not the citation) is all bold: "2.1. Carleson embeddings (Schuyler, [7])." (AMS house style)
32. Algorithms that are mathematical items are set as theorem-style enunciations; algorithms that are computer code (Input/Output, numbered code lines) take a separate code format — don't mix the two.

## §12.1 Basic editing (consistency obligations)

33. Impose ONE consistent choice throughout the paper for: spelling variants ("parameterize" or "parametrize", never both); compound treatment ("first-order equation" vs "equation of first order"; "time-step" vs "timestep"); math expression style ("1000" vs "1,000"; "2-norm" vs "two-norm"); citation grouping ("[1], [2], [3]" vs "[1, 2, 3]"); and numbering style ("Theorem 1" vs "Theorem 1.1").
34. British spellings are allowed if consistent; if British and American spelling are mixed, change all to American.
35. Series of displayed equations must be punctuated even when authors omit it (see §13.4) — text and displays together must read grammatically.
36. Figures and tables belong in the same section as their callouts (same or following page); numbered figures/tables must not interrupt mid-paragraph in mid-page.
37. Correct incomplete sentences, dangling participles, and disagreement in number, gender, or tense; edit wording "only as needed" — do not impose personal style over a consistent authorial choice.

## §12.2 Mathematical symbols as parts of speech

38. Classify symbols grammatically when reading math as prose: Verbs: = ≠ < > ≤ ≥ ≺ ≻ ≪ ≫ ⊂ ⊃ ∈ ∋ ≡ ≢ ∼ ≁ ≃ ≅ → ← ⇒ ⇔ ∉. Conjunctions: + − × ∓ ∪ ∩ ∨ ∧ · ∘ ⊕ ⊗. Fences: { } [ ] ⟨ ⟩ ( ) | | ‖ ‖. Nouns: italic/Greek/German/Hebrew/Cyrillic letters and numerals. Sigma-class (collective) signs: ∑ ∏ ⋃ ⋂ ⋀ ⋁ ⨁ ⨂ and ∫. A displayed or in-text formula must parse as a clause or sentence under this reading.

## §12.3 Type

39. No "fake" blackboard bold (IR, IP built from letter pairs); use true blackboard bold (ℝ, ℙ).
40. Avoid bold for emphasis; emphasize with lightface italic in roman text and roman in italic text (consistent author usage may stand, but italic is the norm). (AMS house style)
41. Slant type is not a substitute for italic; the text of theorem-style enunciations is italic.
42. Standard functions/operators (cos, sin, log, det, dim, …; see Appendix-A rule 200) are roman in both roman and italic text; author-invented functions may be italic if treated consistently; roman functions may appear italic in subscripts/superscripts if the author is consistent.
43. Arabic numerals are ALWAYS roman, even inside italic text, theorem statements, figure legends, references, and list identifiers ((1), (i)): ✓ "For any integers k > 1, 2, …" (numerals roman within the italic theorem text); ✓ "Assume that F is uniformly convex of Type I."
44. Letters identifying figure parts are roman: "Figure 2.1(a)".
45. Latin words/abbreviations found in the dictionary (a priori, et al., i.e., e.g., cf., etc.) are "text dependent": roman in roman text, italic in italic text — never fonted independently of their surroundings. (AMS house style)
46. Lowercase Greek letters are always italic (γ, δ, θ); uppercase Greek letters are always roman (Γ, Δ, Θ). (AMS house style)
47. Punctuation and true-punctuation parentheses inside italic text are italic; parentheses that are part of a math expression are ALWAYS roman.
48. Italics for the first use of a defined term is standard; scare quotes are for words used in an unusual sense — pick one scheme and hold it ("use italics for a word that will be defined and … scare quotes for words being used in an unusual way").

## §12.4 Capitalization in lists

49. Use parallel construction in every list.
50. Words denoting list parts (step, case, region) are lowercase in text UNLESS the list names its items ("Step 1", "Region 2"), which makes them proper nouns: with items labeled "Region 1., Region 2., …" write "In Region 1, b_{i+1} is either n or ⌈n/2⌉"; with items labeled "1., 2., 3." write "In region 1, …".
51. Names of theorems/concepts are lowercase except proper-noun parts ("the fast Fourier transform theorem"); numbered ones are capitalized proper nouns ("Theorem 2.2", "Lemma 3.1", "Figure 4.5").
52. Capitalize the first word of a list item only if the item is a complete sentence; phrase items are lowercase and separated by commas (or semicolons if items contain internal commas), with "and" before the last item.

## §12.5 Wording

53. "shall", "upon", "since" (causal), future tense, "well-defined" and friends: all acceptable — do not "correct" them.
54. Use first person plural ("we"), including in the abstract, even for a single author; "one" is also acceptable. (AMS house style)
55. Avoid starting a sentence with a reference number, variable, equation number, or mathematical expression.
56. Midsentence, "equation (2.6)" may drop the word "equation"; but NEVER drop the describing word in "assumption (2.6)", "problem (14)", "inequality (3.3)"; keep "equation" at sentence start and in named constructs ("the density equation (3.1)").
57. "respectively"/"resp.": either, if consistent; the preferred pattern is "respectively" in text and "(resp. …)" in parentheses; set "respectively" off with commas ("…are discussed in sections 2 and 4, respectively."; "Using m = 1 (resp., m = .001) yields 20 (resp., 42) points per subdomain.").
58. "i.e.", "e.g.", "that is", "for example", "etc." are set off with commas; author's choice between symbol/abbreviation and words stands if consistent.
59. ∀ and ∃ may not open a sentence or replace words in running text: ✗ "∃ an n-dimensional compact complex manifold X with c₁(X) ≥ 0." ✓ "There exists an n-dimensional compact complex manifold X with c₁(X) ≥ 0."; ✗ "∀ integers k ≥ 0 we know that Hᵏ(X) ∈ 𝒯ₙ." ✓ "For all integers k ≥ 0 we know that Hᵏ(X) ∈ 𝒯ₙ." — but ∀/∃ INSIDE a math expression is fine: ✓ "We know that Hᵏ(X) ∈ 𝒯ₙ ∀k ≥ 0."; best reserved for displayed math.
60. Spell out "Figure" and "Table" in callouts ("See Figure 2.1 and Table 3.2"); avoid "above"/"below" when referencing numbered figures/tables (they may float; links need full references).
61. Replace "the sequel" with "what follows" (unless it genuinely means Part II of a series). (AMS house style)
62. Use a comma in if/then constructions: "If x < 0, then x = y."
63. In a series of let/be statements, each independent clause needs both "let" and "be", joined by commas: "Let K be a triangle (tetrahedron), and let S be any of its edges (faces)."; "Let ρ be a segment, let g be an elliptic curve, and let h be a domain." One grandfathered elided form is allowed and does NOT generalize: "Let A be an abelian group and h : A → R a real valued function on A such that…".
64. "that" vs "which": leave the author's choice unless meaning is certainly unchanged.
65. Parallelize correlatives and series: ✗ "The proof follows easily from Proposition 3.4, Theorems 3.5 and 2.4." ✓ "The proof follows easily from Proposition 3.4 and Theorems 3.5 and 2.4."; ✗ "This type of system is practical, easily implemented, and can be adapted to different problems." ✓ "This type of system is practical and easily implemented and can be adapted to different problems."; ✗ "depends both on the driving current I and the actual boundary conditions" ✓ "depends on both the driving current I and the actual boundary conditions"; ✗ "either will admit shock waves or rarefactions" ✓ "will admit either shock waves or rarefactions".
66. MATLAB is spelled in all caps.

## §12.6 Acronyms

67. Spell out every acronym at first use in the body, followed by the acronym in parentheses; then use the acronym consistently. (An acronym better known than its expansion may be reversed: "the RSA algorithm (the Rivest, Shamir, and Adelman algorithm)".)
68. Plural acronyms take lowercase "s", no apostrophe: "PDEs", not "PDE's".
69. "3D"/"3-D"/"3d" (three-dimensional) counts as an acronym: spell out on first use.

## §12.7 Punctuation

70. Figure and table captions end with a period only when they are a full sentence.
71. Comma policy is OPEN style: use commas only when necessary; a consistent, not-incorrect authorial pattern stands.
72. Use the serial comma before "and"/"or" in lists of three or more; if items contain internal commas, separate items with semicolons.
73. Conditions are treated as parentheticals and set off with commas: "In this case, x_i > 2, i = 1, …, N, and k denotes a constant."
74. Use a comma before "where" following an equation (it usually introduces nonrestrictive information).
75. "however" used parenthetically is set off with commas; joining independent clauses it takes a semicolon before it (see rule 82).
76. Use a comma after a long introductory clause, and to prevent misreading (e.g., in a "where μ and ν are positive constants which depend only on m and n, and σ(C) := C{1+ln(1+C)}⁻¹" list, the comma stops "σ(C)" from attaching to "depend only on").
77. A formally posed (unquoted) question midsentence is introduced by a comma and capitalized: "The question we now ask is, Are strict and realistic bounds known for the remainder of the terms?"
78. Delete the comma between parts of a compound predicate: ✗ "We present our study in several steps, and consider f strongly convex and differentiable."
79. Delete commas before final prepositional phrases ("if", "for", "with" in a final clause), and before ∀ / "for all".
80. Write "if and only if" without commas (delete the commas in "if, and only if,").
81. Semicolon joins two independent, RELATED clauses not linked by a conjunction ("This assumption is required for the approximation results in Sobolev spaces; see, e.g., [5]."); no comma splices and no "semicolon splices" (two unrelated independent clauses spliced together).
82. Use a semicolon before "thus", "hence", "therefore", "then", "however", "moreover" when they join independent clauses: "Let us restrict our discussion to m = 2; then we can provide a proof for Theorem 4.2."
83. Use semicolons between list items that contain internal commas; semicolons and commas are NOT interchangeable: ✗ "Clustering is used in various fields of statistical analysis; pattern recognition; learning theory; computer graphics; and combinatorial chemistry." (simple items — should be commas).
84. A colon introducing a series/list must follow a COMPLETE sentence (typically with "the following" or "as follows"); never put a colon before the direct object or predicate nominative: ✗ "Members of the department include: the undergraduates, graduate students, and the professors."
85. After "namely", "for instance", "for example", "that is": no colon (unless what follows is a complete clause); AMS preference is semicolon (or em dash) BEFORE "namely" and comma after it. (AMS house style)
86. Introduce theorems/lemmas with a PERIOD, not a colon: ✓ "Our results are summarized in the following theorem." ✗ "Our results are summarized in:" ✗ "Our results are summarized in the following theorem:"
87. In section titles, capitalize after a colon: "The Smith theorem: An overview". (AMS house style)
88. Hyphenate: "-type" compounds ("a Newton-type method, a Cauchy–Schwarz-type equation"); prefixes before proper nouns ("non-Hermitian"); adjective+past-participle ("well-known study"); noun+present-participle ("decision-making methods"); adjectival compounds ("lower-level toxin"); compounds of degree ("very-low-degree polynomial").
89. Hyphenated compound modifiers appear BEFORE the noun; after the noun they open up: "second-order differential operators" but "differential operators of second order"; "an ill-posed question" but "the question was ill posed".
90. Do NOT hyphenate words formed with the prefixes ante-, anti-, bi-, counter-, de-, equi-, extra-, infra-, inter-, intra-, macro-, micro-, mid-, mini-, multi-, non-, over-, pre-, post-, pro-, pseudo-, re-, semi-, sub-, super-, supra-, trans-, tri-, ultra-, un-, under- (so: "nonnegative", "semigroup", "preimage") — EXCEPT when the prefix meets the same vowel it ends with: "semi-independent", "bi-invariate".
91. Do NOT hyphenate: suffixes -fold, -hood, -less, -wise; units read together ("ice cream cone"); after "-ly" adverbs ("highly specialized field"); "ill"/"well" compounds that are themselves modified ("very ill conditioned matrix"); ordinal-letter expressions — "xth", not "x-th".
92. En dash for numeric/reference ranges: "equations (2.2)–(2.6)", "pp. 345–348"; change hyphens in ranges to en dashes; do not replace an en dash with "to"/"through".
93. En dash joins two DIFFERENT people's names in adjectival compounds ("the Smith–Jones formula", "Cauchy–Schwarz", "the Birch–Swinnerton-Dyer conjecture" — hyphen inside the single hyphenated surname Swinnerton-Dyer, en dash between authors); also en dash in a compound modifier when one element is hyphenated or multiword ("post–Civil War period").
94. Opposition pairs take a HYPHEN, not an en dash: "even-odd system", "an apples-oranges kind of choice", "a zero-nonzero pattern of solutions". (AMS house style — APA prescribes en dash here; AMS explicitly rejects that.)
95. Em dash sets off material for emphasis or as strong parentheses: "…P₀.₅(1000) ≈ 1 − e⁻⁵ = 0.99326—a virtual certainty."; use parentheses for less emphasis.
96. Plurals of single-character variables and numerals take apostrophe-s: "a's, b's, c's; α's, β's, γ's, 1's, 2's, 3's"; plurals of acronyms do not ("PDEs").
97. Avoid contractions. (AMS house style)
98. Possessives of names ending in "s" add apostrophe-s: "Gauss's ideas, Descartes's dreams, Eratosthenes's sieve, Wiles's solution".
99. Double quotation marks for quotes and scare quotes; single quotes ONLY inside double quotes; no quotation marks after "so-called" ("the so-called minor arcs", not "the so-called 'minor arcs'").
100. Logical (British-style) punctuation: commas and periods fall OUTSIDE closing quotation marks (a deliberate break with US convention); colons/semicolons also outside; question/exclamation marks inside only when part of the quotation. Example: offered to "include the corrections I have learned from our memorable correspondence". (AMS house style)

## §12.8–12.10 Quotations, bias-free language, articles

101. Direct quotations of five or more lines are block indented (quote environment).
102. Gender-neutral wording preferred; per this guide singular "they/their" is NOT an acceptable substitute for he/she — use "he or she" sparingly, consistent "she", or alternation. (AMS house style, 2017-era; many venues now accept singular they.)
103. Articles carry meaning in math prose — "The combinatorial interpretation" (the one and only) vs "A combinatorial interpretation" (one of many); do not add/delete articles unless the meaning is certain.
104. "a" vs "an" goes by sound: "a univalent thingie", "an honorary degree", "an n-dimensional doodad", "an ω-level widget"; before pronounced "h", AMS prefers "a" — "a historical remark". (AMS house style)
105. Watch singular/plural of -ics words: "statistics" ≠ "statistic"; "mathematics" and "asymptotics" always end in s; "The number is…" but "a number are…".

## §13.1–13.3 Numbers, variables, functions

106. Spell out single-digit numbers and use digits for 10 and above in text; BUT mathematical uses of single digits are fine if consistent ("rank 1" or "rank one"; "codimension 2" or "codimension two"; "3-dimensional" or "three-dimensional") — default to keeping the author's consistent pattern.
107. Numerals — including Roman numerals (I, IV, XII) — are set roman regardless of surrounding font: "uniformly convex of Type I" (roman "I" in italic theorem text).
108. Variables default to italic (f) but may be bold (f), bold italic, roman, fraktur (𝔣), calligraphic (ℱ), or blackboard bold (𝔽) as the author sets them — consistency required; fake blackboard bold always fixed to true.
109. Standard operators/functions are roman so they aren't read as products of variables: ✓ "lim_{k→∞} |C_k| = 0" with roman "lim"; ✗ with italic "lim". (See rule 200 for the list.)
110. "ker" vs "Ker" (and similar case pairs) can denote different objects — case of function names must not be silently normalized.
111. A function name is followed by a thin space unless its argument is fenced (then closed up): "dim e_{3,0}", "max⟨θ,p⟩", "Aut_C(V)".
112. In TEXT, subscripts of functions/operators go alongside, not beneath: "max_{P̂∈C_{N−k+2}} min_{P̃∈C_k} ρ(P̃,P̂) = λ_k" with limits to the side (below-style limits are display-only).

## §13.4 Punctuation of mathematics

113. Every equation, displayed or in-text, reads as a clause or sentence and is punctuated accordingly; insert the commas/periods needed so display + surrounding text reads grammatically.
114. Set off conditions (phrases restricting an item in an equation) with commas: "z_k = Φ⁻¹(e^{iθ_k}), k = 1, …, n+1,"; "the computation of L⁻¹A, i = 1, …, m, takes mn³ + O(max{m,n}³) flops."
115. No comma before ∀ or "for all" after math; but a parenthetical "for all" phrase BEFORE its equation keeps its commas: "Then (4.2) shows that, for all x < 0, the restriction would be T₀ ≤ T₁."
116. No comma between math and a following restrictive verbal expression — "if", "when", "for", "such that": ✗ "f = 2(x), if x < 1"; ✗ "a_i = a_j + a_k for some k ≤ j < i, such that…". DO use a comma before "where" (nonrestrictive).
117. Do not blindly comma-terminate every display; a comma never precedes "for all", ∀, or a preposition; no comma before prepositions INSIDE equations either: ✓ "…< ∞ for every u ∈ X" (no comma before "for").
118. Two displayed equations joined by "and" can form a compound predicate — no comma before the "and"; with three or more displayed equations in series, use the serial comma.
119. Left-braced multiline systems (cases-like): punctuate each line (commas); right-braced systems: no line punctuation required.
120. A colon may introduce a display ONLY if the introducing sentence does not continue after the display (or if a "where" list/qualifier immediately follows); if the sentence continues past the display, no colon: ✗ "This gives differential equations and inclusions: [display], but note that…" ✓ same display ending with a period, then "Note, however, that…". Never colon before a display that is the direct object: ✗ "The results can be written as: Ca ≥ [0]." ✗ "The volume of a tetrahedron is given by: 1/3 × (area of base) × height." ✗ "We can also state that: F(i) = I." (all three read on with NO punctuation before the display).

## §13.5 Line dots vs centered dots

121. \ldots (baseline dots) between variables separated by commas or other punctuation: "0, …, n−1".
122. \cdots (centered dots) between operators and relations: "0 < ⋯ < 2", "x₁ + x₂ + ⋯ + x_n". Exception: "a₁ · a₂ · … · a_n" (baseline dots preferred between centered dots for readability).
123. Dots with no flanking commas/operators stand where the author put them; literal "..." (three periods) becomes \ldots.

## §13.6 Fences

124. Fence inventory: parentheses ( ), brackets [ ], braces { }, angle brackets ⟨ ⟩, single bars | |, double bars ‖ ‖; fences are ALWAYS roman.
125. Angle brackets are ⟨ ⟩ (\langle\rangle), never the relations < >: ✓ "⟨f ∘ g⟩′(t)", ✗ "<f ∘ g>′(t)".
126. Every opening fence needs its closing fence (count them!); deliberate mixed pairs like "(a, b]", "[a, b)", "[a, b[" are legitimate; the single bar in "X = {x_i ∈ N | i = 1, …, n}" is "such that", not absolute value.
127. In TEXT, fences stay normal size even if fractions/scripts overhang; in DISPLAYS, fences should be as large as the material they enclose (consistent smaller sizing acceptable) — but do NOT enlarge fences merely to encompass superscripts/subscripts.
128. In multiline displays, an opening fence and its closing fence on different lines must be the same size.

## §13.7–13.9 Sigma-class symbols and integrals

129. Sums/products: limits to the RIGHT of ∑/∏ in text; ABOVE AND BELOW in display.
130. A primed sum ∑′ (prime on the sum) is meaningful notation — the prime must not be moved; small ∑ or ∫ in numerators/denominators of stacked fractions may stay small (consistently within the equation).
131. Distinguish capital Sigma "Σ" (a letter) from summation "∑", and capital Pi "Π" from product "∏" — using the letter where the operator is meant is an error.
132. Unions/intersections (and ∧ ∨ ⊗ ⊕): SMALL size when used as a binary operation/conjunction ("f₁ ∪ f₂ ∪ f₃ ∪ ⋯"), BIG size (⋃, ⋂, ⨁, ⨂) when used as a collective noun over a family ("⋃_{n=1}^∞ f_n"). The presence of a subscript is NOT diagnostic — position between two operands identifies the small binary form (e.g. "x ⊗_A Ae" is small ⊗ despite its subscript).
133. Integrals: limits to the right of ∫ in text ("∫₀ᵀ C(φ_t) dt"); in display, limits at the right or centered above/below — either, per the author.

## §13.10 Fractions

134. Never break or alter a fraction; a display-margin overrun with a big fraction is an author query, and an in-text overrun means move it or display it.
135. In-text fractions may be stacked (case) or slashed — both fine; but DISPLAY-STYLE (full-size) fractions inside text lines are wrong, mark to text style.
136. Fractions need not be uniform across the paper — only within a single math phrase; slashed-fraction parenthesization ("1/2a + b" vs "1/2(a + b)") stands unless the same construction is internally inconsistent.
137. Case/slashed fractions in superscripts and subscripts are fine and need not match the full-size fractions' style, but must be consistent within one display.

## §13.11 Cases

138. Lines of a cases construction are separated by commas (or semicolons, if consistent) and the last line ends with a comma or period per the following text: "|a| = { a, a ≥ 0, / −a, a < 0. }" or "|a| = { a, a ≥ 0; / −a, a < 0. }".
139. Comma before each case's condition — unless the condition begins with text ("1 if x ≥ 0, / 0 otherwise,"), where the comma may be omitted consistently.
140. Cases constructions are always displayed, never run into text.

## §13.12–13.13 Matrices and diagrams

141. Two-row matrices (e.g. binomial coefficients) may sit in text; matrices of more than two rows must be displayed.
142. Do not enlarge fences around an in-text matrix to fully enclose it (causes line spread) — text-size fences are correct there; matrices are NEVER broken (shrink point size if a display overruns).
143. Commutative diagrams, unlike displays, may legitimately end unpunctuated; if an unpunctuated diagram ends a sentence, the preceding text should end with a colon; never a floating period on its own line after a diagram; treat all diagrams in the article consistently.

## §13.14 Equation numbers

144. Equation numbers are optional — never add numbers to unnumbered equations.
145. Equation numbers go on the LEFT of the display. (AMS house style)
146. The number may align with the first line, last line, or center of a multiline equation — any is fine if unambiguous; keep the author's grouping of displayed equations unless a line overruns.
147. Letters or words may serve as equation numbers ("(C)"); their font must match between display and text mentions.
148. Cross-references to equations are enclosed in roman parentheses — "(3.2)" — with the parentheses always roman.

## §13.15 Spacing in displays

149. Two separate equations on one line, or an equation and its condition, are separated by a two-quad (four-letter) space; a consistent one-quad space is acceptable: "γ′(s) = …,   s ∉ {−2, −3, …, −b}."
150. Three or more equations on one line: single quad space between them.
151. A preposition inside a display gets a quad space before and a word space after: "X_i(z) = (π(i)z / (1−(1−π(i))z))^b   for i < j".
152. Spacing around conjunctions (and/or between equations) may be a word space, quad, or two-quad — but the same on both sides.

## §13.16 Breaking equations in text

153. Break in-text math before or after an operator (or after a comma/semicolon) that is NOT between fences; if there's a choice, breaking at a word (thick) space beats breaking at an operator.
154. After a sigma-class (collective) sign, no break until an operator occurs outside the fences.
155. After an ∫, no break until the d…; then break after the next punctuation or at a verb; exception "∫ dx + dy" — no break at all.
156. When two fenced groups abut (")(" juxtaposition = multiplication), a break between them requires inserting × or a centered dot — EXCEPT when a sigma-class symbol precedes the fences, at the slash of a slashed fraction (never break there), and in logic.
157. Breaking between fences is allowed only when the open fence isn't directly preceded by a noun/fence/sigma-class symbol AND the closing fence isn't directly followed by a noun/fence — but avoid fence-interior breaks whenever possible.
158. Never run an author's displayed equation into text; you MAY promote an in-text equation to display to fix a bad break.
159. Logic-specific: expressions break BEFORE verbs and conjunctions and not within fences; ⇒/→ (implies), ⇔ (iff), &/∧ (and), ∨ (or) are conjunctions that may outrank verbs for choosing the break; breaks go BEFORE ¬, ∃, ∀; when breaking at a fence in logic, insert NO times sign or dot.

## §13.17 Breaking and aligning equations in displays

160. In displays, break BEFORE an operator, never after; do not rebreak displayed equations that fit the margin.
161. Operators never end a line of a displayed equation: ✗ "0 = kΛ(k(ρ(x)), k(ρ(y))) = ⏎ = lim_{n→∞} kΛ(…)" (trailing "=", then repeated); ✓ the "=" starts the continuation line, once.
162. Align multiline equations on operators: verbs align with verbs (successive = / ≤ signs in a column), conjunctions with conjunctions.
163. If a long expression precedes the first verb, indent the succeeding verb-aligned lines two em quads from the left.
164. Breaks at conjunctions (+, −, ×): align the conjunction to the RIGHT of the first verb (i.e., visibly inside the right-hand side), or two em quads from the left margin.
165. Keep expressions visually within their fences: when a break falls inside a fence pair, the continuation operator lines up to the RIGHT of the opening fence so the line reads as inside the fences.
166. Author-intended alignment (left, right, on the verb, or centered) stands if clear and within margins.

## Appendices A–F (reference lists distilled)

167. Roman-type functions/operators (Appendix A; roman in both roman and italic text): ad, arccos, arcsin, arctan, arg, Aut, bd/Bd, bin, cl, coker, const, cos, cosh, cot/ctg, coth, Cov, csc, deg, det, diag, dim, div, exp, Ext, Gal, gcd, GL, gr, grad, hom/Hom, id, Im, inf, int, ker/Ker, lg, lim, lim inf, lim sup, ln, log, Log, max, min, mod, Pr/Prob, pt, rank/Rank, Re, sec, sech, sgn, sin, sinh, SL, SO, Sp, spin/Spin, SU, sup, supp, tan, tanh, tg, tr/Trace, Var, w (weak star), wr, Wr.
168. Eponym adjectives: ancient/classical (mostly Greek) mathematicians take "-ean" ("Euclidean", "Pythagorean"); modern ones take "-ian" ("Riemannian", "Noetherian", "Abelian"); lowercase forms ("abelian", "euclidean", "gaussian", "boolean") are acceptable if used consistently.
169. En dash between different mathematicians' names, hyphen within one hyphenated surname: "Cauchy–Schwarz", "Gauss–Seidel", "Runge–Kutta", "Korteweg–de Vries", "Birch–Swinnerton-Dyer" vs the single people "Heath-Brown", "Colliot-Thélène", "Levi-Civita". (Hyphens throughout are tolerated if consistent, but the distinction is preferred.)
170. Spellings to check: "Schwarz" (Cauchy–Schwarz) vs "Schwartz" (distributions); "Eisenstein" ≠ "Einstein"; "l'Hôpital" preferred over "l'Hospital"; "Chebyshev" standard; possessive vs attributive: "Burgers's equation" but "the Burgers equation".
171. Standard scholarly abbreviations are text dependent and used without explanation: a.a., a.e., a.s., cf. ("compare" — NOT a substitute for "see"; never "c.f."), e.g. (not a substitute for "i.e."), et al., etc., i.e., iff, i.i.d., viz., w.r.t., w.l.o.g.
172. Four math compounds are ALWAYS hyphenated, in every position: "well-behaved", "well-defined", "well-order(ing)", "well-posed". Other "well/ill" compounds hyphenate only before the noun ("a well-known result" / "the result is well known" / "a very well known result").
173. AMS-preferred spellings (any consistent authorial variant may stand, but inconsistency resolves to these): acknowledgment; analogue (noun) / analog (adjective); byproduct; canceled, canceling, but cancellation; cross section (noun); descendant (noun) / descendent (adjective); embedding (not imbedding); homogeneous; labeled; modeled; online; parallelepiped; setup (noun) / set-up (adjective) / set up (verb); traveled; zeros; zeroth. "pseudo" and "quasi": noun compounds open, adjective compounds hyphenated.
174. Commonly confused pairs to check (Appendix F): affect/effect; assure/ensure/insure; between/among; comprise/compose; discrete/discreet; farther/further; if/whether; imply/infer; lay/lie; less/fewer; maybe/may be; precede/proceed; principle/principal; proved/proven; till/until (never 'til); toward (US)/towards (UK); who/whom; "data" always takes a plural verb; dilation vs dilatation; homomorphism (algebra) ≠ homeomorphism (topology).
