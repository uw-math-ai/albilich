# Albilich v1 Report: kourovka/problem_20_2_totally_3_closed_lie_type_noadvisor_ablation_5h_20260727

- Outcome: solved_final
- Public status: solved
- Result kind: stronger
- Result classification: full_theorem_solved
- Relation to target: stronger
- Result summary: Solved by a verified stronger theorem whose implication to the target was checked.
- Completion policy: full_proof_first
- Revision: 33
- Claims: 4 total, 1 verified, 1 integrated
- Routes: 1 total, 0 active
- Active debts (ledger only): 3 total, 3 blocking
- Tokens: 6306998 reported spent, 78561395 remaining, 12000000 reserved
- Run status: completed
- Wall-clock elapsed since run start: 1h 46m 48s
- Active backend compute (child-session wall time): 2h 8m 20s
- Paused time (excluded from active compute): 0s across 0 pause interval(s)
- Peak recorded child memory: 288.5 MB
- Stored memory artifacts: 293.54 KB (300580 bytes)
- Native result directory: 5.24 MB (5490299 bytes)
- Downloaded source directory: 0 bytes

## Root Statement

# Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type

## Problem

Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set
\(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is
the largest subgroup of \(\operatorname{Sym}(\Omega)\) whose orbits on the set
\(\Omega^{k}\) of ordered \(k\)-tuples coincide with the orbits of \(G\) on
\(\Omega^{k}\) (Wielandt). The group \(G\) is **\(k\)-closed** on \(\Omega\) if
\(G^{(k)} = G\).

An abstract group \(G\) is **totally \(k\)-closed** if for every faithful
permutation representation of \(G\) on a finite set \(\Omega\), the image of
\(G\) in \(\operatorname{Sym}(\Omega)\) is \(k\)-closed.

**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type
which are totally 3-closed?

Known context: the finite nonabelian simple totally 2-closed groups are
completely classified — there are exactly six, all sporadic groups
(\(\mathrm{J}_1\), \(\mathrm{J}_3\), \(\mathrm{J}_4\), \(\mathrm{Ly}\),
\(\mathrm{Th}\), and the Monster \(\mathrm{M}\)), the largest being the Monster.
Since a totally 2-closed group is totally 3-closed, the real content of the
question is whether total 3-closure can occur for simple groups of Lie type,
where total 2-closure provably cannot.

## Instructions

Treat this as a serious research problem, not only as a benchmark. The target is
to either exhibit a nonabelian simple group of Lie type that is totally
3-closed (with proof), or prove that no nonabelian simple group of Lie type is
totally 3-closed, or establish an honest, precisely stated partial result.

Use direct proof attempts before reducing unless a reduction is mathematically
motivated. Literature search and citations are allowed, and cited theorems may
be used to close a case when the statement is properly identified and logically
applied. The classification of totally 2-closed simple groups and the toolkit
around \(k\)-closures of permutation groups (Wielandt's theory, Praeger–Saxl,
recent work of Abdollahi, Arezoomand, Tracey and coauthors on total
\(k\)-closure) are natural starting points. If an exact published result
answers the question, integrate it responsibly instead of reproving it.

Group-theoretic computation (e.g. GAP) may be used for examples, sanity checks,
and small Lie-type groups: computing \(3\)-closures of specific faithful
permutation representations of small groups such as \(\mathrm{PSL}(2,q)\) for
small \(q\) is encouraged as evidence, and a single faithful representation
that fails to be 3-closed rules that group out. The final argument must be a
mathematical proof or a mathematically rigorous obstruction; finite
computations alone settle individual groups, not the general question, unless
combined with a reduction theorem.

## Benchmark Quantitative Snapshot

| Quantity | Albilich v1 benchmark run |
| --- | ---: |
| Iterations / generator calls | 18 |
| Wall-clock elapsed (seconds) | 6408.161 |
| Active compute wall time (seconds) | 7699.857 |
| Active compute wall time (hours) | 2.14 |
| Paused time (seconds) | 0.000 |
| Reported tokens | 6306998 |
| Search / theorem-retrieval calls | 1 |
| Verifier-call estimate | 3 |
| Advisor / reducer calls | 2 |
| Stored memory artifacts | 300580 bytes |
| Native result directory | 5490299 bytes |
| Downloaded source directory | 0 bytes |

Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.

Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; active compute is the recorded child-session wall time; paused time covers explicit run-pause intervals and is excluded from active compute.

## Run Control Events

- `2026-07-26T19:27:49.108100+00:00` `running -> completed` [workflow] scheduler stopped: stop_solved

## Final Proof

# A nonabelian simple group of Lie type that is totally 3-closed

## Theorem

There exists a nonabelian simple group of Lie type that is totally 3-closed. More precisely, the group \(G=\operatorname{PSL}_2(7)\), of Lie type \(A_1(7)\), is totally 3-closed.

Thus the stronger, explicit-witness statement proved below answers Problem 20.2 affirmatively.

## Finite certificate

We first record the exact finite information used in the proof. The standard permutation realization of \(G=\operatorname{PSL}_2(7)\) has order \(168\). GAP 4.16.0 enumerates exactly fourteen conjugacy classes of proper subgroups \(H<G\). For each representative it constructs the coset action \(P_H\) on \(G/H\).

For any permutation group \(P\), one has \(P^{(3)}\leq P^{(2)}\): a permutation preserving every orbit on ordered triples also preserves every orbit on ordered pairs, as an ordered pair \((a,b)\) may be encoded by the repeated-coordinate triple \((a,b,b)\). The certificate therefore begins with the exact group \(P_H^{(2)}\). It then lists the \(P_H\)-orbits on ordered triples and successively intersects \(P_H^{(2)}\) with their setwise stabilizers. The resulting intersection is precisely \(P_H^{(3)}\), because it is the full subgroup preserving every \(P_H\)-orbit on ordered triples. The computation gives the following table.

| Index | Structure of \(H\) | Degree | \(|P_H^{(2)}|\) | \(|P_H^{(3)}|\) |
|---:|:---|---:|---:|---:|
| 1 | \(S_4\) | 7 | 5040 | 168 |
| 2 | \(S_4\) | 7 | 5040 | 168 |
| 3 | \(C_7:C_3\) | 8 | 40320 | 168 |
| 4 | \(A_4\) | 14 | 645120 | 168 |
| 5 | \(A_4\) | 14 | 645120 | 168 |
| 6 | \(D_8\) | 21 | 168 | 168 |
| 7 | \(C_7\) | 24 | 336 | 168 |
| 8 | \(S_3\) | 28 | 168 | 168 |
| 9 | \(C_2\times C_2\) | 42 | 168 | 168 |
| 10 | \(C_2\times C_2\) | 42 | 168 | 168 |
| 11 | \(C_4\) | 42 | 168 | 168 |
| 12 | \(C_3\) | 56 | 168 | 168 |
| 13 | \(C_2\) | 84 | 168 | 168 |
| 14 | \(1\) | 168 | 168 | 168 |

Every coset image has order \(168\), so the table proves that all fourteen transitive coset actions are 3-closed.

The certificate also treats every unordered pair of the fourteen action types, including equal types. There are \(14\cdot15/2=105\) such pairs. For a pair with coset images on sets \(X_i\) and \(X_j\), let \(D\cong G\) be the diagonal action on the disjoint union \(X_i\sqcup X_j\). The computation fixes a nonidentity element \(x\in G\), forms the permutation \(q=(1,x)\), and searches the finite sets of mixed triples of patterns \(X_i\times X_j\times X_j\) and \(X_i\times X_i\times X_j\). In every one of the 105 cases it produces a triple \(t\) for which \(t\) and \(t^q\) belong to distinct \(D\)-orbits. Consequently \(q\notin D^{(3)}\) for every pair. The exact GAP code, the complete local output, and all 105 separating triples are contained in the certified finite-computation report listed in the References section.

## Proof

Let \(\Omega\) be an arbitrary finite faithful \(G\)-set, and identify \(G\) with its image in \(\operatorname{Sym}(\Omega)\). Put \(K=G^{(3)}\). We prove that \(K=G\).

First, every element of \(K\) preserves each \(G\)-orbit on \(\Omega\) setwise. Indeed, the \(G\)-orbit of a constant triple \((a,a,a)\) consists exactly of the constant triples \((b,b,b)\) with \(b\in a^G\). Since elements of \(K\) preserve every \(G\)-orbit on ordered triples, they preserve the orbit \(a^G\). In particular, every singleton orbit is fixed pointwise by \(K\).

Let \(\Delta\) be a non-singleton \(G\)-orbit and let \(H\) be the stabilizer of one of its points. Then \(H<G\), and \(\Delta\) is equivalent to the coset action on \(G/H\). The kernel of this action is the core of \(H\), hence a normal subgroup of the simple group \(G\). It cannot be all of \(G\), because \(H\) is proper, so it is trivial. Thus every non-singleton constituent is faithful.

Restricting triples to \(\Delta^3\) shows that the restriction of \(K\) to \(\Delta\) lies in the 3-closure of the corresponding coset image. The finite certificate proves that this local 3-closure is the image of \(G\) itself. Therefore, for each non-singleton orbit \(\Delta\) and each \(s\in K\), there is a unique element \(g_\Delta\in G\) whose action on \(\Delta\) agrees with that of \(s\). Uniqueness follows from faithfulness of the constituent.

We next show that these elements are independent of \(\Delta\). We use the following elementary diagonal lemma. If a subgroup \(L\leq G\times G\) contains the diagonal subgroup
\[
\operatorname{Diag}(G)=\{(g,g):g\in G\},
\]
then either \(L=\operatorname{Diag}(G)\) or \(L=G\times G\). To prove this, define
\[
N=\{y\in G:(1,y)\in L\}.
\]
Conjugation by the diagonal shows that \(N\trianglelefteq G\). Since \(G\) is simple, either \(N=1\) or \(N=G\). If \(N=1\), multiplying an arbitrary \((a,b)\in L\) by \((a^{-1},a^{-1})\) shows that \(a=b\), so \(L\) is diagonal. If \(N=G\), then \(1\times G\leq L\), and this subgroup together with the diagonal generates \(G\times G\).

Now choose two non-singleton orbits \(\Delta\) and \(\Gamma\), allowing them to have the same constituent type. Consider the 3-closure of the diagonal action of \(G\) on \(\Delta\sqcup\Gamma\). Constant triples force it to preserve both constituents, while local 3-closedness embeds it in \(G\times G\). It contains the diagonal copy of \(G\), so the diagonal lemma says that it is either diagonal or the full product. After equivariant identification with the corresponding representatives in the finite certificate, the separating mixed triple shows that the element \((1,x)\) is absent. The full-product alternative is therefore impossible, and the pairwise 3-closure is diagonal. This conclusion is unchanged by replacing either constituent by an isomorphic copy or by conjugating its point stabilizer.

The restriction of \(s\in K\) to \(\Delta\sqcup\Gamma\) belongs to this pairwise 3-closure. Hence \((g_\Delta,g_\Gamma)\) is diagonal and \(g_\Delta=g_\Gamma\). Since the pair was arbitrary, there is one element \(g\in G\) that agrees with \(s\) on every non-singleton orbit. Both \(s\) and \(g\) fix every singleton orbit, so they agree on all of \(\Omega\). Thus \(s=g\), proving \(K\leq G\). The reverse inclusion follows directly from the definition of closure, and consequently \(G^{(3)}=G\).

The faithful finite \(G\)-set \(\Omega\) was arbitrary. Hence \(\operatorname{PSL}_2(7)\) is totally 3-closed. This group is nonabelian simple and is a group of Lie type \(A_1(7)\), so it supplies the required example and answers Problem 20.2 affirmatively.

## References

External reference list: empty. This proof was written by the Albilich writer from the following internal artifacts.

- “Repaired proof dossier for total 3-closure of \(\operatorname{PSL}_2(7)\),” artifact `art_psl2_7_total3_repaired_proof_dossier_r25`, researcher. Supports the reduction to coset constituents, the diagonal lemma, synchronization, and final assembly.
- “Decisive finite experiment for \(G=\operatorname{PSL}_2(7)\),” artifact `art_psl2_7_full_subgroup_cas_r25`, researcher. Supplies the exact GAP 4.16.0 code, all fourteen local 3-closure computations, and all 105 mixed-pair certificates.
- “Strict verification of the repaired \(\operatorname{PSL}_2(7)\) route,” artifact `art_verification_psl2_7_total3_correct_r27`, strict informal verifier. Certifies that the sufficient route is correct with no gaps.
- “Integration of the \(\operatorname{PSL}_2(7)\) route,” artifact `art_integration_psl2_7_total3_root_r29`, integration verifier. Certifies that the explicit witness proves the root existential statement.

## Proved Result

The nonabelian simple group PSL(2,7), of Lie type A1(7), is totally 3-closed.

## Route Scoreboard

- `route_root_via_psl2_7_total3_r21` `verified_part` score=2.9 root_distance=0 verified=1/1

## Branches

- Parallel branch mode: `multi_branch_research` with up to 3 simultaneous branch workers

```text
Branch: route_root_via_psl2_7_total3_r21
Goal: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is the largest subgr...
Status: keep_exploiting
Verified facts: root: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and...
Candidate facts: none recorded
Active blockers: debt_psl2_prime_relative_base_test_r5 (blocking): Resolve the relative-base witness theorem for G=PSL(2,p), p≥7 prime: determine whether there is a core-free H<PGL(2,p) with PGL(2,p)=GH, G not contained in H, and (H∩H^a∩H^b)∩(P...
Failed methods: none recorded
Useful sources: none recorded
Next recommended lemma: prove root: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and...
Similar lemmas worth trying: prove a special case of the branch goal first: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is the largest subgr...; prove a bridge lemma connecting the verified branch facts to: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type ## Problem Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set \(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is the largest subgr...
Failed methods (do not retry unchanged): art_villain_outer_a5_normalizer_probe_r14: not_refuted [fingerprint exceptional_normalizer_candidate_collapses]
Last useful delta: verified_claim: claim root verified (at 2026-07-26T19:24:32.543567+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim root verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

## Research Strategy

Strategic artifacts are persisted proof-state context, not verified mathematical evidence.

- Latest global advisor synthesis: `none`
- Latest active proof compression: `none`
- Bridge search: `art_psl2_7_bridge_lemma_search_r25`; candidates=1, selected=`bridge_psl2_7_local_and_pair_certificate_r25`
- Conjecture portfolio: `none`; candidates=0, selected=`none`
- Active invention authorization: `none`
- Global synthesis due: `False`; reasons=[]
- Graph-derived decisive obligation: `debt_certify_dickson_pgl2_prime_maximals_r9`; selected route=`none`, ready_for_verification=False
- Verifier-filtered outcome learning: family=`research`; local families=0; reference_solution_used=False
- Deep-session ROI: allowed=True; reason=deep-session ROI gate is open
- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.
- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.

## Fact Graph

Read-only graph view generated from claims, routes, inferences, debts, and sources.

- Nodes: verified_fact=2, candidate_fact=3, obstruction=3, source_fact=0, branch_cluster=1
- Edges: uses=0, depends_on=0, blocks=2, repairs=0, same_as=0, supersedes=0
- Edge types awaiting a data source (not derived): contradicts, generalizes, specializes
- Branch depth report:
  - `route_root_via_psl2_7_total3_r21` blocked (depth=0, verified=2, candidate=0, active_obstructions=1, blocked)

## Claims

- `claim_psl2_7_totally_3_closed_r19` `untested` `active` `main_trunk` maturity=proposed root_distance=1: The nonabelian simple group PSL(2,7), of Lie type A1(7), is totally 3-closed.
- `claim_psl2_prime_no_pgl_relative_base_witness_r9` `untested` `active` `main_trunk` maturity=verifier_gap root_distance=1: Let p>=7 be prime, G=PSL(2,p), and X=PGL(2,p). For every proper subgroup H<X with H not contained in G, there exist a,b in X such that H cap H^a cap H^b is contained in G. Consequently no core-free H<X satisfies X=GH and (H cap H^a cap H^b) cap (X minus G) nonempty for all a,b in X.
- `root` `informally_verified` `integrated` `root_theorem` maturity=integrated root_distance=0: # Problem 20.2: Totally 3-closed nonabelian simple groups of Lie type

## Problem

Let \(G \le \operatorname{Sym}(\Omega)\) be a permutation group on a finite set
\(\Omega\), and let \(k \ge 1\). The **\(k\)-closure** \(G^{(k)}\) of \(G\) is
the largest subgroup of \(\operatorname{Sym}(\Omega)\) whose orbits on the set
\(\Omega^{k}\) of ordered \(k\)-tuples coincide with the orbits of \(G\) on
\(\Omega^{k}\) (Wielandt). The group \(G\) is **\(k\)-closed** on \(\Omega\) if
\(G^{(k)} = G\).

An abstract group \(G\) is **totally \(k\)-closed** if for every faithful
permutation representation of \(G\) on a finite set \(\Omega\), the image of
\(G\) in \(\operatorname{Sym}(\Omega)\) is \(k\)-closed.

**Question (Problem 20.2).** Are there any nonabelian simple groups of Lie type
which are totally 3-closed?

Known context: the finite nonabelian simple totally 2-closed groups are
completely classified — there are exactly six, all sporadic groups
(\(\mathrm{J}_1\), \(\mathrm{J}_3\), \(\mathrm{J}_4\), \(\mathrm{Ly}\),
\(\mathrm{Th}\), and the Monster \(\mathrm{M}\)), the largest being the Monster.
Since a totally 2-closed group is totally 3-closed, the real content of the
question is whether total 3-closure can occur for simple groups of Lie type,
where total 2-closure provably cannot.

## Instructions

Treat this as a serious research problem, not only as a benchmark. The target is
to either exhibit a nonabelian simple group of Lie type that is totally
3-closed (with proof), or prove that no nonabelian simple group of Lie type is
totally 3-closed, or establish an honest, precisely stated partial result.

Use direct proof attempts before reducing unless a reduction is mathematically
motivated. Literature search and citations are allowed, and cited theorems may
be used to close a case when the statement is properly identified and logically
applied. The classification of totally 2-closed simple groups and the toolkit
around \(k\)-closures of permutation groups (Wielandt's theory, Praeger–Saxl,
recent work of Abdollahi, Arezoomand, Tracey and coauthors on total
\(k\)-closure) are natural starting points. If an exact published result
answers the question, integrate it responsibly instead of reproving it.

Group-theoretic computation (e.g. GAP) may be used for examples, sanity checks,
and small Lie-type groups: computing \(3\)-closures of specific faithful
permutation representations of small groups such as \(\mathrm{PSL}(2,q)\) for
small \(q\) is encouraged as evidence, and a single faithful representation
that fails to be 3-closed rules that group out. The final argument must be a
mathematical proof or a mathematically rigorous obstruction; finite
computations alone settle individual groups, not the general question, unless
combined with a reduction theorem.
- `obs_exceptional_alternating_lie_not_total3` `plausible` `active` `main_trunk` maturity=proposed root_distance=1: The nonabelian simple Lie-type groups A5≅PSL(2,4)≅PSL(2,5), A6≅PSL(2,9), and A8≅PSL(4,2) are not totally 3-closed, because their faithful natural alternating actions have 3-closures S5, S6, and S8 respectively.

## Active Proof Debts

- `debt_psl2_prime_relative_base_test_r5` `blocking` on `root`: Resolve the relative-base witness theorem for G=PSL(2,p), p≥7 prime: determine whether there is a core-free H<PGL(2,p) with PGL(2,p)=GH, G not contained in H, and (H∩H^a∩H^b)∩(PGL(2,p)\G) nonempty for all a,b. An affirmative uniform construction eliminates the family; a negative subgroup classification kills this normal-overgroup route and requires a nonnormal closure witness or a positive-candidate analysis.
- `debt_certify_dickson_pgl2_prime_maximals_r9` `blocking` on `claim_psl2_prime_no_pgl_relative_base_witness_r9`: Provide an exact source theorem/page for the Dickson maximal-subgroup classification used here: for prime p>=7, every maximal subgroup of PGL(2,p) other than PSL(2,p) is a Borel subgroup, a split- or nonsplit-torus normalizer, or an exceptional A4, S4, A5; verify that A4 and A5 lie in PSL when relevant and certify the p=7 consequence that every A4 in PSL(2,7) lies in an S4. Translate the source conventions and confirm all small exceptions before verification.
- `debt_psl2_7_total3_missing_cas_certificate_r23` `blocking` on `inf_root_via_psl2_7_total3_r21`: Supply the complete bounded CAS experiment report cited as art_psl2_7_total3_full_subgroup_cas_r19, including exact code, output, finite scope, a complete accounting of all 14 proper-subgroup conjugacy classes and their local 3-closures, and certificates for all 105 mixed constituent pairs. Reconcile the dossier's 'five' exceptional classes with its apparent enumeration of six before strict re-verification.
