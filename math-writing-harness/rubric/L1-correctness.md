# L1 — Mathematical Correctness & Faithfulness

**Owner critics:** Referee (proof correctness), Provenance Auditor (faithfulness, citations).
**Default severity:** `blocker` for faithfulness/citation; `blocker`/`major` for proof errors.
**This layer gates shipping.** No L1 blocker may remain unresolved at the human gate.

The order below is the order to run: cheap triage → global screens (skim-cost, per `TAO-READ`:
"to find a local error … one basically has to read a significant fraction of that paper
line-by-line, whereas to find a global error it is often sufficient to skim") → local
line-by-line checks → escalation to tools.

Sources: `AARONSON`, `TAO-READ`, `TAO`, `SERRE`, `PAK-STORY`, `PAK-CLEAR`, `MAURER`,
`HALMOS`, `MILNE`, `GOVERNANCE`.

---

## L1.A — Triage screen (Referee, run first; cheap) — `AARONSON`

- `L1-AARONSON-01` [llm] **Engages prior work.** Absent related-work grounding is a red flag.
  severity: `major`.
- `L1-AARONSON-02` [llm] **A key idea / difficulty spike is identifiable** — not a wall of
  manipulation with no new idea. severity: `major`. (also `TAO-READ` 18)
- `L1-AARONSON-03` [llm] **Worked examples / concrete instances exist**, not only notation.
  severity: `minor`→`major` if the claim is strong.
- `L1-AARONSON-04` [llm] **Famous problem + disproportionately elementary tools** → flag for
  heightened scrutiny (never auto-reject); raises the verify budget. severity: `nit` flag.
- `L1-AARONSON-05` [llm] **Claim-strength sanity:** the harder/stronger the headline claim,
  the more the triage screens above are weighted. severity: meta (budget control).

## L1.B — Global proof errors (Referee; run BEFORE local) — `TAO-READ`, `AARONSON`, `SERRE`

- `L1-GLOBAL-01` [verify] **The argument does not prove too much.** Probe: would the proof,
  run verbatim, also establish a known-false stronger statement (drop a hypothesis, widen a
  class, strengthen the conclusion)? "Global errors tend to invalidate not only the proposed
  proof as it stands, but also all reasonable perturbations." severity: `blocker`.
- `L1-GLOBAL-02` [verify] **No contradiction with known results** — cross-check statement and
  key intermediate claims against standard facts and known counterexamples in the area.
  A counterexample to the claimed implication is a *non-constructive guarantee* that a local
  error exists somewhere. severity: `blocker`.
- `L1-GLOBAL-03` [verify] **Every stated hypothesis is used essentially.** A proof that
  "mysteriously never uses in any essential way a crucial hypothesis" is structurally
  flawed — either the hypothesis is removable (weaken the statement) or it was silently
  covering a gap. severity: `major`. (`TAO-READ` 5, `HALMOS` §11 irrelevant assumptions)
- `L1-GLOBAL-04` [verify] **Hypotheses are preserved on every restatement.** Abstract, intro,
  and formal statement carry identical hypotheses and conclusion strength. severity:
  `blocker`. (`SERRE`, `TAO` 7)
- `L1-GLOBAL-05` [verify] **Boundary / degenerate / tight-hypothesis cases** hold or are
  explicitly excluded (the "something fishy about 0" rule: mention and exclude trivial cases
  explicitly). severity: `major`. (`AARONSON`, `HALMOS` §11)
- `L1-GLOBAL-06` [verify] **Quantifier/negation order is correct** — a correctness bug, not
  style: "not all X are Y" ≠ "all X are not Y". severity: `major`. (`MILNE`)
- `L1-GLOBAL-07` [verify] **Strength-jump audit.** Locate steps where statement strength
  increases sharply (existential→universal, special→general, asymptotic→exact, dimension
  d→d+1). "If the proof ends up being flawed, it is quite likely that at least one of these
  flaws will be associated with a step where statements became unexpectedly stronger by a
  suspiciously significant amount." Those steps get line-by-line L1.C priority. severity:
  routing rule (its findings inherit `blocker`/`major`). (`TAO-READ` 19)
- `L1-GLOBAL-08` [llm] **Parallel-claim probe.** If the proof's structure would work for a
  parallel claim A′ ⟹ E′ known to fail, flag the structural flaw even without locating the
  local error. severity: `blocker`. (`TAO-READ` 10)
- `L1-GLOBAL-09` [llm] **Testing may be non-rigorous.** The Referee is licensed to use
  "heuristics, hand-waving, intuition" to *object*; an objection stands until discharged
  (either the proof is invalid or an accepted intuition is miscalibrated — say which).
  severity: meta (licensing rule for critics). (`TAO-READ` 9)

## L1.C — Local proof errors (Referee) — `TAO-READ`, `SERRE`, `POONEN`

- `L1-LOCAL-01` [verify] **Each inference step follows from stated prior facts.** For every
  step: confirm the entailment, or produce the missing justification, or a counter to the
  step. severity: `blocker` if unjustified and load-bearing.
- `L1-LOCAL-02` [verify] **No claim depends on an unproven/undefined object.** severity:
  `blocker`.
- `L1-LOCAL-03` [verify] **Chains of (in)equalities:** each link holds and its reason is
  identifiable. severity: `major`.
- `L1-LOCAL-04` [verify] **No circularity:** no statement A justified by B where B's
  justification traces back to A. severity: `blocker`. (`TAO-READ` 3)
- `L1-LOCAL-05` [verify] **No equivocation:** no expression used under two readings in
  different steps (each step valid under one reading only ⇒ broken chain). Key terms must be
  defined precisely enough to exclude this. severity: `blocker`. (`TAO-READ` 2)
- `L1-LOCAL-06` [verify] **The last implication exists.** Audit the implicit final step from
  "what was actually shown" to "what was claimed": "they give an argument, then they stop …
  the implication they did not detail. And that's where the mistake was." Mistakes live in
  the non-written part. severity: `blocker`. (`SERRE` §On References and Proofs)
- `L1-LOCAL-07` [verify] **QED-compression audit.** Every "It is a computation," "follows
  from the definitions," "similar to the proof of Theorem 1," *mutatis mutandis*, or bare □
  covering a nontrivial step is expanded or verified. Proof effort must sit where the
  difficulty is — no full proofs for easy Lemmas 1–2 with all difficulty compressed into
  Lemma 3's one-liner. severity: `major` (`blocker` if the compressed step is the paper's
  crux). (`SERRE`)
- `L1-LOCAL-08` [verify] **"Obvious"/"easy to see"/"clearly" claims are actually true and
  actually obvious** (Halmos's tests: still obvious months later? accepted by a colleague
  without intimidation?). The major rule: *make sure the "obvious" is true.* severity:
  `major`. (`HALMOS` §10, `AMS-NOTICES` 6 for general venues)
- `L1-LOCAL-09` [verify] **Existence vs. choice (the a/the cheat).** A proof of "there exists
  f" does not license later reference to "the f of Theorem 1"; if later text needs a specific
  object, the construction must be exhibited and referenced ("the map constructed in the
  proof of Theorem 1"), or the statement reorganized to construct first, then assert
  properties. severity: `blocker` when a later step uses a property not guaranteed by bare
  existence. (`SERRE` §On Grammar)
- `L1-LOCAL-10` [verify] **Conjunction-scope of multi-part theorems.** "(a) There exists f;
  (b) f is P" must say whether SOME f satisfies both or EVERY f from (a) satisfies (b).
  severity: `major`. (`SERRE`)
- `L1-LOCAL-11` [verify] **Naturality/commutativity claims are proved, not declared.** "Two
  naturally defined arrows are equal" and "the diagram commutes" are proof obligations
  (Eilenberg: "you have not proved it's the same map. Might be the opposite."); "the spectral
  sequence of f" presupposes a fixed construction — name it when it matters. severity:
  `major`. (`SERRE`)
- `L1-LOCAL-12` [verify] **Analysis constants discipline.** Every constant's dependencies are
  stated (Vinogradov ≪ with subscripts); every O(·) has an explicit limit direction and, if
  its "implicit constant" is later referenced, an explicit x₀-regime. "x₀ is as difficult to
  choose as the constant." severity: `major`. (`SERRE` §Analysis)
- `L1-LOCAL-13` [verify] **Pictures in proofs carry stated invariants.** Which features of
  the figure are essential (touching? count of wiggles? orientation?) is said in words; the
  proof step must not depend on unstated picture features. severity: `major`. (`SERRE`
  §Topology, `LEE` 27)
- `L1-LOCAL-14` [verify] **Identifications are declared where they matter.** When multiple
  standard embeddings/identifications exist (Q into A_Q vs through Q_p …), the one in use is
  named at the point where the argument depends on it. severity: `major`. (`SERRE`)
- `L1-LOCAL-15` [llm] **Levels of confirmation are not conflated.** "Prove" = airtight
  argument from definitions/theorems; "verify" (numerical) and "show"/"illustrate" (example)
  are weaker; proving a special case *illustrates* a general rule, it does not prove it;
  definitions cannot be "proved." The verb must match what the text actually does. severity:
  `major` (it silently overstates confirmation). (`MAURER` §7)

## L1.D — Escalation tiers (Referee)

Run only for `blocker`/`major` correctness items still open after L1.B/C:

1. `tool` **Symbolic check** (CAS) of identities/algebra.
2. `tool` **Numeric sanity** — evaluate claims on random and adversarial instances.
3. `tool` **Counterexample search** on boundary regions where hypotheses are tight
   (`TAO-READ` 14: specializing to a near-counterexample "is often quite instructive").
4. `tool` **Optional autoformalization** of the critical lemma in a proof assistant
   (highest assurance; reserve for the load-bearing result).

Cache `verify` results against a hash of the relevant proof block; unchanged proofs are not
re-verified in later rounds.

## L1.E — Faithfulness to source (Provenance Auditor) — `PAK-STORY`, `TAO`, `HALMOS`

- `L1-FAITH-01` [verify] **No claim exceeds source support.** Every theorem/lemma/remark maps
  to something the source proof-state actually establishes; unsupported claims are demoted
  to conjecture/remark or removed. severity: `blocker`.
- `L1-FAITH-02` [verify] **Gaps are surfaced, not smoothed.** Where the source has a gap or
  pending debt, the paper says so explicitly. severity: `blocker`.
- `L1-FAITH-03` [verify] **Historical/attribution claims are correct.** "On facts, results,
  mathematical implications, prior work, references … you must be completely, 100% correct.
  There is no room for flexibility here. Yes, this includes historical discussions." Never
  guess a reference — find it or drop the claim. severity: `blocker`. (`PAK-STORY` 11)
- `L1-FAITH-04` [llm] **Framing may be constructed; facts may not.** The narrative (order of
  discovery, motivation) may be shaped post hoc if "literally correct"; any statement of
  mathematical fact, priority, or provenance is L1-FAITH-01/03 territory. This is the
  routing rule between allowed storycraft (L3) and forbidden fabrication (L1). (`PAK-STORY`
  12)
- `L1-FAITH-05` [llm] **Status honesty at every assertion.** For each non-obvious claim the
  text discloses its status: proved here / proved elsewhere (cite) / obvious (say so) /
  promised later (promise now) / not known ("We do not know if hypothesis H is actually
  necessary"). "Whenever you tell him something, tell him where it stands: this has been
  proved, that hasn't, this will be proved, that won't." severity: `major`. (`HALMOS` §10,
  `TAO` 9-11, `POONEN-SPK` 10)
- `L1-FAITH-06` [llm] **Unproven assertions are flagged as such.** "If for some reason you
  need to assert a non-trivial statement without proof or citation, it should be made clear
  that you are doing so." severity: `major`. (`TAO` 11)
- `L1-FAITH-07` [llm] **Skipped steps are announced** ("If you skip steps, say so"; simplified
  half-truths are labeled: "Write and say only true things … if simplifying, tell the
  audience"). severity: `major`. (`POONEN-SPK` 8-9)

## L1.F — Citations & residue (Provenance Auditor) — `GOVERNANCE`, `PAK-CLEAR`, `TAO`

- `L1-CITE-01` [tool] **Every citation resolves to a real work** (DOI/arXiv/MathSciNet
  lookup). No hallucinated references. severity: `blocker` — also platform-disqualifying
  (`GOVERNANCE` B1: 1-yr arXiv ban regime).
- `L1-CITE-02` [verify] **Each citation actually supports the sentence citing it.** Serre's
  referee anecdote: the cited formula wasn't in the cited book — and was false. "When in
  doubt, don't hesitate to look up primary sources." severity: `blocker`. (`SERRE` 5,
  `TAO` 68)
- `L1-CITE-03` [lint] **Residue scan** (deterministic, every round): no prompt fragments,
  "as an AI language model," knowledge-cutoff phrases, placeholder text (`???`, `TODO`,
  `[CITATION]`), leftover scaffolding, or instruction echoes. severity: `blocker`.
  (`GOVERNANCE` B2)
- `L1-CITE-04` [verify] **Citation phrasing matches epistemic status** per the Pak citation
  ladder: "proved in [R]" (definitive) vs "see [R]" (survey-grade) vs "see e.g. [R1,R2]"
  (well-known; confirmed in several sources) vs "personal communication" (unverified) vs
  "claims to have proved" (disputed). The chosen form must not overstate the reliability of
  the source. severity: `major`. (`PAK-CLEAR` 21)
- `L1-CITE-05` [verify] **Uncheckable references are forbidden:** no bare pointer to a
  600-page book without page/section, no "[H] D. Hilbert, private communication"-grade
  entries for load-bearing facts, no citing unpublished complete works. Pin-cite anything
  quoted from a work > 5 pages (prefer stable arXiv section numbers, "see [A, §3.1]").
  severity: `major` (`blocker` if the uncheckable citation carries a load-bearing step).
  (`SERRE` 4, `PAK-CLEAR` 24)
- `L1-CITE-06` [llm] **Priority-uncertainty caveats** where novelty is asserted: "to the
  author's knowledge, this observation is new" rather than bare novelty claims. severity:
  `minor`. (`TAO` 60)
- `L1-CITE-07` [llm] **No verbatim reuse without quotation.** Copied paragraphs from prior
  work (including the author's own) appear only as attributed direct quotation ("As Bourbaki
  [17, p. 146] writes"); otherwise paraphrase-with-citation ("The proof here is loosely based
  on that in [5]") or plain citation ("See [27, Section 4]"). severity: `blocker`
  (plagiarism class). (`TAO` 57-58, `MAURER` §12)

---

### Notes for implementers
- L1 is where **critic context differs most**: the Referee sees the proof but *not* the
  drafter's confident summary (no belief inheritance); the Provenance Auditor is the *only*
  critic that sees **both** paper and source proof-state.
- Run order within L1: A (cheap triage) → B (global screens, skim-cost) → C (local,
  line-cost, prioritized by L1-GLOBAL-07's strength-jump map) → D (tools). This is the
  Tao asymmetry exploited as a scheduling rule.
- L1↔L2 routing: a step the Confused Reader cannot reconstruct is EITHER an exposition gap
  (L2) or a real hole (L1). The meta-reviewer asks the Referee whether the step is *true*
  independent of wording: true-but-unfollowable → L2; not established → L1 blocker. Never
  "fix" a genuine gap by rewording it.
