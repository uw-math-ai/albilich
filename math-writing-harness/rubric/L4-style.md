# L4 — Sentence-Level Style

Local, mostly mechanical. **Owner critic:** Pedant (deterministic lint first, then an LLM
pass for judgment calls). **Default severity:** `minor`/`nit`. **Most are `autofix: safe` or
`assisted`.**

Sources: `CONRAD`, `POONEN`, `SU`, `MILNE`, `KLR`, `HALMOS`, `PAK-CLEAR`, `MAURER`,
`AMS-STYLE`, `KRANTZ`, `SERRE`, `LEE`.

Run all `lint` rules here every round — they are near-free and catch the bulk of surface
defects before any LLM budget is spent.

---

## Sentences & symbols (deterministic)

- `L4-SENT-01` [lint] **Math is written in complete, punctuated sentences;** displayed
  equations take punctuation as clauses of the surrounding sentence (period if the sentence
  ends, comma otherwise). Read aloud including the equations to test. autofix: assisted.
  (`CONRAD` §2, `SU` 3, `LEE` 2-4, `AMS-STYLE` 113, `MAURER` §14)
- `L4-SENT-02` [llm] **Formulas have verbs.** "=" and its kin are the verbs of math clauses;
  an expression without a relation is a noun, not a sentence; never use "=" to mean "the
  next step is" (a chained mis-equality literally asserts −1 = 0 = 1). autofix: assisted.
  (`LEE` 7, `MAURER` 34, `AMS-STYLE` 38)
- `L4-SYM-01` [lint] **Symbols in different formulas are separated by words.** Bad:
  "Consider S_q, q < p." Good: "Consider S_q, where q < p." autofix: assisted. (`KLR` 1,
  `CONRAD` §3)
- `L4-SYM-02` [lint] **No sentence begins with a symbol** — prepend the type word in
  apposition ("The set X belongs to…", "The polynomial xⁿ − a has…"); never capitalize a
  variable to fix this (math is case-sensitive) — recast instead ("Quantity a is positive").
  autofix: assisted. (`KLR` 2, `HALMOS` §17, `MAURER` 23, `AMS-STYLE` 55, `SERRE` 16)
- `L4-SYM-03` [lint] **Ranges/quantifier scopes are bound** ("for 1 ≤ k ≤ n," not a dangling
  "1 ≤ k ≤ n"). autofix: assisted. (`CONRAD` §1)
- `L4-SYM-04` [lint] **No footnote markers attached to math symbols.** autofix: assisted.
  (`MILNE`)
- `L4-SYM-05` [lint] **Punctuation marks are not overworked:** no "Assume that a ∈ X. X
  belongs to C" (period doing double duty); not "Since p ≠ 0, p ∈ U" but "Since p ≠ 0, it
  follows that p ∈ U"; not "For invertible X, X* also is invertible" but "…the adjoint X*
  also is invertible." autofix: assisted. (`HALMOS` §17)
- `L4-SYM-06` [llm] **Each relation symbol reads one fixed way** (∈ always "is in", never
  sometimes "in"); no symbol-as-preposition and symbol-as-verb in one sentence ("For x ∈ A,
  we have x ∈ B" → "For x in A, we have x ∈ B"); no "is ≤ 3" hybrids ("Whenever a positive
  number is ≤ 3, its square is ≤ 9" is ugly). Krantz's stronger form: a binary relation
  appears only in the exact form A REL B — "Every real, nonsquare x < 0" is illegitimate.
  autofix: assisted. (`HALMOS` §17, `KRANTZ`)
- `L4-SYM-07` [lint] **Typography dots don't collide:** no "sin(x)·cos(x). cos(x) being…"
  (product dot vs sentence period); insert words ("the function cos(x)"). autofix: assisted.
  (`SERRE` 17)

## Symbol/word discipline (deterministic)

- `L4-LOGIC-01` [lint] **No ∀, ∃, ∧, ∨, ⇒, ∴, ∵, ∋ as prose abbreviations** outside logic
  papers; write the words. ∀/∃ INSIDE a displayed math expression is acceptable
  (`AMS-STYLE` 59); ⇒ in prose to mean "so/thus" is always wrong (`POONEN-SPK` 14). Bad:
  "∃ an n-dimensional compact complex manifold X." autofix: **safe**. (`KLR` 3, `CONRAD` §4,
  `HALMOS` §14, `SERRE` 24)
- `L4-SHORT-01` [lint] **No blackboard shorthand in formal prose:** `WLOG`, `s.t.`, `w.r.t.`,
  `iff`, `resp.` used inconsistently. "iff" is "ugly English, but good mathematics" — still
  auto-expand to "if and only if" (`SERRE` 25; note `AMS-STYLE` 171 tolerates iff/w.l.o.g.
  as scholarly abbreviations — venue-profile decides; default: expand). autofix: **safe**.
  (`CONRAD` §4, `SU` 5)
- `L4-SHORT-02` [lint] **No ambiguous abbreviations** (the "with." = without? Kodaira
  anecdote); abbreviations that can be misresolved are spelled out. autofix: safe. (`SERRE`
  23)
- `L4-BB-01` [lint] **Blackboard-bold sets (ℤ, ℚ, ℝ, ℂ) are not used as adjectives/element
  names**; and no fake blackboard bold (IR, IP letter pairs) — true ℝ, ℙ only. autofix:
  assisted. (`CONRAD` §8, `AMS-STYLE` 39)
- `L4-NUM-01` [lint] **Small numbers spelled as adjectives, digits as names:** "the method
  requires two passes" but "Method 2", "increased by 2", "the leftmost 2". Single-digit
  mathematical uses ("rank 1" vs "rank one") — either, consistently. autofix: assisted.
  (`KLR` 18, `AMS-STYLE` 106)
- `L4-NUM-02` [llm] **Numeral-vs-word ambiguity resolved toward the symbol:** "What are we
  to do when x is one?" — write 1 when the numeral is meant. autofix: assisted. (`KLR` 41)

## Words & usage (lint + judgment)

- `L4-USAGE-01` [lint] **"that" vs "which":** restrictive that, non-restrictive
  comma-which; operational test: "if it sounds all right to replace a 'which' by a 'that',
  replace it." (AMS copyeditors leave author choice — venue profile may relax.) autofix:
  assisted. (`KLR` 22, 34; `MILNE`)
- `L4-USAGE-02` [lint] **less/fewer; affect/effect; principle/principal; imply/infer;
  comprise/compose; precede/proceed; discrete/discreet; lay/lie; maybe/may be; its/it's;
  who/whom; "data" plural; dilation ≠ dilatation; homomorphism ≠ homeomorphism.** autofix:
  assisted. (`AMS-STYLE` 174, `KLR` 21-22, `SERRE` 22)
- `L4-USAGE-03` [lint] **Spelling traps:** occurrence, dependent, auxiliary, feasible,
  preceding, referring, category, consistent, descendant (noun), nonnegative/nonzero
  (unhyphenated), "principal bundle" (never "principle bundle" — "has a moral fiber"),
  Schwarz ≠ Schwartz, Eisenstein ≠ Einstein. Standard American spellings by default; any
  consistent variant per venue. autofix: safe. (`KLR` 21, `SERRE` 22, `AMS-STYLE` 170,
  173, `PAK-CLEAR` 32)
- `L4-USAGE-04` [lint] **"any" is banned where ∀/∃ ambiguity exists** (cross-listed
  L2-QUANT-02); "where" as lazy afterthought recast ("If n is sufficiently large, then
  |aₙ| < ε, where ε is a preassigned positive number" — fix by quantifying up front);
  "equivalent" only for genuine logical equivalence, never for "both provable with similar
  effort." autofix: assisted. (`HALMOS` §14)
- `L4-USAGE-05` [llm] **Function/value/expression discipline:** f is the function, f(3) a
  value ("the function f(3)" is wrong; "the function f(x)" tolerated); an expression
  (x + 10) is not a function; "solve" only when isolating an unknown (evaluation is not
  solving); "function notation," not "functional notation"; not "the function z² + 1" but
  "the function z ↦ z² + 1". autofix: assisted. (`MAURER` 34-40, `HALMOS` §15)
- `L4-USAGE-06` [llm] **"sequence" only for ℕ-indexed families; contain (∈) vs include (⊂)
  used consistently.** autofix: assisted. (`HALMOS` §15)
- `L4-USAGE-07` [lint] **"Assume/Suppose that" keep the "that"** when it aids parsing; never
  "We have that x = y" (drop it); no padding ("because of the fact that"). In complicated
  technical sentences prefer keeping "that." autofix: assisted. (`KLR` 8, 51)
- `L4-USAGE-08` [lint] **"the sequel" → "what follows"** (unless a literal Part II exists);
  "the proof above"-style word order preferred over "the above proof". autofix: safe.
  (`AMS-STYLE` 61, `KLR` 45)
- `L4-USAGE-09` [lint] **No contractions; no "hopefully" as sentential adverb** (raises
  hackles, distracts). autofix: safe. (`AMS-STYLE` 97, `KLR` 35)
- `L4-USAGE-10` [llm] **Plain words over fancy ones.** No "henceforth"-class vocabulary
  where "from now on" serves; unusual words can be mistaken for technical terms; repetitive
  therefores beat elegant variation (audience includes non-native readers). "Communicate
  and inform, not impress." autofix: assisted. (`PAK-CLEAR` 27, `TAO` 63-65, `KLR` 26)
- `L4-USAGE-11` [llm] **No noun-string adjectives, no unnecessary jargon** ("the packet
  switched data communication network protocol problem"). autofix: assisted. (`KLR` 26)
- `L4-USAGE-12` [llm] **Don't echo unusual ("sticky") words** — two uses of a striking word
  in unrelated passages create phantom connections; keep them spaced. autofix: assisted.
  (`KLR` 9, 40)
- `L4-USAGE-13` [lint] **Latin scholarly abbreviations used correctly and text-dependent:**
  cf. = "compare" (not "see"); e.g. ≠ i.e.; i.e./e.g. set off with commas; et al.; a.e.;
  i.i.d. autofix: assisted. (`AMS-STYLE` 58, 171)
- `L4-USAGE-14` [lint] **Acronyms spelled out at first body use** (again, even if spelled in
  the abstract), then used consistently; plurals without apostrophe (PDEs); "3D" counts as
  an acronym. autofix: assisted. (`AMS-STYLE` 7, 67-69)
- `L4-USAGE-15` [llm] **Defined-term morphology is frozen:** if "nice graph" is defined,
  "niceness of graphs" is banned — stick to the basic form. autofix: assisted.
  (`PAK-CLEAR` 33)
- `L4-USAGE-16` [llm] **Gender-neutral, bias-free wording** per venue norms (modern default:
  recast or singular they; AMS-2017 house style prescribed he-or-she/alternation — venue
  profile decides). autofix: assisted. (`AMS-STYLE` 102, `KLR` 37)
- `L4-USAGE-17` [llm] **Articles carry meaning:** "THE combinatorial interpretation" claims
  uniqueness, "A combinatorial interpretation" does not; a/an by sound ("an n-dimensional",
  "a historical"). Definite article requires an established unique referent — cross-listed
  with L1-LOCAL-09 (the a/the cheat). autofix: assisted. (`AMS-STYLE` 103-104, `SERRE` 11)

## Grammar & punctuation (lint)

- `L4-GRAM-01` [lint] **Agreement and structure:** subject–verb agreement ("the set … is"),
  no dangling participles, no sentence fragments, pronoun–antecedent agreement, complete
  parallel constructions in series and correlatives ("will admit either shock waves or
  rarefactions", not "either will admit shock waves or rarefactions"). autofix: assisted.
  (`CONRAD` §5, `KLR` 20, `AMS-STYLE` 37, 65, 73)
- `L4-GRAM-02` [lint] **Comma discipline:** open style (only when necessary) but serial
  comma in lists ≥3; comma in "If …, then …"; comma before nonrestrictive "where" after an
  equation; NO comma before restrictive if/when/for/such-that after math; no comma before
  ∀/"for all"; conditions set off as parentheticals ("x_i > 2, i = 1, …, N, and…"); no
  comma splices; commas never do logical work (`SERRE` 14); coincident punctuation
  collapses (two commas → one; comma+period → period). autofix: safe where regexable,
  else assisted. (`AMS-STYLE` 71-80, 114-118, `PAK-CLEAR` 29, `KLR` 36)
- `L4-GRAM-03` [lint] **Semicolon discipline:** joins related independent clauses; before
  "thus/hence/therefore/however/moreover" between independent clauses; between list items
  with internal commas; never between simple list items. (Pak bans semicolons outright —
  "make the logical connection explicit between sentences"; venue/voice profile chooses;
  default: allow AMS usage, flag overuse.) autofix: assisted. (`AMS-STYLE` 81-83,
  `PAK-CLEAR` 30)
- `L4-GRAM-04` [lint] **Colon discipline:** a colon introducing a list/display must follow a
  complete sentence; never between verb and object ("The results can be written as: Ca ≥ 0"
  ✗); theorems introduced by a PERIOD, never a colon ("We can now prove the following
  result." then the Theorem); no colon after "namely"/"that is." autofix: safe. (`KLR` 4,
  23, `AMS-STYLE` 84-86, 120)
- `L4-GRAM-05` [lint] **Hyphen/dash discipline:** hyphenate compound modifiers before the
  noun, open after ("second-order operator" / "of second order"; well-defined, well-posed,
  well-behaved, well-order are ALWAYS hyphenated); no hyphen after standard prefixes
  (nonnegative, semigroup, preimage) except same-vowel collisions (semi-independent); no
  hyphen after -ly adverbs; en dash for ranges "(2.2)–(2.6)" and between different people
  ("Cauchy–Schwarz", "Birch–Swinnerton-Dyer"); hyphen for opposition pairs ("even-odd");
  "xth" not "x-th". autofix: safe. (`AMS-STYLE` 88-94, 169, 172)
- `L4-GRAM-06` [lint] **Quotes & possessives:** double quotes, singles only inside; no
  quotes after "so-called"; logical placement of punctuation relative to quotes when
  quoting symbol strings (always end your program with the word "end".) — venue profile
  picks US vs logical convention elsewhere; possessives: Gauss's, but "the Burgers
  equation" (attributive). autofix: assisted. (`KLR` 25, 43, `AMS-STYLE` 98-100, 170)
- `L4-GRAM-07` [lint] **Exclamation points only for actual exclamations** (or Halmos's
  parenthetical "(!)", at most once per chapter); no double emphasis. autofix: safe.
  (`KLR` 27, 48)
- `L4-GRAM-08` [llm] **Split infinitives and sentence-final prepositions are allowed** when
  recasts sound forced — do NOT "fix" them mechanically (except prepositions the sentence
  already accommodates mid-structure). (Anti-overcorrection rule for the reviser.) (`KLR`
  49-50)

## Tense & voice

- `L4-TENSE-01` [lint] **Mathematical facts in present tense**; outside intro/final remarks
  use present indefinite (occasionally past indefinite); grant footnotes past tense.
  autofix: assisted. (`CONRAD` §5, `PAK-CLEAR` 28, `AMS-STYLE` 11)
- `L4-VOICE-01` [llm] **Invitational, neutral, factual voice:** "we" = author+reader (never
  royal/authorial-only "we": "We thank our wife" is always bad); "I" avoided in formal
  papers; imperative recasts welcome ("Replace x by 7 throughout"); no "one has thus
  proved"; simple declaratives carry facts. autofix: assisted. (`SU` 2, `HALMOS` §13,
  `KLR` 6, 42, `AMS-STYLE` 54)
- `L4-VOICE-02` [llm] **In revision mode, preserve the author's voice** — minimal targeted
  edits, no homogenizing rewrite. severity: `major` if violated. autofix: manual. (`TAO`
  56-62, `KLR` 44: "the style has to be your own")
- `L4-VOICE-03` [llm] **Rhythm check:** read the passage aloud (or simulate); reword what
  doesn't flow; sentences parse left-to-right without garden paths ("Smith remarked in a
  paper about the scarcity of data"). autofix: assisted. (`KLR` 7, 17, `AMS-NOTICES` 4,
  `LEE` 4)
- `L4-VOICE-04` [llm] **Humor and cleverness budget ≈ 0:** jokes only if they encode a
  technical point and survive rereading; no snide polemics, no in-jokes, no showy
  quotations of famous mathematicians as decoration. autofix: assisted. (`KLR` 27, 29,
  `TAO` 50-52, `HALMOS` §3)
- `L4-VOICE-05` [llm] **Proof-by-contradiction openers are worded formally:** "Seeking a
  contradiction, suppose …" (not "Not."/"Deny."). autofix: safe. (`KRANTZ`)

## Notation & fonts

- `L4-NOT-01` [lint] **Every symbol defined at/before first use** with its kind (number?
  function? set?). Cross-listed with L2-DEF-01; here as a surface check via the notation
  table. autofix: assisted. (`CONRAD` §1, `HALMOS` §5, `KLR` 11, `LEE` 21-25)
- `L4-NOT-02` [lint] **Notation is consistent and injective:** no symbol for two things (the
  h-variable/h-function 30-minute rule: rename every instance, never a per-section
  disclaimer), no two symbols for one thing, no "A_j for 1 ≤ j ≤ n" here and "A_k" there;
  index conventions fixed (i≤m, j≤n) and kept. severity: `major` (this one silently breaks
  proofs). autofix: assisted. (`PAK-CLEAR` 2, `HALMOS` §15, `KLR` 14, `SERRE` 28, `LEE` 25)
- `L4-NOT-03` [llm] **Notation fits convention:** p primes, z complex, n naturals, ε small
  positive; violating letter-type connotations creates "unnecessary cognitive dissonance"
  (a large negative ε; "a sequence nε tending to 0 as ε becomes infinite"); respect frozen
  letters (e, i, π) and avoid freezing new ones ("xyz-space"). autofix: assisted.
  (`CONRAD` §1, `TAO-READ` 21, `HALMOS` §6)
- `L4-NOT-04` [lint] **No stacked/nested subscripts where avoidable** (set-element notation
  over subscripted subscripts: elements x, y of X, not x_{i_1}); no subscript-superscript
  collision designs (x^p_i vs x_p^i: "what is x²₃?"). autofix: manual. (`KLR` 15, `HALMOS`
  §6)
- `L4-NOT-05` [llm] **Minimal notation ("the best notation is no notation"):** no irrelevant
  symbols in statements ("On a compact space every real-valued continuous function f is
  bounded" — f contributes nothing); no proof-preparation constants smuggled into statements
  (the ρ in "If 0 ≤ limₙ αₙ^{1/n} = ρ < 1…" belongs in the proof); three-use rule: notation
  for what recurs ≥3×, none for one-offs. autofix: assisted. (`HALMOS` §16, `TAO` 29)
- `L4-NOT-06` [llm] **Notation harmony:** ax + by or a₁x₁ + a₂x₂, never ax₁ + bx₂; no
  ∑_{σ∈Σ} a_σ; ∈ vs ε kept apart; alphabetically/mnemonically coherent families (tails =
  functions; a-e constants; i-n integers; x-z variables). autofix: assisted. (`HALMOS` §5,
  `PAK-CLEAR` 35)
- `L4-NOT-07` [llm] **Named-vs-bland terminology calibrated to centrality:** bland names
  ("good/bad", "Type I/II") for peripheral tech; colorful names only for central concepts;
  never name anything after yourself; descriptive names beat attribution chains ("the
  closed graph theorem" good, "the Cauchy-Buniakowski-Schwarz theorem" bad). autofix:
  manual. (`TAO` 28-30, `HALMOS` §20)
- `L4-NOT-08` [llm] **Symbol legibility:** avoid Ξ ι ϖ ı ȷ; κ/υ too close to k/v; ∅ not
  \emptyset-zero; ℓ not l; ε not ϵ; avoid Gothic unless field-standard; distinct meanings
  need visually distinct letters. autofix: assisted. (`PAK-CLEAR` 35)
- `L4-FONT-01` [lint] **Font discipline:** variables italic; numerals ALWAYS roman (even in
  italic theorem text); standard operators roman (sin, log, lim, det, …, per the AMS
  Appendix-A list); lowercase Greek italic, uppercase Greek roman; fences always roman;
  same letter in a different font is a DIFFERENT symbol — never drift (v vs 𝐯); Latin
  abbreviations text-dependent; punctuation/parens part of math are roman. autofix:
  assisted. (`CONRAD` §8, `AMS-STYLE` 42-47, 108-110, 167, `MAURER` 21-23)
- `L4-FONT-02` [lint] **Emphasis with italics, not bold; defined terms italicized/bolded at
  definition; scare quotes only for words used unusually — one scheme, held.** autofix:
  assisted. (`AMS-STYLE` 40, 48, `SU` 5, `MAURER` §8)

## AI-pattern slop & house anti-choreography (sources: `AI-SLOP`, `HOUSE`, stop-slop)

- `L4-SLOP-01` [lint] **AI-vocabulary density:** flag occurrences of delve, tapestry, testament,
  showcase/showcasing, underscore(s), pivotal, intricate, interplay, meticulous(ly), boasts,
  vibrant, garner, foster(ing), metaphorical landscape/realm/journey, seamless(ly), multifaceted,
  holistic, leverage (verb), commendable, resonate, groundbreaking, renowned, "valuable insights",
  ever-evolving — density-based, not banned words; one survives, three do not. severity: `minor`.
  autofix: assisted. (`AI-SLOP` 1)
- `L4-SLOP-02` [lint] **No significance inflation:** "plays a crucial/vital/pivotal/key role",
  "stands/serves as a testament/reminder", "underscores/highlights the importance", "setting the
  stage for", "marks a (key) shift/turning point", "reflects broader". Replace with the specific
  mathematical fact or delete. severity: `major`. autofix: assisted. (`AI-SLOP` 2)
- `L4-SLOP-03` [lint] **No copula avoidance:** "serves as", "stands as", "boasts", "features"
  (verb), "offers" where plain "is/are/has" is meant. severity: `minor`. autofix: safe.
  (`AI-SLOP` 3)
- `L4-SLOP-04` [lint] **No negative-parallelism drama:** "not only … but also", "not X, but
  rather Y", "It is not X. It is Y." — state Y directly. severity: `minor`. autofix: assisted.
  (`AI-SLOP` 4)
- `L4-SLOP-05` [lint] **No section-recap openers:** paragraphs starting "In summary,",
  "Overall,", "In conclusion,", "Taken together,", "To summarize,". Math papers do not recap
  sections. severity: `major`. autofix: safe (delete the recap). (`AI-SLOP` 4)
- `L4-SLOP-06` [lint] **No connector spam:** consecutive sentences/paragraphs opening with
  Moreover/Furthermore/Additionally/Also. severity: `minor`. autofix: assisted. (`AI-SLOP` 4)
- `L4-SLOP-07` [lint] **Em-dash density bounded** (sparse em dashes acceptable per AMS; flag
  clustering). severity: `nit`. autofix: assisted. (`AI-SLOP` 4)
- `L4-SLOP-08` [llm] **One name per object — no elegant variation:** the same mathematical object
  keeps the same name at every mention; synonym chains ("the group … the algebraic structure …
  the object under study") are defects. severity: `major`. autofix: assisted. (`AI-SLOP` 4,
  `HOUSE` 7)
- `L4-SLOP-09` [lint] **No task-narration/choreography phrases:** "We now proceed to", "We first
  establish the following", "Having established X, we turn to", "With these preparations in
  place", "the necessary input", "the remaining calculation", "it remains to check" as filler,
  "the proof rests on N points", "we (now) record the following", "needed below", "the mechanism
  is simple". Replace checklist transitions with the mathematical implication being used.
  severity: `major`. autofix: assisted. (`HOUSE` 29-32, `AI-SLOP` 5)
- `L4-SLOP-10` [llm] **No uniform rhythm or hedging stacks:** paragraphs of identical shape and
  punchy endings; "may potentially/could possibly suggest" where status must be definite
  (proved/cited/conjectured). severity: `minor`. autofix: manual. (`AI-SLOP` 4)
- `L4-SLOP-11` [lint] **No one-sentence paragraphs** (also catches stray LaTeX blank lines
  splitting a paragraph). severity: `minor`. autofix: assisted. (`HOUSE` 13)
- `L4-SLOP-12` [lint] **No vague-pronoun paragraph openers:** a paragraph must not begin
  "This/These/It" + verb with no single antecedent; repeat the noun. severity: `nit`. autofix:
  assisted. (`HOUSE` 18)
- `L4-HOUSE-01` [llm] **Proofs explain why relations hold — never narrate task completion;** no
  mid-proof foreshadowing; mathematical levels kept distinct (geometric identities stated
  geometrically before functors are applied). severity: `major`. autofix: manual. (`HOUSE` 29-33)
- `L4-HOUSE-02` [llm] **"We" discipline:** "we" for novel authorial acts (we prove/define/
  construct — required near genuine novelty, never hidden in passive prose); impersonal sentences
  for standard background; no habitual "we recall/we record/we now show"; "recall" only for
  material stated earlier in the same paper. severity: `minor`. autofix: assisted. (`HOUSE`
  24-26)
- `L4-HOUSE-03` [lint] **Colons and semicolons avoided outside math mode** (prefer separate
  sentences or connecting phrases; HOUSE override of the AMS semicolon license). severity:
  `minor`. autofix: assisted. (`HOUSE` 15)
- `L4-HOUSE-04` [llm] **No parenthetical asides in prose** — integrate the qualification or
  delete it. severity: `nit`. autofix: assisted. (`HOUSE` 16)
- `L4-HOUSE-05` [llm] **Background reads as established mathematics, not project planning;**
  argument-first citations (fact, then source); references integrated into the argument, never
  listed as imported ingredients; no vague scope language ("considered here", "suitable",
  "relevant", "in this setting") outside precisely-scoped statements. severity: `major`.
  autofix: assisted. (`HOUSE` 20-23, 34-36)
- `L4-HOUSE-06` [llm] **Attribution chronology is accurate:** "introduced/generalized/
  reformulated/later associated" used per the true historical relation; never attribute a
  definition to the later paper that only generalized it. severity: `major` (cross-listed
  L1-FAITH-03). autofix: manual. (`HOUSE` 12)
- `L4-HOUSE-07` [lint] **Section openers (HARD RULE): every section's first paragraph carries
  a sentence beginning "In this section, we …"** ("In this appendix, we …" for appendix
  sections); References/Acknowledgment/bibliography sections (and their starred variants) are
  exempt. Deterministically enforced on the final_paper — violations block the paper.
  severity: `major`. autofix: assisted. (`HOUSE` 19)
- `L4-HOUSE-08` [lint] **"We" discipline, deterministic subset (HARD RULE): the habitual
  collocations "we recall", "we record", "we now show", "we now prove", "we now turn",
  "we begin by", "we start by", "we note that", "we observe that" are banned in prose**
  (case-insensitive, math stripped); the judgment remainder of the "we" discipline stays
  with L4-HOUSE-02. Deterministically enforced — violations block the paper. severity:
  `major`. autofix: assisted. (`HOUSE` 25)

---

### Two operating modes for the Pedant
- **Generation mode:** the Pedant may rewrite freely toward the house style.
- **Revision mode:** `L4-VOICE-02` dominates — every `autofix: safe` still applies (these
  are errors, not style), but `assisted`/judgment edits must be **diff-minimal** and voice-
  preserving. The reviser produces the smallest patch that clears the rule.

### Known style conflicts (store both; venue/voice profile arbitrates)
- Quotation punctuation: US convention (KLR 25) vs logical placement (Halmos §19,
  AMS-STYLE 100 sides with logical).
- Semicolons: AMS grammar (yes) vs Pak (never).
- "iff"/"w.l.o.g.": AMS scholarly-abbreviation list (allowed) vs Conrad/Su/Serre (expand).
- Generic pronouns: AMS-2017 (no singular they) vs modern venue norms (singular they fine).
- Tabular/structured proofs: Lamport (pro) vs Halmos (prose) — KLR 32.
- Referring to results: Poonen 35 (always by number) vs Conrad §6 (words like "by the
  previous theorem" acceptable).
