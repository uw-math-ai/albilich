# Albilich v1 Report: kourovka/problem_17_91_benchmark_no_cas_1h_20260721

- Outcome: verified_partial
- Public status: certified_partial_progress
- Result kind: partial
- Result classification: partial_progress
- Relation to target: unknown
- Result summary: The root theorem is not solved; verified non-root claims are available as certified partial progress.
- Completion policy: full_proof_first
- Revision: 38
- Claims: 7 total, 5 verified, 4 integrated
- Routes: 5 total, 1 active
- Active debts: 4 total, 3 blocking
- Tokens: 9981614 reported spent, 78474227 remaining, 12000000 reserved
- Run status: stopped
- Wall-clock elapsed since run start: 1h 3m 40s
- Active backend compute (child-session wall time): 1h 30m 11s
- Paused time (excluded from active compute): 0s across 0 pause interval(s)
- Peak recorded child memory: 106.9 MB
- Stored memory artifacts: 56.78 KB (58138 bytes)
- Native result directory: 4.42 MB (4631214 bytes)
- Downloaded source directory: 0 bytes

## Root Statement

# Kourovka Notebook Problem 17.91

## Problem

Let \(d(X)\) denote the derived length of a group \(X\).

1. Does there exist an absolute constant \(k\) such that
   \[
   d(G)-d(M)\leq k
   \]
   for every finite soluble group \(G\) and every maximal subgroup \(M\) of
   \(G\)?
2. Find the minimum \(k\) with this property.

## Benchmark Quantitative Snapshot

| Quantity | Albilich v1 benchmark run |
| --- | ---: |
| Iterations / generator calls | 20 |
| Wall-clock elapsed (seconds) | 3819.952 |
| Active compute wall time (seconds) | 5410.717 |
| Active compute wall time (hours) | 1.50 |
| Paused time (seconds) | 0.000 |
| Reported tokens | 9981614 |
| Search / theorem-retrieval calls | 1 |
| Verifier-call estimate | 11 |
| Advisor / reducer calls | 3 |
| Stored memory artifacts | 58138 bytes |
| Native result directory | 4631214 bytes |
| Downloaded source directory | 0 bytes |

Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.

Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; active compute is the recorded child-session wall time; paused time covers explicit run-pause intervals and is excluded from active compute.

## Run Control Events

- `2026-07-21T12:35:58.210389+00:00` `running -> completed` [workflow] scheduler stopped: stop_with_partial_results (stop_reason_code=exhausted_budget)
- `2026-07-21T12:35:58.440726+00:00` `completed -> running` [workflow] workflow started; clearing already-honored run_status completed
- `2026-07-21T12:36:22.909952+00:00` `running -> stopped` [workflow_exception] workflow aborted by _WorkflowTerminationSignal: received signal 15

## Certified Partial Results

- `c_core_abelian_bound_rev0` `informally_verified` `partial`: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
- `c_core_complexity_module_obstruction_rev20` `informally_verified` `partial`: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b. Writing P=G/K, V=F(P)=N/K, L=G^(b), and B=K', one has P^(b)=V, G=LM, L∩M=L∩K, L''=A=G^(b+2)≠1, and W=L'B/B is a nonzero P-submodule of K/B. Moreover L' is a G-normal lift of W satisfying (L')'=A.
- `c_core_monolith_lift_dichotomy_rev26` `informally_verified` `partial`: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexample theorem. Then every nontrivial G-normal subgroup contained in K contains A. Moreover either A≤Phi(G), or G=A⋊H and M=A⋊J for a sharp gap-two pair with J maximal in H, d(H)=b+2, d(J)=b, Core_H(J)=H∩K, and a recursive operator filtration V_0=A, V_(i+1)=[V_i,J^(i)] satisfying V_1=A, V_b=0, b≥3, and 0<V_t<A at its first drop for some 2≤t≤b-1. If d(K)=2 and |A| is a power of p, then K' is a p-group containing A in every nonzero G-invariant subgroup, and either A≤Z(K), or K/C_K(A) is a nontrivial abelian p'-group with [A,K]=A; the latter alternative necessarily holds in the split case.
- `c_lower_bound_two_rev0` `informally_verified` `partial`: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.
- `c_minimal_counterexample_shape_rev0` `informally_verified` `partial`: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap d(G)-d(M)=3, and a unique minimal normal subgroup A of G contained in K'. Moreover A=G^(d(G)-1), d(G/A)=d(G)-1, d(M/A)=d(M), and d(G/A)-d(M/A)=2.

## Remaining Obligations

- major: Determine whether core extensions can create a third unmatched derived layer. A primitive-quotient argument alone is insufficient: the pair SL(2,3)>C6 has quotient gap 1 but original gap 2. Prove a universal upper bound of 2 by controlling derived layers inside core_G(M), or produce and validate a finite soluble pair with gap at least 3.
- blocking: Rule out, or explicitly construct, the minimal-counterexample package from c_minimal_counterexample_shape_rev0: a finite soluble pair with nonabelian core K and unique A=G^(d(G)-1)≤K' such that the quotient pair has gap 2 while d(M/A)=d(M). The first sharply bounded case is d(K)=2 with ε=d(G/K)-d(M/K)=1. A proof of impossibility completes the root with minimum k=2; a construction produces a genuine gap-3 example.
- blocking: Metabelian-core bridge: under the complete hypotheses of c_core_complexity_module_obstruction_rev20, prove that W=L'K'/K' must be zero, equivalently L'≤K', or construct an actual finite soluble pair satisfying every original compatibility, maximality, core, irreducibility, uniqueness-of-A, and exact derived-length condition with W≠0. An abstract P-module or extension without reconstruction of the original pair does not resolve the debt.
- blocking: Metabelian-core closure after c_core_monolith_lift_dichotomy_rev26: assuming d(K)=2, rule out or explicitly realize one of the two exhaustive packages. (F) A≤Phi(G), B=K' is an abelian p-group whose every nonzero G-invariant subgroup contains A, and the nonsplit Frattini lift has G^(b+2)=A while M^b=1. (S) A is complemented, b≥3, G=A⋊H and M=A⋊J with Core_H(J)=H∩K, the core acts through a nontrivial abelian p'-group on A, the H-operator filtration stays equal to A through index b+2, but the J-filtration has a first proper nonzero drop 0<V_t<A for 2≤t≤b-1 and ends at V_b=0. Any proof or construction must preserve maximality, the exact core, and all derived-length equalities.
- The root theorem still requires an exact, equivalent, or stronger verified route.

## Route Scoreboard

- `route_minimal_counterexample_shape_rev0` `verified_part` score=2.72 root_distance=1 verified=1/1
- `route_core_monolith_lift_dichotomy_rev26` `promising` score=2.43 root_distance=1 verified=1/1
- `route_core_complexity_module_obstruction_rev20` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_core_abelian_bound_rev0` `stalled` score=1.1 root_distance=1 verified=1/1 reasons=['advisor or triage report paused this stale route']
- `route_lower_bound_two_rev0` `stalled` score=1.04 root_distance=1 verified=1/1 reasons=['advisor or triage report paused this stale route']

## Branches

- Parallel branch mode: `multi_branch_research` with up to 3 simultaneous branch workers

```text
Branch: route_minimal_counterexample_shape_rev0
Goal: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap d(G)-d(M)=3, and a unique minimal normal subgroup A of G contained in K'. Moreo...
Status: keep_exploiting
Verified facts: c_minimal_counterexample_shape_rev0: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap...; c_core_abelian_bound_rev0: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_monakhov_2004_lemma4_primitive_soluble: Lemma 4. Let G be a finite primitive soluble group with primitivator M. Then (1) Phi(G)=1; (2) F(G)=C_G(F(G))=O_p(G), and F(G) is an elementary abelian p-group of order p^n for...
Next recommended lemma: extend the verified chain toward the branch goal: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap d(G)-d(M)=3, and a unique minimal normal subgroup A of G contained in K'. Moreo...
Similar lemmas worth trying: prove a special case of the branch goal first: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap d(G)-d(M)=3, and a unique minimal normal subgroup A of G contained in K'. Moreo...; prove a bridge lemma connecting the verified branch facts to: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap d(G)-d(M)=3, and a unique minimal normal subgroup A of G contained in K'. Moreo...
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim c_minimal_counterexample_shape_rev0 verified (at 2026-07-21T11:54:03.831657+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim c_minimal_counterexample_shape_rev0 verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_core_monolith_lift_dichotomy_rev26
Goal: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexample theorem. Then every nontrivial G-normal subgroup contained in K contains A. Mo...
Status: keep_exploiting
Verified facts: c_core_monolith_lift_dichotomy_rev26: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexampl...; c_minimal_counterexample_shape_rev0: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: art_villain_split_direct_drop_stress_rev30 (construction_failure): not_refuted
Useful sources: card_monakhov_2004_lemma4_primitive_soluble: Lemma 4. Let G be a finite primitive soluble group with primitivator M. Then (1) Phi(G)=1; (2) F(G)=C_G(F(G))=O_p(G), and F(G) is an elementary abelian p-group of order p^n for...
Next recommended lemma: extend the verified chain toward the branch goal: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexample theorem. Then every nontrivial G-normal subgroup contained in K contains A. Mo...
Similar lemmas worth trying: prove a special case of the branch goal first: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexample theorem. Then every nontrivial G-normal subgroup contained in K contains A. Mo...; prove a bridge lemma connecting the verified branch facts to: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexample theorem. Then every nontrivial G-normal subgroup contained in K contains A. Mo...
Failed methods (do not retry unchanged): art_villain_split_direct_drop_stress_rev30: not_refuted [fingerprint counterexample_construction_failed]
Last useful delta: verified_claim: claim c_core_monolith_lift_dichotomy_rev26 verified (at 2026-07-21T12:33:33.125243+00:00)
Passes since useful delta: 1
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim c_core_monolith_lift_dichotomy_rev26 verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_core_complexity_module_obstruction_rev20
Goal: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b. Writing P=G/K, V=F(P)=N/K, L=G^(b), and B=K', one has P^(b)=V, G=LM, L∩M=L∩K,...
Status: keep_exploiting
Verified facts: c_core_complexity_module_obstruction_rev20: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b...; c_minimal_counterexample_shape_rev0: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_monakhov_2004_lemma4_primitive_soluble: Lemma 4. Let G be a finite primitive soluble group with primitivator M. Then (1) Phi(G)=1; (2) F(G)=C_G(F(G))=O_p(G), and F(G) is an elementary abelian p-group of order p^n for...
Next recommended lemma: extend the verified chain toward the branch goal: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b. Writing P=G/K, V=F(P)=N/K, L=G^(b), and B=K', one has P^(b)=V, G=LM, L∩M=L∩K,...
Similar lemmas worth trying: prove a special case of the branch goal first: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b. Writing P=G/K, V=F(P)=N/K, L=G^(b), and B=K', one has P^(b)=V, G=LM, L∩M=L∩K,...; prove a bridge lemma connecting the verified branch facts to: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b. Writing P=G/K, V=F(P)=N/K, L=G^(b), and B=K', one has P^(b)=V, G=LM, L∩M=L∩K,...
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim c_core_complexity_module_obstruction_rev20 verified (at 2026-07-21T12:15:12.337022+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim c_core_complexity_module_obstruction_rev20 verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_core_abelian_bound_rev0
Goal: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
Status: pause_or_merge
Verified facts: c_core_abelian_bound_rev0: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_monakhov_2004_lemma4_primitive_soluble: Lemma 4. Let G be a finite primitive soluble group with primitivator M. Then (1) Phi(G)=1; (2) F(G)=C_G(F(G))=O_p(G), and F(G) is an elementary abelian p-group of order p^n for...
Next recommended lemma: extend the verified chain toward the branch goal: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
Similar lemmas worth trying: prove a special case of the branch goal first: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.; prove a bridge lemma connecting the verified branch facts to: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim c_core_abelian_bound_rev0 verified (at 2026-07-21T11:53:35.543845+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim c_core_abelian_bound_rev0 verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_lower_bound_two_rev0
Goal: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.
Status: pause_or_merge
Verified facts: c_lower_bound_two_rev0: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_monakhov_2004_lemma4_primitive_soluble: Lemma 4. Let G be a finite primitive soluble group with primitivator M. Then (1) Phi(G)=1; (2) F(G)=C_G(F(G))=O_p(G), and F(G) is an elementary abelian p-group of order p^n for...
Next recommended lemma: extend the verified chain toward the branch goal: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.
Similar lemmas worth trying: prove a special case of the branch goal first: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.; prove a bridge lemma connecting the verified branch facts to: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim c_lower_bound_two_rev0 verified (at 2026-07-21T11:55:03.685708+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim c_lower_bound_two_rev0 verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

## Research Strategy

Strategic artifacts are persisted proof-state context, not verified mathematical evidence.

- Latest global advisor synthesis: `none`
- Latest active proof compression: `none`
- Bridge search: `none`; candidates=0, selected=`none`
- Conjecture portfolio: `none`; candidates=0, selected=`none`
- Active invention authorization: `none`
- Global synthesis due: `False`; reasons=[]
- Graph-derived decisive obligation: `none`; selected route=`route_core_monolith_lift_dichotomy_rev26`, ready_for_verification=True
- Verifier-filtered outcome learning: family=`research`; local families=0; reference_solution_used=False
- Deep-session ROI: allowed=True; reason=deep-session ROI gate is open
- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.
- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.

## Fact Graph

Read-only graph view generated from claims, routes, inferences, debts, and sources.

- Nodes: verified_fact=10, candidate_fact=2, obstruction=4, source_fact=1, branch_cluster=5
- Edges: uses=3, depends_on=3, blocks=4, repairs=0, same_as=0, supersedes=0
- Edge types awaiting a data source (not derived): contradicts, generalizes, specializes
- Branch depth report:
  - `route_core_abelian_bound_rev0` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_lower_bound_two_rev0` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_minimal_counterexample_shape_rev0` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_core_complexity_module_obstruction_rev20` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_core_monolith_lift_dichotomy_rev26` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)

## Retrieval Cards

- `card_monakhov_2004_lemma4_primitive_soluble` `partial_match` confidence=high: Lemma 4. Let G be a finite primitive soluble group with primitivator M. Then (1) Phi(G)=1; (2) F(G)=C_G(F(G))=O_p(G), and F(G) is an elementary abelian p-group of order p^n for some prime p; (3) G contains a unique minimal normal subgroup, which coincides with F(G); (4) G=[F(G)]M and O_p(M)=1; (5) M is isomorphic to an irreducible subgroup of GL(n,p). The source-view OCR renders 'unique' incorrectly as 'trivial'; the surrounding assertions and the standard primitive-soluble-group theorem fix the reading.

## Claims

- `c_core_complexity_module_obstruction_rev20` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, let K=Core_G(M), put b=d(M), r=d(K), and epsilon=d(G/K)-d(M/K). Then r+epsilon≥3. If r=2, then epsilon=1 and d(M/K)=b. Writing P=G/K, V=F(P)=N/K, L=G^(b), and B=K', one has P^(b)=V, G=LM, L∩M=L∩K, L''=A=G^(b+2)≠1, and W=L'B/B is a nonzero P-submodule of K/B. Moreover L' is a G-normal lift of W satisfying (L')'=A.
- `c_core_monolith_lift_dichotomy_rev26` `informally_verified` `active` `partial_result` maturity=verified root_distance=1: Let (G,M) be a minimal-order counterexample to d(G)-d(M)≤2, put b=d(M) and K=Core_G(M), and let A=G^(b+2)≤K' be the minimal normal subgroup supplied by the minimal-counterexample theorem. Then every nontrivial G-normal subgroup contained in K contains A. Moreover either A≤Phi(G), or G=A⋊H and M=A⋊J for a sharp gap-two pair with J maximal in H, d(H)=b+2, d(J)=b, Core_H(J)=H∩K, and a recursive operator filtration V_0=A, V_(i+1)=[V_i,J^(i)] satisfying V_1=A, V_b=0, b≥3, and 0<V_t<A at its first drop for some 2≤t≤b-1. If d(K)=2 and |A| is a power of p, then K' is a p-group containing A in every nonzero G-invariant subgroup, and either A≤Z(K), or K/C_K(A) is a nontrivial abelian p'-group with [A,K]=A; the latter alternative necessarily holds in the split case.
- `root` `untested` `active` `root_theorem` maturity=verifier_gap root_distance=0: # Kourovka Notebook Problem 17.91

## Problem

Let \(d(X)\) denote the derived length of a group \(X\).

1. Does there exist an absolute constant \(k\) such that
   \[
   d(G)-d(M)\leq k
   \]
   for every finite soluble group \(G\) and every maximal subgroup \(M\) of
   \(G\)?
2. Find the minimum \(k\) with this property.
- `c_core_abelian_bound_rev0` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite soluble group, M a maximal subgroup, and K=Core_G(M). If K is abelian, then d(G)-d(M)≤2; if K=1, then d(G)-d(M)≤1.
- `c_lower_bound_two_rev0` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Any absolute constant in the root problem is at least 2. Explicitly, for G=Q8⋊C3 where C3 cyclically permutes i,j,k, the subgroup M=Z(Q8)×C3 is cyclic maximal, d(G)=3, and d(M)=1.
- `c_minimal_counterexample_shape_rev0` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: If a pair (G,M) with G finite soluble and M maximal violates d(G)-d(M)≤2, then a pair of minimal |G| among all such violations has nonnormal M, nonabelian K=Core_G(M), exact gap d(G)-d(M)=3, and a unique minimal normal subgroup A of G contained in K'. Moreover A=G^(d(G)-1), d(G/A)=d(G)-1, d(M/A)=d(M), and d(G/A)-d(M/A)=2.
- `claim_gap_at_least_two_sl2_3` `plausible` `active` `main_trunk` maturity=proposed root_distance=1: There exists a finite soluble group G with a maximal subgroup M such that d(G)-d(M)=2; specifically, one may take G=SL(2,3) and M the cyclic order-six inverse image of a maximal C3 subgroup under SL(2,3)→A4. Hence any absolute constant satisfying the root problem must be at least 2.

## Active Proof Debts

- `debt_root_core_lift_gap` `major` on `root`: Determine whether core extensions can create a third unmatched derived layer. A primitive-quotient argument alone is insufficient: the pair SL(2,3)>C6 has quotient gap 1 but original gap 2. Prove a universal upper bound of 2 by controlling derived layers inside core_G(M), or produce and validate a finite soluble pair with gap at least 3.
- `debt_nonabelian_core_one_layer_rev0` `blocking` on `root`: Rule out, or explicitly construct, the minimal-counterexample package from c_minimal_counterexample_shape_rev0: a finite soluble pair with nonabelian core K and unique A=G^(d(G)-1)≤K' such that the quotient pair has gap 2 while d(M/A)=d(M). The first sharply bounded case is d(K)=2 with ε=d(G/K)-d(M/K)=1. A proof of impossibility completes the root with minimum k=2; a construction produces a genuine gap-3 example.
- `debt_metabelian_core_operator_lift_rev20` `blocking` on `root`: Metabelian-core bridge: under the complete hypotheses of c_core_complexity_module_obstruction_rev20, prove that W=L'K'/K' must be zero, equivalently L'≤K', or construct an actual finite soluble pair satisfying every original compatibility, maximality, core, irreducibility, uniqueness-of-A, and exact derived-length condition with W≠0. An abstract P-module or extension without reconstruction of the original pair does not resolve the debt.
- `debt_metabelian_frattini_operator_exclusion_rev26` `blocking` on `root`: Metabelian-core closure after c_core_monolith_lift_dichotomy_rev26: assuming d(K)=2, rule out or explicitly realize one of the two exhaustive packages. (F) A≤Phi(G), B=K' is an abelian p-group whose every nonzero G-invariant subgroup contains A, and the nonsplit Frattini lift has G^(b+2)=A while M^b=1. (S) A is complemented, b≥3, G=A⋊H and M=A⋊J with Core_H(J)=H∩K, the core acts through a nontrivial abelian p'-group on A, the H-operator filtration stays equal to A through index b+2, but the J-filtration has a first proper nonzero drop 0<V_t<A for 2≤t≤b-1 and ends at V_b=0. Any proof or construction must preserve maximality, the exact core, and all derived-length equalities.
