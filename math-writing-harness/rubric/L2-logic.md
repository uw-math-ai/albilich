# L2 — Logical Exposition

Correct math can still be unfollowable. L2 is about whether the *reasoning is legible*:
every claim justified, every justification attached to the right claim, the reader never
stranded. **Owner critics:** Confused Reader (primary), Referee (assists on justification).
**Default severity:** `major` for stranded-reader failures, else `minor`.

Sources: `POONEN`, `TAO-READ`, `TAO`, `SU`, `CONRAD`, `LEE`, `MAURER`, `KLR`, `HALMOS`,
`SERRE`, `POONEN-SPK`.

---

## Justification discipline

- `L2-JUSTIFY-01` [llm] **Non-immediate claims name their support.** If a claim doesn't
  follow from the previous sentence alone, the text says what it follows from ("By Lemma
  8.3," "Combining the previous two sentences,"). severity: `major`. (`POONEN` 1)
- `L2-JUSTIFY-02` [llm] **One reason per claim, correctly attached.** In multi-claim
  sentences and equality chains, each justification is unambiguously tied to its claim.
  severity: `major`. (`POONEN` 2)
- `L2-JUSTIFY-03` [llm] **At every period, the reader can see why each prior claim is true.**
  Deferred proofs are flagged at the point of assertion ("We will prove this proposition in
  Section X"). severity: `major`. (`POONEN` 3, `TAO` 46)
- `L2-JUSTIFY-04` [llm] **Connective words are present and truthful.** "Thus/therefore/so/
  consequently" appear exactly where one statement is derived from another; their absence
  signals independent derivation (readers parse it that way — `TAO-READ` 13). And they may
  not lie: "thus" is wrong if the next claim doesn't depend on the previous one ("Let f(t)
  be the temperature at time t. Thus f′(t) = lim…" — temperature has nothing to do with the
  definition). severity: `major`. (`MAURER` §11, `POONEN-SPK` 2)
- `L2-JUSTIFY-05` [llm] **No unexplained equality chains.** A proof that is a chain of
  expressions separated by = signs is "coding"; supply the recipe sentence ("first
  substitute p for q, then collect terms, permute factors, insert and cancel r") or
  per-line side-comments ([def. of f] / [expand] / [combine terms]). severity: `major` for
  nontrivial chains. (`HALMOS` §16, `MAURER` §14, `KLR` 10, `LEE` 7-8)
- `L2-JUSTIFY-06` [llm] **Proofs run forward.** No "Given ε, let δ = (ε/(3M²+2))^{1/2}"
  backward-verification openings; start from what is being controlled and derive the choice.
  "Neither arrangement is elegant, but the forward one is graspable and rememberable."
  severity: `minor`. (`HALMOS` §16)
- `L2-JUSTIFY-07` [llm] **Prefer direct proofs to contradiction when a direct proof is
  available** (the contradiction wrapper often hides a direct argument: strip "suppose not …
  contradiction" shells whose contradictory hypothesis is never used). severity: `minor`.
  (`KLR` 39 Halmos-lecture, `SU` 10)

## Reader reconstruction (the Confused Reader's core)

- `L2-RECONSTRUCT-01` [llm] **Reconstructability:** a reader with only the paper text (no
  author reasoning, no source) can rebuild each proof. Points where reconstruction fails are
  L2 defects located exactly there. severity: `major`. (`POONEN` 8; `TAO-READ` compilation-
  error taxonomy: undefined terms, unexplained steps, cascading typos, cryptic-but-essential
  comments, implicit connections, buried hypotheses)
- `L2-RECONSTRUCT-02` [llm] **No forward-reference repair work.** The reader should never
  NEED the `TAO-READ` repair strategies (read ahead to the proof's end, search forward to
  where the lemma is used, re-parse a cryptic remark) to parse a statement: define terms
  before use, put hypotheses in the statement, make comments interpretable at the point they
  appear. Each needed repair = one defect. severity: `major`. (`TAO-READ` 11-13)
- `L2-RECONSTRUCT-03` [llm] **Running hypotheses are recapped** where they operate: lemma
  statements restate accumulated assumptions/conventions ("Let notation and assumptions be
  as in §2" at minimum); theorem statements are self-contained. severity: `major`. (`TAO`
  44, `KLR` 5)
- `L2-RECONSTRUCT-04` [llm] **The "blah" test:** sentences flow when all but the simplest
  formulas are replaced by "blah" — logical scaffolding must live in the words, since readers
  skim formulas on first pass. severity: `minor`. (`KLR` 13)
- `L2-DIFFICULTY-01` [llm] **Difficulty spikes are surfaced and explained**, not glossed;
  jumps in statement strength come with commentary on why the amplification is available.
  severity: `minor`→`major`. (`TAO-READ` 18-21)
- `L2-DETAIL-01` [llm] **Detail budget matches novelty.** "Dwell at length (plenty of
  English) on the most important, innovative, and crucial components … be brief on the
  routine, expected, and standard"; material familiar to the author but not the field is
  expounded "even if these details are 'obvious' to you." severity: `major` when a crucial
  step is under-explained or a standard step bloats the proof. (`TAO` 35-36, `SU` 6,
  `SERRE` 26: prefer more detail on paper — "too long → flip the page; too short → spend a
  lot of time trying to reconstruct")
- `L2-DETAIL-02` [llm] **Obscure imported lemmas are restated in full** with precise citation
  (never "by a lemma in [my previous 100-page paper]"); crucial ones get a proof sketch.
  severity: `major`. (`TAO` 37)
- `L2-DETAIL-03` [llm] **Standard tedious computations are flagged as standard beforehand**
  (reader license to skim) and then done tersely. severity: `minor`. (`TAO` 66)

## Definitions & quantification

- `L2-DEF-01` [llm] **Definitions precede use and are stable** (no meaning drift; no
  recalling notation introduced inside a lemma's proof outside that proof). severity:
  `major`. (`CONRAD` §7, `TAO` 26)
- `L2-DEF-02` [llm] **Definitions are motivated** where the reader would otherwise not know
  why the definition is needed. severity: `minor`. (`MAURER`, `KLR` 12)
- `L2-DEF-03` [llm] **Definitions are marked as definitions** (Def./":="/italicized term/
  boldface definiendum) and stated twice where helpful — formal + informal characterization
  ("Nⁿ is defined twice; Aₙ is described as 'nonincreasing'"). severity: `minor`.
  (`POONEN-SPK` 6, `KLR` 11, `MAURER` §8)
- `L2-DEF-04` [llm] **Defined terms displace their English synonyms.** After defining
  "slope," never write "steepness" for the same concept (the trained reader assumes a second,
  different refinement); never use the defined word in its loose English sense ("critical"
  after defining critical point). severity: `major`. (`MAURER` §8)
- `L2-DEF-05` [lint] **"Let"-definitions bind left.** The definiendum goes on the left of =
  ("Let f(x) = x²", never "Let x² = f(x)"); a let-equality assigns right to left. severity:
  `minor`. autofix: safe. (`MAURER` §8)
- `L2-DEF-06` [llm] **"Let" vs "suppose" vs bare assertion:** "let" introduces conventions we
  control (symbols); "suppose" introduces hypotheses we don't ("Suppose f′(x) > 0 for x < a"
  in a case split — "let" would be wrong because the sign is not up to us); "X = Y" asserts,
  "Let X = Y"/"X := Y" defines. severity: `minor`→`major` where the role is ambiguous.
  (`MAURER` §11, `POONEN-SPK` 6)
- `L2-QUANT-01` [lint/llm] **Quantifiers are explicit** where ambiguity would result. Bad:
  "a is in the center iff ax = xa." Good: "… iff ax = xa for all x ∈ G." severity: `minor`→
  `major` when the quantifier is load-bearing. (`POONEN-SPK` 4-5)
- `L2-QUANT-02` [lint] **"Any" is banned in formal statements** — ambiguous between ∀ and ∃
  ("Prove that any complex number is …" invites the one-witness reading); use "each"/"every"
  or recast. severity: `minor`. autofix: assisted. (`HALMOS` §14)
- `L2-QUANT-03` [llm] **No free variables in statements** (every letter bound or introduced;
  "use no letter only once"); bendable mid-paragraph, never in theorem statements.
  severity: `minor`. (`HALMOS` §16)
- `L2-COND-01` [lint] **Conditionals are explicit:** "If …, then …" — and in mathematical
  contexts the "then" is kept ("The presence of 'then' can never confuse; its absence can";
  Knuth: keep it whenever the post-comma clause is a mathematical statement). severity:
  `minor`. autofix: safe. (`POONEN-SPK` 3, `HALMOS` §17, `KLR` 52)
- `L2-COND-02` [llm] **No stacked conditionals** ("If p, then if q, then r") — recast per
  local emphasis ("If p and q, then r"). severity: `nit`. (`HALMOS` §14)
- `L2-COND-03` [llm] **Commas do not carry logic.** "If A, B, C" (comma-as-"and" +
  comma-as-"hence") must be spelled out: "If A and B are true, so is C." severity: `major`
  when genuinely ambiguous. (`SERRE` 14)

## Statement hygiene

- `L2-STMT-01` [llm] **Theorem statements are self-contained** — hypotheses inside the
  statement, no dependence on the preceding paragraph's assumptions (or an explicit
  "Notation as in §2"). severity: `major`. (`KLR` 5, `TAO` 44)
- `L2-STMT-02` [llm] **Theorem first, then proof** — no rambling development ending "Thus we
  have proved that…", no "hanging theorem" ("Thus we have proved\nTheorem 2 …"). Motivation
  comes before the statement; the statement comes before the proof. severity: `minor`.
  (`HALMOS` §11)
- `L2-STMT-03` [llm] **Statements are single sentences where possible; no chit-chat inside**
  ("Without loss of generality we may assume…" and "Moreover it follows from Theorem 1
  that…" do not belong in a theorem statement). severity: `minor`. (`HALMOS` §11)
- `L2-STMT-04` [llm] **Page-long many-hypothesis theorems are refactored** — "a list of eight
  hypotheses and six conclusions do not a theorem make; they are a badly expounded theory";
  isolate the underlying concept or split. severity: `minor` (structural; escalate to L3).
  (`HALMOS` §11)
- `L2-STMT-05` [llm] **Words are the verbs of statements.** No theorem whose entire content
  hides in a symbol (the Inventiones "∈ Q" theorem — the verb must be findable; write "is
  rational"). Do not use ⇒ to mean "so/then" in prose. severity: `minor`. (`SERRE` 15,
  `POONEN-SPK` 14)
- `L2-STMT-06` [llm] **Sentence roles are explicit for formula-sentences.** "Let A = 5" /
  "Suppose A = 5" / "Therefore A = 5" — a bare "A = 5" that leaves assumption vs assertion
  ambiguous is flagged. severity: `minor`. (`SU` 4, `LEE` 26)

## Sentence-level logic flow

- `L2-SENTENCE-01` [llm] **Single-idea sentences by default;** combine only to clarify
  logical relationships. severity: `nit`. (`POONEN` 4, `PAK-CLEAR` 28)
- `L2-CLARITY-01` [llm] **Clarity is not sacrificed for brevity or elegance-variation.**
  Repetitive connectives beat varied-but-vague prose ("It is perfectly ok to be repetitive
  and have ten therefore's … rather than difficult words like 'henceforth'"). severity:
  `minor`. (`POONEN` 5, `PAK-CLEAR` 27)
- `L2-CLARITY-02` [llm] **For the sake of clarity, rules may be broken** — when a style/
  grammar rule and mathematical clarity conflict, reword first; if nothing works, clarity
  wins. (Meta-rule: critics do not flag deliberate, clarity-serving violations; the
  meta-reviewer confirms intent.) (`PAK-CLEAR` 5, `HALMOS` §19)
- `L2-CLARITY-03` [llm] **Unclear writing masks errors** — "when you are unclear, all claims
  look reasonably true" (Pak's false-but-clear Abelian-center example). Any passage the
  Confused Reader cannot paraphrase truth-conditionally is flagged even if no error is
  visible — opacity itself is the defect. severity: `major`. (`PAK-CLEAR` 1)
- `L2-REPEAT-01` [llm] **Good repetition, bad repetition.** Parallel passages repeat
  word-for-word with the difference drum-rolled ("Note that the first five conditions … are
  the same; what differs is the sixth"); near-repetition in different words (reader wonders:
  same or different?) is flagged; a proof repeated is a missing lemma ("never repeat a
  proof"). severity: `minor`. (`HALMOS` §12, `KLR` 9-parallelism)

---

### Interaction with L1
L2 and L1 overlap on justification: if the Confused Reader can't reconstruct a step, that is
*either* an exposition gap (L2, fix the writing) *or* a real hole (L1, fix the math). The
**meta-reviewer** decides which, by asking the Referee whether the step is *true*
independent of how it's written:
- true but unfollowable → **L2** (reviser rewrites the exposition),
- not established → **L1** (blocker; math must be fixed or claim demoted).
This routing prevents "fixing" a genuine gap by merely rewording it.

### Context-isolation contract
The Confused Reader sees ONLY the paper (never the source, never other critics' notes) —
its confusion is the signal. Do not "brief" it out of its confusion.
