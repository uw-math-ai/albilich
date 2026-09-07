# Auto-proof / auto-research benchmark landscape for Albilich (compiled 2026-07-15)

Curated for Albilich: an **informal (natural-language) proof agent**, CAS-grounded
(Sage/GAP), verification-gated (strict/integration verifiers + adversarial refuter),
aiming at **research-level** problems, with a group-theory/algebra/combinatorics lean.

**How to read the tiers.** Albilich's distinguishing output is a *full written proof*,
not a final answer, and its distinguishing internal machinery is *verification and
refutation*. So the benchmarks that actually measure it are **proof-graded** and
**natural-language**; answer-only sets under-measure it but are needed for comparability;
Lean/formal sets need an autoformalization bridge and are mostly positioning-only.

> SOTA figures are as of ~mid-2026 and move fast — reconfirm any number before putting it in
> the paper. Items marked ✓ were confirmed against primary sources this session; others are
> from standing knowledge — check the source before citing.

## Strategic read (the finding that should shape the whole benchmark plan)

The sharpest 2025-26 result for Albilich's positioning is the **answer-vs-proof gap**. On the
*same* fresh contests, frontier models score near the top of human contestants on final-answer
tasks but **collapse on full proofs**:

- **USAMO 2025, expert-graded proofs ("Proof or Bluff?", ETH/INSAIT):** best model
  Gemini-2.5-Pro **10.1/42 ≈ 24%**; *every other model < 5%* (o3-mini 0.9/42). The paper's
  diagnosis is exactly Albilich's thesis: models "overgeneralize patterns observed in smaller
  numerical cases to larger, untested cases" — fine for a numeric answer, **fundamentally flawed
  for rigorous proof.** Meanwhile they do symbolic algebra/arithmetic well.
- **IMO 2025 public models:** best ≈ **31%** (below bronze); the gold systems (DeepMind Deep
  Think 35/42) are unreleased.
- **Ceiling (Epoch):** *no* tested LLM has solved any difficulty-9 competition problem.

Implication for the paper: **lead with proof-graded benchmarks** (Tier 1) — that is where the
field is failing and where Albilich's verification + refutation machinery is designed to help.
Answer-only benchmarks (Tier 3) are saturating and, worse, *reward exactly the brute-force
pattern-matching the proof benchmarks punish* — report them only for comparability. And note the
tool caveat: MathArena runs models **tool-free by policy**, so it will not credit Albilich's CAS
on numeric contests; CAS shows its value on **FrontierMath / HARP / Project Euler** (Python/CAS
allowed) and inside proofs (finite certificates), not on tool-free answer boards.

---

## Tier 1 — Proof-graded natural-language benchmarks (RUN THESE; they measure Albilich's actual output)

| Benchmark | Year | What it tests | Size | Eval | Access | Relevance |
|---|---|---|---|---|---|---|
| **IMO-ProofBench** (Google DeepMind, part of IMO-Bench) ✓ | 2025 (EMNLP) | IMO-level **proof writing**, 0–7 scored | 60 (30 basic / 30 advanced) | Full-proof, with published grading guidelines for auto-grading | Public — imobench.github.io | **HIGH** — the flagship NL-proof benchmark; grading rubric makes it self-runnable |
| **ProofBench / ProofGrader** ✓ | 2025 | Fine-grained expert **proof evaluation** | 145 problems (6 competitions, 2022–2025), 435 model solutions | Expert-annotated full-proof grading | Public — proofgrader.github.io | **HIGH** — recent, contamination-aware, proof-quality focused |
| **MathArena** (proof track) ✓ | 2024– (live) | Full-proof grading of **fresh** contests (USAMO 2025, IMO 2025, Putnam) | Rolling | Expert full-proof grading, contamination-free by construction | Public — matharena.ai | **HIGH** — the most credible *uncontaminated* signal; run new contests as they land |
| **Putnam (informal)** | classic | Undergraduate proof problems | 12/yr | Full-proof (human or rubric) | Public statements | **HIGH** — proof-graded, in Albilich's wheelhouse |
| **USAMO-2025 "Proof or Bluff?"** (Petrov/Dekoninck/Balunović et al., ETH/INSAIT) ✓ | 2025 | Expert-graded full USAMO proofs | 6 (×4 runs, 8 models) | 2 expert graders/problem, /42 | Public (report + rubrics on GitHub) | **HIGH** — the canonical answer≠proof result (best 10.1/42; rest <5%); cite it as motivation |
| **IMO 2025 proof grading** (MathArena) ✓ | 2025 | Full IMO proofs, graded hours after release | 6 (42 pts) | 4 expert judges | Public | **HIGH** — best public model ≈31%; uncontaminated |

**Why this tier first:** these are the only benchmarks that see the thing Albilich is built
to produce. IMO-ProofBench + MathArena-proof + ProofBench are the core three.

---

## Tier 2 — Research-level / frontier (Albilich's stated ambition)

| Benchmark | Year | What it tests | Size | Eval | Access | Relevance |
|---|---|---|---|---|---|---|
| **IMProofBench** ✓ | 2025 (arXiv 2509.26076, v2 2026) | **Research-level proof generation in a realistic agentic research environment — tools include web search AND SageMath** | 77 peer-reviewed (paired final-answer subproblems) | Dual: human expert on the proof + automated on subproblem answers | **Private** (submit to authors) | **HIGHEST — this is nearly a description of Albilich itself** (agentic, CAS-in-the-loop, proof+subproblem). The single most important benchmark to run/compare against; v2 tested GPT-5.4/Gemini 3.1 Pro/Claude Opus 4.6 |
| **FrontierMath** (Epoch AI), incl. **Tier 4** ✓ | 2024; **v2 2026-06-12** (42% of originals audited/fixed) | Exceptionally hard research-adjacent; Tier 4 is research-level | ~300 (T1–3) + **43** (Tier 4) | Answer-checkable; **Python code execution built into the harness** (submit via `answer()`) | **Gated / held-out** (eval via Epoch) | **HIGH — Python/CAS allowed by design**, "computationally intensive" number theory; the best home for the CAS-helps thesis. SOTA T4 ≈40s% (reconfirm — JS dashboard) |
| **Humanity's Last Exam** (math subset) | 2025 | Frontier closed-form questions | ~2.5k total, math slice | Answer-checkable | Public (some held-out) | **MED-HIGH** — answer-only, but a recognized frontier yardstick |
| **Erdős Problems** (erdosproblems.com, Bloom) ✓ | 2024– (live) | **Genuinely open/unsolved** number theory & combinatorics — the truest "research novelty" test | 1,000+ catalog | **Novel proof**, human-verified (Tao et al.), some Lean-checked | Public (bot-gated) | **HIGH — the closest PUBLIC analogue to Albilich's Kourovka work.** GPT-5.2 Pro's #728 (Jan 2026) is cited as the first genuinely-novel autonomous solve; most "solves" are rediscovery. CAS-amenable (small-case verification). *This is the benchmark that most directly demonstrates the open-problem capability.* |
| **FormalConjectures** (DeepMind) | 2025 | **Open conjectures** (incl. algebra) formalized in Lean | Growing corpus | Corpus, not scored (verifier if proven) | Public | **MED-HIGH** — open *algebra* targets; a source of formalized open problems to attempt |
| **ArXivMath** (MathArena) | 2026-02 | Problems from arXiv papers <1 month old (contamination-free) | 40, rolling | Final-answer (SymPy + LLM judge) | Public | **MED** — freshest answer-checkable; good anti-contamination signal |
| **RiemannBench** ("moonshot mathematics") | 2026 (arXiv 2604.06802) | Research/"moonshot" math | — | — | emerging | **MED** — verify scope/availability |
| Kourovka-notebook open problems | — | Advancing open group-theory problems | n/a | Expert | **No community benchmark exists** (confirmed via arXiv sweep) | Albilich's own results are the evidence; **Erdős Problems is the nearest public proxy.** The absence of a Kourovka/group-theory eval is itself a paper point |

---

## Tier 3 — Answer-only competition sets (for comparability; they UNDER-measure proof quality)

Run a few for cross-system comparability, but note in the paper that final-answer accuracy
hides Albilich's proof-level differentiator.

| Benchmark | Size | Status | Note |
|---|---|---|---|
| **AIME 2025 / 2026** | 30/yr | Fresh-ish; 2024 has contamination | Run 2025+; integer-answer, quick |
| **HMMT Feb 2025** (via MathArena) | ~30 | Fresh | Answer-only, contamination-free |
| **OlympiadBench** | ~8.4k | Established | Multimodal olympiad; answer + some proof |
| **Omni-MATH** | 4,428 | Established | Olympiad-level, answer-graded |
| **HARP** ✓ | 5,409 (4,780 SymPy-auto-checkable) | AMC/AIME/USAMO chain, 6 difficulty levels | **SymPy is the grader** → exact-answer, computation-friendly; good difficulty-stratified answer set |
| **MathOdyssey / U-MATH** | varies | Harder answer sets | Useful spread of difficulty |
| **MATH-500** | 500 | **Saturated** (>90–95% frontier) | Keep only as a sanity baseline; do not headline |
| GSM8K, full MATH | — | **Saturated — skip** | No signal at frontier |

---

## Tier 4 — Verification / refutation / error-detection (SHOWCASE Albilich's differentiators)

These directly exercise the verifier + refuter roles — the paper's trust story. Run them to
demonstrate Albilich's verifier/critic and counterexample search *as capabilities*, not just
as internal plumbing.

| Benchmark | Year | What it tests | Size | Relevance |
|---|---|---|---|---|
| **ProcessBench** (Qwen) | 2024 | Step-level **error localization** in solutions | 3,400 solutions | **HIGH** — evaluate the strict informal verifier as a step-critic |
| **PRMBench** | 2025 | Fine-grained process-reward-model reliability | ~6.2k | **HIGH** — verifier-as-reward-model quality |
| **REFUTE** | 2025 | **Counterexample / disproof** generation to false claims | — | **HIGH** — direct match to the adversarial refuter |
| **IMO-GradingBench** ✓ | 2025 | Automated **proof grading** reliability | 1,000 graded solutions | **MED-HIGH** — test Albilich's verifier *as a grader* |
| **ProJudge / DeltaBench / MalAlgoQA** | 2024–25 | Judge reliability, deceptive/flawed reasoning | varies | **MED** — robustness of the critic |
| Missing-hypothesis / flawed-proof detection sets | 2025 | Does the system catch a silently-dropped hypothesis? | varies | **MED-HIGH** — a signature Albilich check (cf. Tao local/global errors) |

---

## Tier 5 — Computation / CAS-grounded & tool-use (Albilich's home turf)

This is the strongest-fit tier for a Sage/GAP backend, and the CAS-oracle benchmarks below
are the most *reusable* (their graders are literally SymPy/Sage equivalence checkers — you can
borrow the verification design). ✓ = fetched from primary source this session.

| Benchmark | Year | What it tests | Size | CAS role | SOTA (reconfirm) | Access | Relevance |
|---|---|---|---|---|---|---|---|
| **ASyMOB** ✓ | 2025 (arXiv 2505.23851) | University symbolic manipulation (integrals, ODEs, series, limits, hypergeometric) | 35,368 (from 100 seeds via perturbation) | **Grader is CAS** — SymPy simplify(answer−ref)==0 + numeric substitution; tool-use tested as a variable | ~78% pass@1 (frontier); code/CAS helps weak models, not strong ones | Open (GitHub + HF) | **HIGH** — best fit for a symbolic backend; reuse its SymPy-equivalence harness directly |
| **SageMath-Augmented Agents / RealMath** ✓ | 2026 (arXiv 2607.06820) | Whether **SageMath in a ReAct loop** lifts research-level solving | RealMath subset: 133 (numeric/symbolic answers) | **Sage is the verifiable oracle** — model writes Sage, iterates on output | Sage access = **+9.7pp** avg (up to +27.8pp) | Open code | **HIGH** — this paper *is* the SageMath-backend thesis; closest external validation of Albilich's CAS design |
| **MathConstruct** ✓ | 2025 (arXiv 2502.10197, ETH) | **Constructive** proofs — build an object with prescribed properties (matrices, colorings, permutations) | ~127 (121 after revision — verify) | Per-problem **programmatic Python verifier** checks the object, not the prose | ~41%→~60% best LLM (version-dependent) | Open, MIT | **HIGH** — matches "construct an exact object, verify it computationally"; template for CAS-checked construction |
| **FrontierMath** (again) | 2024–26 | Research-level, exact answers | 350 | Answers exact-symbolic; ships <1-min check scripts | o3 25.2% (Dec-2024; superseded — reconfirm) | Gated | **HIGH** — heavy computation rewarded |
| **SRBench(++)** ✓ | 2024–25 | Symbolic regression (recover closed form from data) | 20+ datasets | **SymPy equivalence** = the scoring oracle | method-dependent | Open | **MED** — CAS-as-ground-truth pattern; method-benchmark, not LLM-prompting |
| **Literature-faithfulness** (citation-correctness) evals | 2025 | Does the agent cite *real* theorems correctly? | varies | — | — | varies | **MED** — matches the provenance-checked retrieval (theoremsearch/matlas) |

> **Genuine gap worth naming in the paper:** as of this search there is **no dedicated LLM
> benchmark built on GAP or Magma** as the required backend (only general "LLMs can emit
> Sage/GAP code" observations). Since Albilich uses **GAP** for finite group computation, this
> is both a positioning opportunity and a candidate contribution (you could release a
> GAP-oracle group-theory benchmark).

---

## Tier 6 — Formal (Lean/Isabelle/Rocq) — positioning only, needs an autoformalization bridge

Albilich is informal, so these are relevant **only** if (a) you add an autoformalization arm,
or (b) you attempt their *natural-language source problems* in informal mode and grade against
known answers. Include one or two for positioning against the formal SOTA line (AlphaProof,
Seed-Prover, Kimina, Goedel, DeepSeek-Prover).

| Benchmark | Size | SOTA (approx, reconfirm) | Note for Albilich |
|---|---|---|---|
| **PutnamBench** | ~660 (Lean ~640 / Isabelle ~640 / Rocq ~412) | Seed-Prover **>50%** ✓ | **NL source problems are directly attemptable informally** — best formal set to bridge |
| **miniF2F** | 244 | **Saturating** — Seed-Prover "saturates" ✓; Kimina ~80%+ pass@large | Low remaining signal; skip unless positioning |
| **ProofNet** | 371 (undergrad) | — | Autoformalization + proof; undergrad NL statements attemptable |
| **FormalMATH** | 5,560 | — | Large; autoformalization-heavy |
| **CombiBench** ✓ | 100 (combinatorics, Lean 4) | Kimina-Prover **7/100** (bottleneck is formalization, not counting) | **Domain match (combinatorics).** Its **fill-in-the-blank mode = enumerate-then-formalize** — precisely where a GAP/Sage finite computation is the natural tool. Best combinatorics-specific benchmark for the CAS thesis |
| **Ax-Prover** (new Lean **abstract-algebra** benchmark) ✓ | 2025 (arXiv 2510.12787) | Multi-agent Lean proving; ships a dedicated **abstract-algebra** Lean set | — | "largely outperforms" specialist provers on it | The closest thing to a dedicated **algebra** theorem-proving benchmark — worth attempting if you add a formal arm |
| **FIMO / ProverBench / Lean Workbook** | varies | — | Formal-arm extras |

**Formal-SOTA context (reconfirm before citing):** Seed-Prover (arXiv 2507.23726) — 78.1% of
formalized past IMO, saturates miniF2F, >50% PutnamBench, 5/6 IMO 2025 ✓; Kimina-Prover — ~80.7%
pass@8192 miniF2F (lead from a session source, verify). DeepSeek-Math-V2 reports on IMO-ProofBench
with self-verifiable proofs (a strong *informal-adjacent* baseline to compare against).

---

## Related AI-for-math systems & competitive context (positioning / related work — NOT benchmarks)

The reviewers will judge Albilich against these; the paper's related-work section needs them.

- **DeepMind "AI co-mathematician" (Gemini-based, agentic) — reportedly CLOSED Kourovka 21.10**
  (Lackenby, Oxford; ~May 2026): AI drafted a proof, a reviewer agent flagged a gap, a human
  filled it, AI completed it; the same system reached **~48% on FrontierMath Tier 4**. This is
  the **direct competitor** — an agentic system working the *same Kourovka notebook* Albilich
  targets. Position Albilich's differentiators explicitly against it (open pipeline, CAS/GAP
  grounding, verifier+refuter, informal-with-rigor). ⚠ one-off collaboration, not a benchmark —
  and its Kourovka claim is worth independently confirming before citing.
- **CayleyPy Growth** (arXiv 2509.19162, 2025): open Python library computing Cayley/Schreier
  graphs ~1000× faster than **GAP and Sage**; generated **200+ new group-theory conjectures**
  (symmetric-group Cayley-graph diameters, Babai-conjecture refinements, Glushkov's 1968
  question). Algorithmic (not LLM), but the nearest systematic **AI-for-group-theory** effort —
  cite as the computational-discovery neighbor.
- **Auto-conjecturing / construction-discovery lineage** (Albilich's open-problem angle sits
  here): FunSearch (cap sets), AlphaEvolve, PatternBoost (combinatorial constructions),
  TxGraffiti / "The Optimist" (graph-theory conjecturing), Ramanujan Machine (identities).
- **CAS-grounded research case study:** Claude + SageMath cutting a ~60-hour quantum-group
  symbolic computation to <1 min (arXiv 2605.02994) — anecdotal support for the CAS thesis.
- **Naming trap to avoid:** "GroupToM-Bench" (arXiv 2606.04184) is *Group Theory of **Mind***
  (social reasoning), NOT mathematical group theory. Do not cite it.

## Two confirmed open niches (candidate contributions, not just gaps)

Both were confirmed by a direct arXiv sweep this session, not assumed:
1. **No LLM benchmark exists on group theory or the Kourovka notebook** — for a group-theory
   specialist, releasing one (with a GAP oracle) would be a standalone contribution.
2. **No LLM benchmark is grounded on GAP** (existing CAS-grounded evals use SageMath or Lean).
   Albilich's GAP grounding is genuinely unoccupied territory.

## Recommended starter set (what to actually run first)

1. **IMProofBench** (77, private) — agentic + SageMath + research-level proof: *the closest
   external mirror of Albilich's own design.* Request access first; it's the headline comparison.
2. **IMO-ProofBench** (60) — flagship NL-proof measure, public rubric. *Core, self-runnable.*
3. **MathArena proof track** — newest USAMO/IMO/Putnam, contamination-free. *Credibility.*
4. **ProofBench/ProofGrader** (145) — fine-grained proof grading. *Depth.*
5. **ProcessBench + REFUTE** — verifier + refuter as first-class capabilities. *Differentiators.*
6. **Erdős Problems** — the closest *public* open-problem eval to Kourovka work; run it to show
   the open-problem capability on neutral ground. *Truest research-novelty signal.*
7. **FrontierMath** (via Epoch; Tier 4) — hardest answer-checkable, Python/CAS allowed by design.
   *Frontier + computation; the DeepMind competitor is benchmarked here.*
8. **CombiBench (fill-in-the-blank) + PutnamBench algebra slice (28 abstract-algebra / 253
   algebra)** — domain-matched formal sets; bridge to the formal-SOTA conversation. *Positioning.*
9. A thin comparability layer: **AIME 2025+**, **HMMT 2025**, one **OlympiadBench/Omni-MATH/HARP**
   slice — report but frame as under-measuring proof quality.

## Cross-cutting cautions
- **Contamination:** anything ≤2024 (AIME-2024, MATH, miniF2F) risks train-set leakage; prefer
  post-2024 and live (MathArena) for headline claims.
- **Answer-only vs proof-graded:** report both, but frame proof-graded as the true measure —
  the USAMO-2025 ~5% result is the canonical illustration of why.
- **Gated/private sets** (FrontierMath, IMProofBench) can't be self-scored; you run via their
  harness or submit — plan lead time.
- **The genuine gap:** no public benchmark yet tests *advancing open problems* or *autonomous
  research* the way Albilich targets — worth stating explicitly as motivation and future work.

## Provenance note
Compiled under heavy API turbulence (parallel research agents failed on stream errors; session
search budget exhausted). Items marked ✓ were verified against primary sources this session
(IMO-Bench/imobench.github.io, ProofGrader, Seed-Prover arXiv:2507.23726, IMProofBench
arXiv:2509.26076). Unmarked items are from standing knowledge to an early-2026 cutoff and should
be reconfirmed against the source before appearing in the paper.
