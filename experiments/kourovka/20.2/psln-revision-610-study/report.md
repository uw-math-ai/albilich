# Albilich v1 Report: kourovka/problem_20_2_psln_family_classification

- Outcome: verified_partial
- Public status: certified_partial_progress
- Result kind: partial
- Result classification: partial_progress
- Relation to target: unknown
- Result summary: The root theorem is not solved; verified non-root claims are available as certified partial progress.
- Completion policy: full_proof_first
- Revision: 610
- Claims: 56 total, 52 verified, 52 integrated
- Routes: 55 total, 0 active
- Active debts: 34 total, 33 blocking
- Tokens: 154772501 reported spent, 53799331 remaining, 12000000 reserved
- Run status: paused
- Wall-clock elapsed since run start: 30h 56m 53s
- Active backend compute (child-session wall time): 30h 0m 32s
- Paused time (excluded from active compute): 16m 19s across 6 pause interval(s)
- Peak recorded child memory: 150.0 MB
- Stored memory artifacts: 1.41 MB (1477236 bytes)
- Native result directory: 118.89 MB (124665523 bytes)
- Downloaded source directory: 0 bytes

## Root Statement

# Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_n(q)\)

## Definitions

For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its
**3-closure** \(G^{(3)}\) is the largest subgroup of
\(\operatorname{Sym}(\Omega)\) having the same orbits as \(G\) on ordered
triples \(\Omega^3\). A finite abstract group is **totally 3-closed** when
every faithful finite permutation representation of it is 3-closed.

## Restricted classification problem

Classify, up to isomorphism, every nonabelian simple group
\[
S=\operatorname{PSL}_n(q)
\]
that is totally 3-closed, for every \(n\geq2\) and every prime power \(q\)
for which \(\operatorname{PSL}_n(q)\) is nonabelian simple.

This run concerns the projective special linear family only. Do not schedule
research on unitary, symplectic, orthogonal, exceptional, twisted, Suzuki, Ree,
or alternating families, except to record a low-rank exceptional isomorphism
needed to avoid double counting a \(\operatorname{PSL}_n(q)\) parameter.

The final result must be an if-and-only-if theorem. It must:

1. prove total 3-closure for every surviving \(\operatorname{PSL}_n(q)\), in
   every faithful finite permutation representation;
2. exclude every other simple \(\operatorname{PSL}_n(q)\) by a uniform theorem
   or an explicit faithful action with strictly larger 3-closure;
3. cover all \(n\), all prime powers \(q\), the simplicity exceptions, and all
   low-rank exceptional isomorphisms;
4. distinguish uniform arguments from computations of bounded finite cases;
5. give exact references, theorem numbers, and checked hypothesis translations
   for every external classification, maximal-subgroup, base-size, or orbit
   theorem used.

## Certified prior premises

The supervising mathematician authorizes the following results from the earlier
Problem 20.2 Albilich ledger as certified premises of this restricted run. They
may be used without reopening their proofs or repeating strict verification.
Preserve their exact scope and cite their proof and integration artifacts in the
final assembly.

1. **Two-orbit reduction.** For a finite nonabelian simple group \(S\), total
   3-closure is equivalent to 3-closedness of every diagonal action on
   \(S/H\sqcup S/K\), for all proper \(H,K<S\), with repetition allowed.
2. **Complete rank-one classification.** Among simple
   \(\operatorname{PSL}_2(q)\), total 3-closure holds exactly when \(q=p\) is
   a prime with \(p\geq7\). In particular, the positive prime cases
   \(p=7,11,13,19\) and all \(p\geq17\), \(p\neq19\), are certified; every
   proper extension-field case \(q=p^f\), \(f>1\), and \(q=5\) is excluded.
3. **Projective outer-witness theorem.** Let \(n\geq3\) and \(q=p^f\). If
   \(f>1\) or \(\gcd(n,q-1)>1\), then \(\operatorname{PSL}_n(q)\) is not
   totally 3-closed. On projective points its 3-closure contains a proper
   semilinear or diagonal extension.

The higher-rank residual family is therefore
\[
q=p\text{ prime},\qquad n\geq3,\qquad \gcd(n,p-1)=1.
\]
For odd \(p\), this forces \(n\) to be odd. For \(p=2\), it leaves every
rank \(n\geq3\), including even ranks, subject to simplicity and exceptional
isomorphisms.
Do not spend sessions reproving the three certified premises. If a genuine
logical inconsistency is discovered, record it precisely, but otherwise treat
these results as fixed inputs.

Authorized provenance is restricted to the PSL-related artifacts in:

- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_import_prior_two_orbit_reduction.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_import_two_orbit_reduction_rev23.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_import_psl27_totally_3closed_rev34.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_psl211_canonical_source_route_rev79.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_claim_psl213_total3closed_rev104.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_root_psl219_total3closed_rev158.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_root_psl2prime_extension_except19_rev125.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_verification_psl2_extension_field_nonclosure_rev162.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_researcher_psl2_extension_field_symbolic_closure_rev166.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_import_psln_projective_nonclosure_rev48.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_verification_import_psln_projective_nonclosure_rev44.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_psl_projective_outer_witness_rev0.md`

Do not use non-PSL artifacts from the earlier ledger as mathematical evidence.

## Research program

Maintain an exhaustive parameter ledger. Each row must end as a certified
survivor, a rigorously excluded family, a finite exception requiring an exact
audit, or one precisely stated theorem-level obstruction.

Run full-proof-first. At regular intervals draft the shortest complete
classification proof and mark every unsupported sentence. Prefer a small
number of high-leverage uniform lemmas to a large inventory of case labels.

Use three genuinely different branches when parallel work is available:

1. a uniform structural proof or reduction for the residual prime-field,
   odd-rank family;
2. an adversarial construction branch seeking an explicit faithful action and
   a proper triple-orbit preserver, testing the full hypotheses;
3. an exact literature and bounded-CAS audit for low-rank parameters,
   exceptional isomorphisms, and any finite residue left by the uniform proof.

Natural graph automorphisms, contragredient duality, flag/Grassmannian actions,
parabolic block systems, diagonal actions on two coset spaces, and
normalizer-coset deck permutations are promising negative mechanisms, but
normalizing the group is not enough: triple-orbit preservation must be proved.
For positive conclusions, checking transitive coset actions alone is not
enough; invoke the certified two-orbit reduction and close every pair of proper
subgroups.

Do not extrapolate a computation beyond its certified finite range. Do not
declare completion while any admissible \((n,q)\) parameter remains uncovered.

## Benchmark Quantitative Snapshot

| Quantity | Albilich v1 benchmark run |
| --- | ---: |
| Iterations / generator calls | 311 |
| Wall-clock elapsed (seconds) | 111412.718 |
| Active compute wall time (seconds) | 108032.386 |
| Active compute wall time (hours) | 30.01 |
| Paused time (seconds) | 979.377 |
| Reported tokens | 154772501 |
| Search / theorem-retrieval calls | 10 |
| Verifier-call estimate | 103 |
| Advisor / reducer calls | 83 |
| Stored memory artifacts | 1477236 bytes |
| Native result directory | 124665523 bytes |
| Downloaded source directory | 0 bytes |

Memory in this table follows the legacy benchmark convention: stored artifact/source directory size, not peak process RSS. Peak RSS is reported separately when the runner can sample it.

Timing convention: wall-clock elapsed runs from problem init to the last recorded activity; active compute is the recorded child-session wall time; paused time covers explicit run-pause intervals and is excluded from active compute.

## Run Control Events

- `2026-07-16T02:25:36.147449+00:00` `running -> pause_requested` [cli] Pause for certified PSL graph import and dashboard repoint
- `2026-07-16T02:33:18.889090+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-16T02:43:16.399797+00:00` `paused -> running` [cli] Resume corrected PSL_n-only scoped state at revision 7
- `2026-07-16T02:50:06.983632+00:00` `running -> pause_requested` [cli] Safe pause after active PSL root session to correct the characteristic-two residual-family wording
- `2026-07-16T02:51:58.002531+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-16T02:53:36.663977+00:00` `paused -> running` [cli] Resume PSL_n-only classification after characteristic-two residual-ledger correction
- `2026-07-17T01:05:33.603859+00:00` `running -> pause_requested` [cli] soft reload duplicate-claim guard after current children finish
- `2026-07-17T01:13:14.004674+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-17T01:14:45.571347+00:00` `paused -> running` [cli] Resume revision 436 with canonical claim graph and concise-symbolic duplicate guard
- `2026-07-17T01:15:36.176264+00:00` `running -> pause_requested` [cli] finish canonicalization by resolving debts owned by superseded central-vector wording
- `2026-07-17T01:18:44.907975+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-17T01:19:38.466106+00:00` `paused -> running` [cli] Resume revision 439 after complete duplicate-claim and stale-debt canonicalization
- `2026-07-17T01:40:21.212846+00:00` `running -> pause_requested` [cli] soft reload scheduler integration and verification fixes
- `2026-07-17T01:45:15.188249+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched
- `2026-07-17T01:47:32.697972+00:00` `paused -> running` [cli] resume revision 455 with parallel integration wave and terminal-inference verifier recovery
- `2026-07-17T09:10:03.009882+00:00` `running -> pause_requested` [cli] User requested focus on PSL_3(3) and the PSL_3(p) family; preserve integrated state while narrowing the active root.
- `2026-07-17T09:15:22.049959+00:00` `pause_requested -> paused` [workflow] pause request honored: current child session finished; no new actions dispatched

## Certified Partial Results

- `claim_import_psl211_totally_3closed` `informally_verified` `partial`: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.
- `claim_import_psl27_totally_3closed` `informally_verified` `partial`: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
- `claim_import_psln_projective_nonclosure` `informally_verified` `partial`: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
- `claim_import_two_orbit_reduction` `informally_verified` `partial`: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
- `claim_root_base2_constituent_synchronization_rev369` `informally_verified` `partial`: Let G act faithfully on two transitive sets Omega_1 and Omega_2. Assume both constituent actions are 3-closed and the action on Omega_1 has a base of size at most two. Then the diagonal action of G on the disjoint union Omega_1 disjoint union Omega_2 is 3-closed.
- `claim_root_binary_antiflag_action_3closed_rev474` `informally_verified` `partial`: For every integer n>=3, let V=F_2^n and G=GL(V). On the set Omega of rank-one idempotents E=v tensor lambda with v nonzero and lambda(v)=1, equivalently on anti-flags (v,ker(lambda)) with v not in ker(lambda), the faithful conjugation action of G is 3-closed.
- `claim_root_binary_c2_orthogonal_graph_pair_obstructions_rev373` `informally_verified` `partial`: Let G=GL_n(2) and α(g)=g^{-T}. If n=dm with m>=3 and H=GL_d(2) wr Sym(m) is the stabilizer of an unordered decomposition into m equal summands, then α moves an H-double coset. The same conclusion holds for every n>=3 when H=O(I_n,2). Consequently the graph-induced permutation on G/H is outside the 2-closure and the 3-closure in both families, so neither family can witness Binary Lemma B.
- `claim_root_binary_twoblock_commutator_rank_separator_rev576` `informally_verified` `partial`: For every d >= 2, let G=GL_(2d)(2), let H=GL_d(2) wr Sym(2) stabilize an unordered decomposition into complementary d-spaces, and let alpha(g)=g^(-T). There are explicit x_d,y_d in G, given by the block matrices in art_researcher_root_binary_twoblock_commutator_rank_separator_rev576, such that no h in H satisfies alpha(x_d)H=hx_dH and alpha(y_d)H=hy_dH simultaneously. The proof uses the independently complement-invariant quantity rho(P,Q,R)=rank([P,Q][Q,R][R,P]), for which the explicit triple has rho(P,Q,R)=1 and rho(P^T,Q^T,R^T)=0. Consequently alpha is not in the 3-closure of the equal two-block decomposition action for any d >= 2.
- `claim_root_binary_twoblock_contragredient_failure_d2_rev486` `informally_verified` `partial`: Let G=GL_4(2), let H=GL_2(2) wr Sym(2) stabilize an unordered decomposition of F_2^4 into complementary 2-spaces, and let α(g)=g^{-T}. There exist x,y in G such that no h in H simultaneously satisfies α(x)H=hxH and α(y)H=hyH. Equivalently, α is not in the 3-closure of the faithful degree-280 action of G on G/H.
- `claim_root_binary_twoblock_contragredient_failure_dge3_rev461` `informally_verified` `partial`: For every d>=3, with G=GL_{2d}(2), H=GL_d(2) wr Sym(2), and alpha(g)=g^{-T}, there exist explicit x_d,y_d in G such that no h in H simultaneously satisfies alpha(x_d)H=hx_dH and alpha(y_d)H=hy_dH. Hence alpha does not preserve every G-orbit on (G/H)^3.
- `claim_root_binary_twoblock_graph_failure_all_d_rev386` `informally_verified` `partial`: For every integer d>=2, let G=GL_{2d}(2), let H=GL_d(2) wr Sym(2) stabilize an unordered decomposition into two complementary d-spaces, and let alpha(g)=g^{-T}. The permutation induced by alpha on G/H moves a G-orbit on ordered triples. Consequently it lies outside the 3-closure of this faithful coset action and cannot witness non-total 3-closure.
- `claim_root_block_base3_lifting_rev190` `informally_verified` `partial`: Let A act faithfully and transitively on Omega, and let B be a nontrivial A-invariant block system. If the induced action A^B is faithful, 3-closed, and has base size at most three, then A is 3-closed on Omega.
- `claim_root_decorated_selfdual_flag_graph_nogo_rev117` `informally_verified` `partial`: Let V=F_2^n, S=GL(V), and P be the stabilizer of a self-dual two-step flag A_0<B_0 with 0<dim A_0<n/2 and dim B_0=n-dim A_0. If H<=P and a graph automorphism beta normalizes both H and P and induces flag duality on S/P, then the induced permutation of S/H is outside the 2-closure, hence outside the 3-closure, of S. The same pair obstruction excludes a componentwise graph permutation on any two-constituent action containing this constituent.
- `claim_root_gl62_c31_endpoint_obstruction_rev602` `informally_verified` `partial`: Let G=GL_6(2). Assume that every maximal subgroup M<G with 31 dividing |M| is conjugate to the stabilizer P_1 of a nonzero vector or the stabilizer P_5 of a hyperplane. Then there are no proper maximal subgroups H,K<G such that G=HK and, for L=H intersection K, both defects |L backslash G/H|-|H backslash G/H| and |L backslash G/K|-|K backslash G/K| are zero.
- `claim_root_graphcentralizer_uniform_obstruction_rev69` `informally_verified` `partial`: Let p be prime and n>=3 with gcd(n,p-1)=1. Put S=PSL_n(p)=SL_n(p), X=S semidirect <tau> with tau(g)=g^{-T}, and L=C_X(tau). Then there is an ordered triple in X/L whose pointwise stabilizer is contained in S. Consequently X is not contained in the 3-closure of S on X/L. In particular, the graph-centralizer action cannot witness non-total 3-closure for PSL_5(2) or for any member of the residual prime-field family.
- `claim_root_graphstable_geometric_nogo_rev93` `informally_verified` `partial`: Let p be prime, n>=3, gcd(n,p-1)=1, S=SL_n(p)=PSL_n(p), and X=S semidirect <tau> with tau(g)=g^{-T}. (i) If P<S is a proper parabolic with N_X(P) not contained in S, then on X/N_X(P) the relative outer base of X over S is at most three, so X is not contained in the 3-closure of S. (ii) If J is the stabilizer of a standard ordered two-block direct decomposition and H=<J,tau>, then on X/H the relative outer base is at most two, so again X is not contained in the 3-closure of S.
- `claim_root_graphstable_multiblock_imprimitive_nogo_rev99` `informally_verified` `partial`: Let p be prime, n=rd with r>=3, d>=1, gcd(n,p-1)=1, and S=PSL_n(p) nonabelian simple. Let X=S semidirect <tau>, tau(g)=g^{-T}, and let H be generated by tau and the S-stabilizer of an unordered decomposition of F_p^n into r equal d-dimensional summands. On Omega=X/H, b_rel(X,S;Omega)<=3; hence X intersect S^(3)=S. Thus this full graph-stable imprimitive action cannot witness non-3-closure via the graph extension.
- `claim_root_local_quotient_surjectivity_criterion_rev42` `informally_verified` `partial`: Let G be normal in a faithful finite permutation group X on Omega. For alpha in Omega^3 let X_alpha be the pointwise stabilizer. Then X is contained in G^(3) if and only if X_alpha G=X for every alpha, equivalently every X_alpha maps surjectively onto X/G. If moreover G<X, this faithful action proves that G is not totally 3-closed.
- `claim_root_mutual_orbital_character_scalar_test_rev150` `informally_verified` `partial`: Let G be a finite group and H,K≤G. If χ_H=Ind_H^G(1_H), then K and G have the same orbits on (G/H)^2 if and only if ⟨Res_K χ_H,Res_K χ_H⟩_K=⟨χ_H,χ_H⟩_G. Hence H,K form a mutual-orbital pair exactly when this equality and its version with H and K interchanged both hold.
- `claim_root_mutual_orbital_double_coset_defect_criterion_rev588` `informally_verified` `partial`: Let G be a finite group and let H,K<=G satisfy G=HK. Put L=H intersection K and r(A;B)=|A backslash G/B|. Then H=L(H intersection xHx^(-1)) for every x in G if and only if r(L;H)=r(H;H), and K=L(K intersection xKx^(-1)) for every x in G if and only if r(L;K)=r(K;K). Equivalently, the two mutual pair-orbital equalities hold exactly when both associated nonnegative double-coset defects vanish.
- `claim_root_piecewise_inner_twocoset_criterion_rev140` `informally_verified` `partial`: Let G be a finite nonabelian simple group and H,K<G proper. On A=G/H disjoint-union B=G/K, let pi_s act as a nonidentity s in G on A and trivially on B. Then pi_s lies in the 3-closure of diagonal G for some nonidentity s if and only if K and G have the same orbits on A^2 and H and G have the same orbits on B^2. Equivalently, G=HK and, for L=H intersection K, H=L(H intersection xHx^(-1)) and K=L(K intersection xKx^(-1)) for every x in G. If these conditions hold, every pi_s lies in the 3-closure and nonidentity pi_s lies outside diagonal G. Any such pair promotes to a pair of proper maximal overgroups with the same property.
- `claim_root_psl213_exact_maximal_subgroups_rev112` `informally_verified` `partial`: Let G = PSL_2(13). Every maximal proper subgroup of G is conjugate to B = C_13:C_6, D_12, D_14, or A_4, where D_m denotes a dihedral group of order m. These four types are maximal; there is no S_4, A_5, subfield, or additional low-parameter maximal subgroup.
- `claim_root_psl213_maximal_subgroups_6b55c08f60` `informally_verified` `partial`: Let S=PSL_2(13). Up to S-conjugacy, the maximal proper subgroups of S are exactly the point stabilizer B≅C_13⋊C_6 of order 78, the split-torus normalizer D_12 of order 12, the nonsplit-torus normalizer D_14 of order 14, and A_4 of order 12. Each listed type is maximal and constitutes one S-conjugacy class.
- `claim_root_psl213_totally_3closed_rev94` `informally_verified` `partial`: The finite simple group PSL_2(13) is totally 3-closed.
- `claim_root_psl219_local_design_reduction_rev258` `informally_verified` `partial`: Let Γ be a 57-vertex graph containing a vertex-transitive subgroup G≅PSL_2(19) with vertex stabilizer H≅A_5. If, at a vertex v, the distance-sphere incidence satisfies LS1--LS3 of art_researcher_root_psl219_local_design_reduction_rev258 and Γ[Γ_3(v)] is a dodecahedron whose antipodal pairs are the two-point fibers F_T, then Aut(Γ)=G.
- `claim_root_psl219_local_rigidity_criterion_rev134` `informally_verified` `partial`: Let G=PSL_2(19), let Omega be one degree-57 conjugacy class of A_5 subgroups, and let Gamma join K,L in Omega exactly when K intersect L is D_10. Fix v and let L_i=Gamma_i(v). Assume: (C1) Gamma has intersection array {6,5,2;1,1,3}; (C2) Gamma[L_3] is the dodecahedron; (C3) the sets F_y defined by two-step paths y-x-z with y in L_1 and z in L_3 are exactly the six unions of opposite facial 5-cycles; (C4) the thirty sets Q_x=Gamma(x) intersect L_3 for x in L_2 are distinct; and (C5) the dodecahedral antipode fails to preserve the family {Q_x:x adjacent to y} for some y in L_1. Then Aut(Gamma)=G.
- `claim_root_psl219_totally_3closed_rev138` `informally_verified` `partial`: The finite simple group PSL_2(19) is totally 3-closed: every faithful finite permutation representation of PSL_2(19) is 3-closed.
- `claim_root_psl2prime_extension_except19_rev116` `informally_verified` `partial`: PSL_2(5) is not totally 3-closed. For every prime p>=17 with p!=19, PSL_2(p) is totally 3-closed.
- `claim_root_psl33_E3_maximal_parabolic_subgroups_rev419` `informally_verified` `partial`: Let G=SL_3(3), let P be a projective point stabilizer, and let E(P)={H<P: H intersect H^g is nontrivial for every g in G}. Every maximal subgroup of P belongs to E(P). Up to P-conjugacy the maximal subgroups are precisely the geometric stabilizers of orders 48,108,144,216 (anti-flag, incident flag, partition of the four-line pencil, and nonzero vector), occurring inside P with multiplicities 9,4,3,1 respectively.
- `claim_root_psl33_exceptional_mixed_M3_incidence_sync_rev504` `informally_verified` `partial`: Let G=PSL_3(3), let T be the six G-conjugacy types in E(P) certified by art_researcher_root_psl33_E3_exact_ternary_proof_rev490, and let T* be their dual line-parabolic types. For every H,K in T union T*, with repetition allowed, the diagonal action on G/H disjoint union G/K is 3-closed.
- `claim_root_psl33_exceptional_parabolic_E3_rev496` `informally_verified` `partial`: Let G=PSL_3(3), let P be a point stabilizer, and define E(P)={H<P proper : H intersects H^g nontrivially for every g in G}. Then E(P) consists of 24 subgroups forming six G-conjugacy classes, represented by subgroups of orders 48, 54, 72, 108, 144, and 216. For every H in E(P), the faithful transitive action of G on G/H is 3-closed. The corresponding assertion holds for the six dual line-parabolic classes.
- `claim_root_psl33_exceptional_transitive_E3_rev403` `informally_verified` `partial`: Let G=PSL_3(3), let P be a point stabilizer, and let E(P)={H<P proper : H cap H^g is nontrivial for every g in G}. For every H in E(P), the transitive coset action G on G/H is 3-closed. The same conclusion holds for the dual family E(P*) inside a line stabilizer.
- `claim_root_psl33_six_geometric_actions_3closed_rev411` `informally_verified` `partial`: Let G=PSL_3(3). The transitive coset action G/H is 3-closed whenever H is one of the six point-parabolic geometric stabilizers of orders 48,54,72,108,144,216 described in art_researcher_root_psl33_E3_geometric_certificate_repair_rev411, or a contragredient-dual stabilizer.
- `claim_root_psl3_scalar_fiber_3closed_obstruction_rev313` `informally_verified` `partial`: Let p be prime with gcd(3,p-1)=1, let C be any subgroup of F_p^*, and let S=PSL_3(p)=SL_3(p). The natural faithful action of S on (F_p^3 minus {0})/C is 3-closed. Moreover, every determinant-character twist H_(e,C) of the point parabolic restricts to this same S-action, so no such scalar-fiber construction supplies a proper 3-closure witness.
- `claim_root_psl42_not_totally3closed_rev10` `informally_verified` `partial`: The finite simple group PSL_4(2) is not totally 3-closed. In its faithful degree-28 action on PSL_4(2)/Sp_4(2), the graph automorphism fixes every orbit on ordered triples but does not belong to the permutation image of PSL_4(2).
- `claim_root_psl52_graphcentralizer_exact_counterexample_rev76` `informally_verified` `partial`: Let S=PSL_5(2)=GL_5(2), let X=Aut(S)=S semidirect <tau> with tau(g)=g^{-T}, and let L=C_X(tau). There exist three distinct elements tau_1,tau_2,tau_3 in tau^S such that C_X(tau_1,tau_2,tau_3) is contained in S. Consequently the universal outer-common-centralizer condition for this L is false and the graph-centralizer subgroup choice cannot supply the proposed outer 3-closure witness.
- `claim_root_psl62_gammaL28_graph_pair_separator_rev303` `informally_verified` `partial`: Let G=GL_6(2), let M be the maximal subgroup GammaL_2(8) of type (L_2(8) x 7):3, and let tau be the permutation of G/M induced by the graph automorphism. Then tau does not preserve every G-orbit on (G/M)^2. In particular, there is an ordered triple t in (G/M)^3 such that t^tau is not G-conjugate to t, so tau is not in the 3-closure of G on G/M.
- `claim_root_psl62_gammaL34_graph_separating_triple_rev287` `informally_verified` `partial`: Let G=GL_6(2)=PSL_6(2), let C be a fixed-point-free cyclic subgroup of order three, let M=N_G(C)=GammaL_3(4), and let tau:g->g^{-T} be a graph automorphism stabilizing M. On Omega=G/M there exists an ordered triple t such that t^tau is not G-conjugate to t. Consequently the permutation induced by tau does not belong to the 3-closure of G on Omega.
- `claim_root_psl62_gammaL34_intertwiner_criterion_rev263` `informally_verified` `partial`: Let G=GL_6(2), J0=[[0,I3],[I3,I3]], P0=<J0>, M=N_G(P0)=GammaL_3(4) of type 3.L_3(4):S3, Omega=G/M, and tau(g)=g^(-T). For a triple Pi=<Ji>, its G-orbit is tau-stable iff some epsilon in {+1,-1}^3 makes A Ji^(-T)=Ji^(epsiloni) A for i=0,1,2 admit an invertible A. Consequently tau is outside G^(3,Omega) exactly when one triple has only singular solutions in all eight systems, and tau is in G^(3,Omega) exactly when every normalized triple admits an invertible solution.
- `claim_root_psl62_geometric_maximal_actions_3closed_rev190` `informally_verified` `partial`: Let G=GL_6(2) and let Omega_k be the set of k-dimensional subspaces of F_2^6. For every 1<=k<=5, the permutation group induced by G on Omega_k is 3-closed.
- `claim_root_psl62_geometric_maximal_actions_3closed_rev206` `informally_verified` `partial`: Let G=GL_6(2)=PSL_6(2), let V=F_2^6, and for 1<=k<=5 let P_k be the stabilizer of a k-dimensional subspace of V. Then the transitive action of G on G/P_k, equivalently on the k-dimensional subspaces of V, is 3-closed for every k.
- `claim_root_psl62_no_mutual_orbital_maxfactorization_rev249` `informally_verified` `partial`: Let G=GL_6(2). There do not exist proper maximal subgroups H,K<G such that G=HK, K and G have the same pair orbitals on G/H, and H and G have the same pair orbitals on G/K.
- `claim_root_psl62_no_mutual_orbital_maxpair_rev183` `informally_verified` `partial`: Let G=GL_6(2). There are no proper maximal subgroups H,K<G such that K and G have the same orbits on (G/H)^2 and H and G have the same orbits on (G/K)^2. Consequently the universal mutual-orbital factorization assertion for GL_{2d}(2), d>=3, is false at d=3.
- `claim_root_psl62_prime_order_fpr_sieve_rev564` `informally_verified` `partial`: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|. If q_X(H)<1, then X acting on X/H has a two-point base and is 3-closed. If K<=H, then q_X(K)<=q_X(H).
- `claim_root_psl62_primitive_closure_normalizer_reduction_rev217` `informally_verified` `partial`: Let G=GL_6(2), let M<G be maximal, and let C be the 3-closure of G on G/M. Then C is contained in the permutation normalizer of G, [C:G] is at most two, and C>G can occur only through the graph automorphism on a graph-stable conjugacy class of M. In that case C>G if and only if the induced graph permutation preserves every G-orbit on (G/M)^3.
- `claim_root_psl62_radicalfree31_reduction_rev168` `informally_verified` `partial`: Let V=F₂^6 and G=GL(V). If M≤G acts irreducibly on V and 31 divides |M|, then M is absolutely irreducible and primitive, C_G(M)=1, Rad(M)=1, and M is contained in no extension-field normalizer, nontrivial tensor-product stabilizer, or nondegenerate alternating-, quadratic-, or symmetric-form isometry group. Hence every counterexample to I31 is a proper maximal subgroup satisfying these restrictions.
- `claim_root_psl62_reducible31_overgroups_rev156` `informally_verified` `partial`: Let V=F_2^6 and G=GL(V). If M<G is maximal and 31 divides |M|, then either M is conjugate to the 1-space stabilizer P_1, M is conjugate to the 5-space stabilizer P_5, or M acts irreducibly on V. Consequently O31 is equivalent to the assertion that no irreducible maximal subgroup of G has order divisible by 31.
- `claim_root_psl62_sp6_graph_pair_separator_rev223` `informally_verified` `partial`: Let G=GL_6(2), let M=Sp_6(2) be the stabilizer of the standard nondegenerate alternating form J, let Omega=G/M, and let tau(g)=g^{-T}. There exists an ordered pair u in Omega^2 such that u^tau is not G-conjugate to u. Consequently tau does not belong to the 3-closure of G on Omega.
- `claim_root_psl62_symplectic_graph_pair_separator_rev351` `informally_verified` `partial`: Let G=PSL_6(2)=GL_6(2), H=Sp_6(2), and let pi be the permutation of G/H induced by the inverse-transpose graph automorphism. Then pi does not preserve all G-orbits on ordered pairs, and consequently pi is not in the 3-closure of G on G/H. Equivalently, the simultaneous-inversion assertion for all admissible relative-operator pairs is false.
- `claim_root_psl62_transitive_closure_equivalence_rev183` `informally_verified` `partial`: For G=GL_6(2)=PSL_6(2), total 3-closure is equivalent to 3-closedness of every transitive coset action G/H with H<G.
- `claim_root_psln_central_vector_exact_nonclosure_rev399` `informally_verified` `partial`: Let n>=4 and q>2, let V=F_q^n and Z=Z(SL(V)), and let G=SL(V)/Z act on Omega=(V-{0})/Z. This action is faithful. If X=GL(V)/Z in the same action, then G<X<=G^(3). Consequently PSL_n(q) is not totally 3-closed.
- `claim_root_psln_central_vector_nonclosure_corrected_rev38` `informally_verified` `partial`: Let q>2 be a prime power and n>=4, and suppose PSL_n(q) is nonabelian simple. Let V=F_q^n and Z=Z(SL_n(q)). On Omega=(V minus {0})/Z, the faithful action G=SL_n(q)/Z satisfies G < GL_n(q)/Z <= G^(3). Consequently PSL_n(q) is not totally 3-closed.
- `claim_root_psln_central_vector_nonclosure_exact_rev283` `informally_verified` `partial`: Let V=F_q^n with n>=4 and q>2, let Z=Z(SL(V)), and let G=SL(V)/Z act on Omega=(V minus {0})/Z. Then this action is faithful and GL(V)/Z is a proper overgroup of G contained in G^(3). Hence PSL_n(q) is not totally 3-closed. More generally, GL(V)/Z<=G^(k) for every k<n.
- `claim_root_unordered_twoblock_binary_nogo_rev111` `informally_verified` `partial`: Let d>=3, V=F_2^(2d), S=GL(V)=PSL_(2d)(2), X=S semidirect <tau> with tau(g)=g^(-T), and H=<N_S(D*),tau> for an unordered decomposition D* of V into two d-spaces. On Omega=X/H, the relative outer base b_rel(X,S;Omega) is at most three. Indeed, three explicit decompositions have common stabilizer in X contained in S. Consequently X intersect S^(3)=S on this action, so the unordered two-block graph-normalizer cannot supply a graph-extension witness for non-total 3-closure.

## Remaining Obligations

- blocking: Prove or refute the residual exclusion theorem R: for every prime p and n>=3 with gcd(n,p-1)=1 and (n,p)!=(3,2), PSL_n(p) is not totally 3-closed. A proof must cover every even-rank binary group PSL_n(2); a refutation must establish total 3-closure of a concrete residual group through all proper-subgroup pair actions using the certified two-orbit reduction.
- blocking: Prove that for every prime p and n>=3 with gcd(n,p-1)=1 and (n,p) not in {(3,2),(4,2)}, PSL_n(p) is not totally 3-closed. Together with the certified survivor PSL_3(2) and claim_root_psl42_not_totally3closed_rev10, this strictly narrower theorem implies the original residual exclusion theorem R.
- blocking: Prove or refute the strictly narrowed residual theorem: (i) PSL_3(3) and PSL_3(p) for every prime p>=5 with p congruent to 2 modulo 3 are not totally 3-closed; and (ii) PSL_n(2) is not totally 3-closed for every n>=5. A negative proof must give a faithful action and an explicit proper triple-orbit preserver for each family. A refutation must establish total 3-closure of a concrete residual group for every pair of proper-subgroup coset actions via the certified two-orbit reduction.
- blocking: Decide the exact finite bridge for S=PSL_5(2): with X=Aut(S), graph involution tau, and L=C_X(tau), prove that every triple tau_1,tau_2,tau_3 in tau^S has C_X(tau_1,tau_2,tau_3) intersecting X minus S, or exhibit one explicit triple whose common centralizer is contained in S. In the first outcome, the proved quotient-surjectivity lemma gives S<X<=S^(3) on X/L; in the second, abandon this subgroup choice for the binary family.
- blocking: Establish the exact X-conjugacy class list of maximal proper subgroups M<X for X=Aut(PSL_5(2)) with M not contained in S=PSL_5(2). Prove that every class is among the seven types tested in art_villain_root_psl52_outer_candidates_cas_rev56, or test each additional class. For every class, certify order, index, core-freeness, and either an explicit ordered triple whose stabilizer is contained in S or universal quotient-surjectivity. Only then may the maximal-overgroup argument rule out or validate the entire single-coset architecture.
- blocking: Prove or refute the following strictly narrowed replacement-witness theorem. For every S in {PSL_3(3)} union {PSL_3(p): p>=5 prime and p congruent to 2 mod 3} union {PSL_n(2): n>=5}, there exists a proper graph-stable subgroup J<S which is nonparabolic, is not an ordered two-block Levi stabilizer, and is not the already-failed graph-centralizer, together with H=<J,gamma><S semidirect <gamma>, such that every intersection of at most three conjugates of H contains an outer element. Equivalently b_rel(S semidirect <gamma>,S;(S semidirect <gamma>)/H)>=4. A proof must construct J uniformly, prove faithfulness, and produce the outer element for every triple. A refutation must show b_rel<=3 for every remaining outer-containing maximal subgroup class, thereby forcing a genuinely non-normalizing two-coset mechanism.
- blocking: Decide the concrete PSL_5(2) pair-action theorem after the exact failure of the natural point and repeated-point witnesses: for every pair of proper subgroups H,K<=PSL_5(2), determine the 3-closure of the diagonal action on G/H disjoint-union G/K. Either exhibit one pair and an explicit permutation outside diagonal G preserving every ordered-triple orbit, or certify all pairs have closure G.
- major: Decide the remaining graph-stable imprimitive case n=2d: for X=PSL_{2d}(p) semidirect <tau> and H the full X-stabilizer of an unordered decomposition V=A direct-sum B with dim A=dim B=d, either prove b_rel(X,PSL_{2d}(p);X/H)<=3 or prove for a specified residual parameter that every triple stabilizer contains an outer element, hence b_rel>=4.
- The root theorem still requires an exact, equivalent, or stronger verified route.

## Route Scoreboard

- `route_import_two_orbit_reduction` `verified_part` score=2.8 root_distance=1 verified=1/1
- `route_import_psl211_certificate` `verified_part` score=2.72 root_distance=1 verified=1/1
- `route_import_psl27_certificate` `verified_part` score=2.72 root_distance=1 verified=1/1
- `route_import_psln_projective_nonclosure` `verified_part` score=2.67 root_distance=1 verified=1/1
- `route_claim_root_psl62_prime_order_fpr_sieve_rev564` `verified_part` score=2.54 root_distance=1 verified=1/1
- `route_claim_root_psl52_graphcentralizer_exact_counterexample_rev76` `verified_part` score=2.37 root_distance=1 verified=1/1
- `route_claim_root_psl62_reducible31_overgroups_rev156` `verified_part` score=2.37 root_distance=1 verified=1/1
- `route_claim_root_base2_constituent_synchronization_rev369` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_claim_root_binary_antiflag_action_3closed_rev474` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_claim_root_binary_twoblock_commutator_rank_separator_rev576` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_claim_root_binary_twoblock_contragredient_failure_d2_rev486` `verified_part` score=2.32 root_distance=1 verified=1/1
- `route_claim_root_block_base3_lifting_rev190` `verified_part` score=2.32 root_distance=1 verified=1/1

## Branches

- Parallel branch mode: `multi_branch_research` with up to 3 simultaneous branch workers

```text
Branch: route_import_two_orbit_reduction
Goal: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
Status: keep_exploiting
Verified facts: claim_import_two_orbit_reduction: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgro...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_freedman_giudici_praeger_psl_primitive_base_closure: Freedman–Giudici–Praeger prove: (Corollary 3.3) if G is a finite nonabelian simple group and b_maxprim(G) is the maximum base size among its faithful primitive permutation repre...; card_praeger_saxl_primitive_kclosure_theorem2_psl62_rev301: Let X be a finite primitive permutation group on a set Omega of n points, let k be an integer with k at least 2, and suppose X<Y<=X^(k) while soc(X) and soc(Y) are different. Th...; card_psl62_praeger_saxl_theorem2_exact_rev277: Let G be a primitive permutation group on a finite set Ω of n points, let k≥2, and suppose G<H≤G^(k) while soc(G) and soc(H) are different. Then one of the following holds: (a)...
Next recommended lemma: extend the verified chain toward the branch goal: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
Similar lemmas worth trying: prove a special case of the branch goal first: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.; prove a bridge lemma connecting the verified branch facts to: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card card_psl62_atlas_bhrd_complete_maximal_classes_rev323 matches the branch goal (at 2026-07-16T20:55:37.833809+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card card_psl62_atlas_bhrd_complete_maximal_classes_rev323 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_import_psl211_certificate
Goal: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.
Status: keep_exploiting
Verified facts: claim_import_psl211_totally_3closed: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_freedman_giudici_praeger_psl_primitive_base_closure: Freedman–Giudici–Praeger prove: (Corollary 3.3) if G is a finite nonabelian simple group and b_maxprim(G) is the maximum base size among its faithful primitive permutation repre...; retrieval_praegersaxl_closures_theorem2_rev235: Let X be a primitive permutation group on a finite set Lambda, let r>=2, and suppose X<Y<=X^(r), where X^(r) is the r-closure. If Soc(X) and Soc(Y) are different, then one of fo...; card_praeger_saxl_primitive_kclosure_theorem2_psl62_rev301: Let X be a finite primitive permutation group on a set Omega of n points, let k be an integer with k at least 2, and suppose X<Y<=X^(k) while soc(X) and soc(Y) are different. Th...
Next recommended lemma: extend the verified chain toward the branch goal: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.
Similar lemmas worth trying: prove a special case of the branch goal first: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.; prove a bridge lemma connecting the verified branch facts to: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card card_psl62_atlas_bhrd_complete_maximal_classes_rev323 matches the branch goal (at 2026-07-16T20:55:37.833809+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card card_psl62_atlas_bhrd_complete_maximal_classes_rev323 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_import_psl27_certificate
Goal: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Status: keep_exploiting
Verified facts: claim_import_psl27_totally_3closed: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_freedman_giudici_praeger_psl_primitive_base_closure: Freedman–Giudici–Praeger prove: (Corollary 3.3) if G is a finite nonabelian simple group and b_maxprim(G) is the maximum base size among its faithful primitive permutation repre...; retrieval_praegersaxl_closures_theorem2_rev235: Let X be a primitive permutation group on a finite set Lambda, let r>=2, and suppose X<Y<=X^(r), where X^(r) is the r-closure. If Soc(X) and Soc(Y) are different, then one of fo...; card_praeger_saxl_primitive_kclosure_theorem2_psl62_rev301: Let X be a finite primitive permutation group on a set Omega of n points, let k be an integer with k at least 2, and suppose X<Y<=X^(k) while soc(X) and soc(Y) are different. Th...
Next recommended lemma: extend the verified chain toward the branch goal: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Similar lemmas worth trying: prove a special case of the branch goal first: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.; prove a bridge lemma connecting the verified branch facts to: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card card_psl62_atlas_bhrd_complete_maximal_classes_rev323 matches the branch goal (at 2026-07-16T20:55:37.833809+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card card_psl62_atlas_bhrd_complete_maximal_classes_rev323 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_import_psln_projective_nonclosure
Goal: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
Status: keep_exploiting
Verified facts: claim_import_psln_projective_nonclosure: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or...
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_lit_psl62_bhrd_main_theorem_tables824_825_rev295: Bray–Holt–Roney-Dougal, Main Theorem 2.1.1, states that for prime-power q and n at most 12, if Omega is one of the specified quasisimple classical groups and G is an almost simp...; card_atlas_l62_complete_maximal_subgroups_rev341: For L_6(2), of order 20158709760 = 2^15*3^4*5*7^2*31, the complete list of maximal-subgroup conjugacy classes is: (1) 2^5:L_5(2), point stabilizer, order 319979520, index 63; (2...; card_literature_psl62_complete_maximal_classes_rev275: For L_6(2), the complete maximal-subgroup conjugacy-class list consists of nine classes with structures and indices: 2^5:L_5(2) (point stabilizer), 63; 2^5:L_5(2) (projective 4-...
Next recommended lemma: extend the verified chain toward the branch goal: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
Similar lemmas worth trying: prove a special case of the branch goal first: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.; prove a bridge lemma connecting the verified branch facts to: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
Failed methods (do not retry unchanged): none recorded
Last useful delta: usable_source: retrieval card card_atlas_l62_complete_maximal_subgroups_rev341 matches the branch goal (at 2026-07-16T21:35:47.785938+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (usable_source: retrieval card card_atlas_l62_complete_maximal_subgroups_rev341 matches the branch goal)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

```text
Branch: route_claim_root_psl62_prime_order_fpr_sieve_rev564
Goal: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|. If q_X(H)<1, then X acting on X/H has a two-point base and is 3-closed. If K<=H,...
Status: keep_exploiting
Verified facts: claim_root_psl62_prime_order_fpr_sieve_rev564: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|....
Candidate facts: none recorded
Active blockers: none recorded
Failed methods: none recorded
Useful sources: card_atlas_l62_complete_maximal_subgroups_rev341: For L_6(2), of order 20158709760 = 2^15*3^4*5*7^2*31, the complete list of maximal-subgroup conjugacy classes is: (1) 2^5:L_5(2), point stabilizer, order 319979520, index 63; (2...; card_lit_psl62_bhrd_main_theorem_tables824_825_rev295: Bray–Holt–Roney-Dougal, Main Theorem 2.1.1, states that for prime-power q and n at most 12, if Omega is one of the specified quasisimple classical groups and G is an almost simp...; card_psl62_atlas_bhrd_complete_maximal_classes_rev323: For L_6(2), the complete maximal-subgroup list consists of nine conjugacy classes: 2^5:L_5(2), point stabilizer, order 319979520 and index 63; 2^5:L_5(2), projective 4-space sta...
Next recommended lemma: extend the verified chain toward the branch goal: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|. If q_X(H)<1, then X acting on X/H has a two-point base and is 3-closed. If K<=H,...
Similar lemmas worth trying: prove a special case of the branch goal first: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|. If q_X(H)<1, then X acting on X/H has a two-point base and is 3-closed. If K<=H,...; prove a bridge lemma connecting the verified branch facts to: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|. If q_X(H)<1, then X acting on X/H has a two-point base and is 3-closed. If K<=H,...
Failed methods (do not retry unchanged): none recorded
Last useful delta: verified_claim: claim claim_root_psl62_prime_order_fpr_sieve_rev564 verified (at 2026-07-17T07:52:02.964443+00:00)
Passes since useful delta: 0
Rotation: continue (productive) — recent branch passes produced a useful delta (verified_claim: claim claim_root_psl62_prime_order_fpr_sieve_rev564 verified)
Advisor state: none
Stop/merge/rotate condition: rotate/pause this branch when the same failure fingerprint repeats 2+ times, when 3 branch passes produce no useful delta, or when the advisor adjudicates it pause_or_merge
```

## Research Strategy

Strategic artifacts are persisted proof-state context, not verified mathematical evidence.

- Latest global advisor synthesis: `none`
- Latest active proof compression: `art_researcher_root_canonical_compression_grassmann_obstruction_rev7`
- Bridge search: `art_researcher_root_psl62_parabolic_closure_bridge_rev598`; candidates=1, selected=`bridge_root_psl62_maximal_or_base_two_dichotomy_rev598`
- Conjecture portfolio: `none`; candidates=0, selected=`none`
- Active invention authorization: `none`
- Global synthesis due: `False`; reasons=[]
- Graph-derived decisive obligation: `debt_root_evenbinary_mutual_orbital_factorization_rev140`; selected route=`none`, ready_for_verification=False
- Verifier-filtered outcome learning: family=`research`; local families=0; reference_solution_used=False
- Deep-session ROI: allowed=True; reason=deep-session ROI gate is open
- Information-gain policy: scheduler exposes closing, refuting, root-progress, information, reuse, duplication, token, wall-time, verification-cost, and verifier-filtered outcome components; speculative work never consumes the protected verification reserve.
- Method library policy: 18 developer-curated structural/domain method cards are advisory only and are kept separate from verified facts, external theorem cards, and private speculation.

## Fact Graph

Read-only graph view generated from claims, routes, inferences, debts, and sources.

- Nodes: verified_fact=106, candidate_fact=2, obstruction=57, source_fact=11, branch_cluster=55
- Edges: uses=10, depends_on=10, blocks=34, repairs=10, same_as=0, supersedes=2
- Edge types awaiting a data source (not derived): contradicts, generalizes, specializes
- Branch depth report:
  - `route_import_psl211_certificate` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_import_psl27_certificate` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_import_psln_projective_nonclosure` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_import_two_orbit_reduction` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_root_psl213_exact_maximal_subgroups_rev112` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_psl213_maximal_subgroups_6b55c08f60` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_psl213_total3closed_rev94` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_psl219_local_design_reduction_rev258` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_psl219_local_rigidity_criterion_rev134` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_psl219_total3closed_rev138` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_root_psl2prime_extension_except19_rev116` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_root_psl42_graphfixed_nonclosure_rev10` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_psln_central_vector_nonclosure_rev18` shallow (depth=0, verified=0, candidate=1, active_obstructions=0)
  - `route_root_psln_central_vector_nonclosure_corrected_rev38` shallow (depth=0, verified=1, candidate=0, active_obstructions=0)
  - `route_root_local_quotient_surjectivity_criterion_rev42` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_root_graphcentralizer_uniform_obstruction_rev69` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl52_graphcentralizer_exact_counterexample_rev76` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_graphstable_geometric_nogo_rev93` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_root_graphstable_multiblock_imprimitive_nogo_rev99` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_unordered_twoblock_binary_nogo_rev111` converging (depth=1, verified=3, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_decorated_selfdual_flag_graph_nogo_rev117` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_piecewise_inner_twocoset_criterion_rev140` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_mutual_orbital_character_scalar_test_rev150` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl62_reducible31_overgroups_rev156` converging (depth=0, verified=2, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl62_radicalfree31_reduction_rev168` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_no_mutual_orbital_maxpair_rev183` converging (depth=1, verified=4, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_psl62_transitive_closure_equivalence_rev183` converging (depth=1, verified=5, candidate=0, active_obstructions=0, converging)
  - `route_claim_root_block_base3_lifting_rev190` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_geometric_maximal_actions_3closed_rev190` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_geometric_maximal_actions_3closed_rev206` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_primitive_closure_normalizer_reduction_rev217` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_sp6_graph_pair_separator_rev223` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_no_mutual_orbital_maxfactorization_rev249` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_gammaL34_intertwiner_criterion_rev263` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psln_central_vector_nonclosure_exact_rev283` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_gammaL34_graph_separating_triple_rev287` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_gammaL28_graph_pair_separator_rev303` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl3_scalar_fiber_3closed_obstruction_rev313` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_symplectic_graph_pair_separator_rev351` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_base2_constituent_synchronization_rev369` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_binary_c2_orthogonal_graph_pair_obstructions_rev373` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_binary_twoblock_graph_failure_all_d_rev386` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psln_central_vector_exact_nonclosure_rev399` shallow (depth=0, verified=1, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_exceptional_transitive_E3_rev403` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_six_geometric_actions_3closed_rev411` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_E3_maximal_parabolic_subgroups_rev419` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_root_binary_twoblock_contragredient_failure_dge3_rev461` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_binary_antiflag_action_3closed_rev474` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_binary_twoblock_contragredient_failure_d2_rev486` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_exceptional_parabolic_E3_rev496` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl33_exceptional_mixed_M3_incidence_sync_rev504` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_psl62_prime_order_fpr_sieve_rev564` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_binary_twoblock_commutator_rank_separator_rev576` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_mutual_orbital_double_coset_defect_criterion_rev588` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)
  - `route_claim_root_gl62_c31_endpoint_obstruction_rev602` shallow (depth=0, verified=2, candidate=0, active_obstructions=0)

## Retrieval Cards

- `card_freedman_giudici_praeger_psl_primitive_base_closure` `method_match` confidence=0.99: Freedman–Giudici–Praeger prove: (Corollary 3.3) if G is a finite nonabelian simple group and b_maxprim(G) is the maximum base size among its faithful primitive permutation representations, then k(G) <= b_maxprim(G)+1. They also prove: (Corollary 4.4(i)) if G=PSL(n,q) is finite simple and is not isomorphic to an alternating group, then b_maxprim(G)=n+1-delta_{2,q}, where delta_{2,q}=1 for q=2 and is 0 otherwise. Consequently, Theorem 1.2(c) and Table 1 give k(PSL(n,q)) <= n+2-delta_{2,q}.
- `card_lang_steinberg_h1_graph_field_2209_00085v2_thm4_4_5` `conditional_match` confidence=0.99: If G is a connected algebraic group and σ∈End(G) has finitely many fixed points, then the Lang map Lσ is surjective.
- `retrieval_praegersaxl_closures_theorem2_rev235` `partial_match` confidence=0.99: Let X be a primitive permutation group on a finite set Lambda, let r>=2, and suppose X<Y<=X^(r), where X^(r) is the r-closure. If Soc(X) and Soc(Y) are different, then one of four alternatives holds: (a) X is r-transitive and 2<=r<=5; (b) r=3, |Lambda|=15, and the degree-15 inclusion is A_7<Y=X^(3)=A_8; (c) r=2 and X and Y are almost simple; or (d) Y preserves a Cartesian product decomposition Lambda=Delta^m with m>=2, and the component groups X_0<Y_0<=X_0^(r)<=Sym(Delta) have different socles and form an instance of (a), (b), or (c).
- `retrieval_bhrd_atlas_l62_maximal_classes_rev253` `partial_match` confidence=0.99: Let L=L_6(2). Up to L-conjugacy, the maximal subgroups of L are exactly the following nine classes: (1) 2^5:L_5(2), the point stabilizer, order 319979520 and index 63; (2) 2^5:L_5(2), the projective 4-space (vector 5-space) stabilizer, order 319979520 and index 63; (3) 2^8:(A_8 x S_3), the line stabilizer, order 30965760 and index 651; (4) 2^8:(A_8 x S_3), the projective 3-space (vector 4-space) stabilizer, order 30965760 and index 651; (5) 2^9:(L_3(2) x L_3(2)), the plane stabilizer, order 14450688 and index 1395; (6) Sp_6(2), order 1451520 and index 13888; (7) 3.L_3(4):S_3, order 362880 and index 55552; (8) (L_3(2) x L_3(2)):2, order 56448 and index 357120; and (9) (L_2(8) x 7):3, order 10584 and index 1904640. The first two classes are respectively the endpoint parabolics P_1 and P_5. Bray–Holt–Roney-Dougal Tables 8.24 and 8.25 jointly supply the complete geometric and non-geometric classification; the ATLAS L_6(2) maximal-subgroups section gives this exact q=2 specialization.
- `retrieval_psl62_praeger_saxl_theorem2_exact_rev255` `conditional_match` confidence=0.99: Praeger–Saxl Theorem 2, in normalized notation: let X be primitive on a finite set Omega of degree n, let k>=2, and suppose X<Y<=X^(k) with soc(X) different from soc(Y). Then one of the following holds: (a) X is k-transitive and 2<=k<=5; (b) k=3, n=15, and X=A_7<Y=X^(3)=A_8 in the degree-15 action; (c) k=2 and X,Y are almost simple; or (d) Y preserves a product decomposition Omega=Delta^m for some m>=2, and the coordinate groups X_0,Y_0 induced by X,Y on Delta have different socles and satisfy X_0<Y_0<=X_0^(k)<=Sym(Delta), with the coordinate inclusion belonging to cases (a)-(c).
- `card_literature_psl62_complete_maximal_classes_rev275` `partial_match` confidence=0.99: For L_6(2), the complete maximal-subgroup conjugacy-class list consists of nine classes with structures and indices: 2^5:L_5(2) (point stabilizer), 63; 2^5:L_5(2) (projective 4-space stabilizer), 63; 2^8:(A_8 x S_3) (line stabilizer), 651; 2^8:(A_8 x S_3) (projective 3-space stabilizer), 651; 2^9:(L_3(2) x L_3(2)) (plane stabilizer), 1395; Sp_6(2), 13888; 3.L_3(4):S_3, 55552; (L_3(2) x L_3(2)):2, 357120; and (L_2(8) x 7):3, 1904640. Their respective orders are 319979520, 319979520, 30965760, 30965760, 14450688, 1451520, 362880, 56448, and 10584.
- `card_psl62_praeger_saxl_theorem2_exact_rev277` `partial_match` confidence=0.99: Let G be a primitive permutation group on a finite set Ω of n points, let k≥2, and suppose G<H≤G^(k) while soc(G) and soc(H) are different. Then one of the following holds: (a) G is k-transitive on Ω, with 2≤k≤5; (b) k=3, n=15, and G=A_7<H=G^(3)=A_8 in the degree-15 action; (c) k=2 and G and H are almost simple; or (d) H preserves a product decomposition Ω=Δ^m for some m≥2, and the groups G_0 and H_0 induced on Δ by G and H respectively have different socles and satisfy G_0<H_0≤G_0^(k)≤Sym(Δ), with the induced pair belonging to one of cases (a)–(c).
- `card_lit_psl62_bhrd_main_theorem_tables824_825_rev295` `conditional_match` confidence=0.99: Bray–Holt–Roney-Dougal, Main Theorem 2.1.1, states that for prime-power q and n at most 12, if Omega is one of the specified quasisimple classical groups and G is an almost simple extension of Omega/Z(Omega), then the appropriate Chapter 8 table supplies representatives of every G-conjugacy class of maximal subgroups not containing the socle. Specializing Tables 8.24 and 8.25 to q=2 and n=6 gives exactly nine SL_6(2)-classes: two 2^5:L_5(2) parabolics, two 2^8:(A_8 x S_3) parabolics, one 2^9:(L_3(2) x L_3(2)) parabolic, Sp_6(2), 3.L_3(4):S_3, (L_3(2) x L_3(2)):2, and (L_2(8) x 7):3. The ATLAS L_6(2) maximal-subgroups section identifies their respective indices as 63, 63, 651, 651, 1395, 13888, 55552, 357120, and 1904640, and identifies the two index-63 classes as the point and projective 4-space stabilizers, hence P_1 and P_5.
- `card_praeger_saxl_primitive_kclosure_theorem2_psl62_rev301` `conditional_match` confidence=0.99: Let X be a finite primitive permutation group on a set Omega of n points, let k be an integer with k at least 2, and suppose X<Y<=X^(k) while soc(X) and soc(Y) are different. Then one of the following holds: (a) X is k-transitive and 2<=k<=5; (b) k=3, n=15, and X=A_7<Y=X^(3)=A_8 in the degree-15 action; (c) k=2 and X and Y are almost simple; or (d) for some finite set Delta and m>=2, Y preserves a product decomposition Omega=Delta^m, and the groups X_0 and Y_0 induced by X and Y on one coordinate have different socles and satisfy X_0<Y_0<=X_0^(k)<=Sym(Delta), with the induced pair belonging to cases (a)–(c).
- `card_psl62_atlas_bhrd_complete_maximal_classes_rev323` `partial_match` confidence=0.99: For L_6(2), the complete maximal-subgroup list consists of nine conjugacy classes: 2^5:L_5(2), point stabilizer, order 319979520 and index 63; 2^5:L_5(2), projective 4-space stabilizer, order 319979520 and index 63; 2^8:(A_8 x S_3), line stabilizer, order 30965760 and index 651; 2^8:(A_8 x S_3), projective 3-space stabilizer, order 30965760 and index 651; 2^9:(L_3(2) x L_3(2)), plane stabilizer, order 14450688 and index 1395; S_6(2), order 1451520 and index 13888; 3.L_3(4):S_3, order 362880 and index 55552; (L_3(2) x L_3(2)):2, order 56448 and index 357120; and (L_2(8) x 7):3, order 10584 and index 1904640. The group order is 20158709760 = 2^15*3^4*5*7^2*31.
- `card_atlas_l62_complete_maximal_subgroups_rev341` `partial_match` confidence=0.99: For L_6(2), of order 20158709760 = 2^15*3^4*5*7^2*31, the complete list of maximal-subgroup conjugacy classes is: (1) 2^5:L_5(2), point stabilizer, order 319979520, index 63; (2) 2^5:L_5(2), 4-space stabilizer, order 319979520, index 63; (3) 2^8:(A_8 x S_3), line stabilizer, order 30965760, index 651; (4) 2^8:(A_8 x S_3), 3-space stabilizer, order 30965760, index 651; (5) 2^9:(L_3(2) x L_3(2)), plane stabilizer, order 14450688, index 1395; (6) S_6(2), order 1451520, index 13888; (7) 3.L_3(4):S_3, order 362880, index 55552; (8) (L_3(2) x L_3(2)):2, order 56448, index 357120; and (9) (L_2(8) x 7):3, order 10584, index 1904640. The first two rows are distinct classes: the point and projective-4-space (vector-hyperplane) stabilizers.

## Claims

- `claim_root_base2_constituent_synchronization_rev369` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G act faithfully on two transitive sets Omega_1 and Omega_2. Assume both constituent actions are 3-closed and the action on Omega_1 has a base of size at most two. Then the diagonal action of G on the disjoint union Omega_1 disjoint union Omega_2 is 3-closed.
- `claim_root_binary_antiflag_action_3closed_rev474` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every integer n>=3, let V=F_2^n and G=GL(V). On the set Omega of rank-one idempotents E=v tensor lambda with v nonzero and lambda(v)=1, equivalently on anti-flags (v,ker(lambda)) with v not in ker(lambda), the faithful conjugation action of G is 3-closed.
- `claim_root_binary_c2_orthogonal_graph_pair_obstructions_rev373` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_n(2) and α(g)=g^{-T}. If n=dm with m>=3 and H=GL_d(2) wr Sym(m) is the stabilizer of an unordered decomposition into m equal summands, then α moves an H-double coset. The same conclusion holds for every n>=3 when H=O(I_n,2). Consequently the graph-induced permutation on G/H is outside the 2-closure and the 3-closure in both families, so neither family can witness Binary Lemma B.
- `claim_root_binary_twoblock_commutator_rank_separator_rev576` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every d >= 2, let G=GL_(2d)(2), let H=GL_d(2) wr Sym(2) stabilize an unordered decomposition into complementary d-spaces, and let alpha(g)=g^(-T). There are explicit x_d,y_d in G, given by the block matrices in art_researcher_root_binary_twoblock_commutator_rank_separator_rev576, such that no h in H satisfies alpha(x_d)H=hx_dH and alpha(y_d)H=hy_dH simultaneously. The proof uses the independently complement-invariant quantity rho(P,Q,R)=rank([P,Q][Q,R][R,P]), for which the explicit triple has rho(P,Q,R)=1 and rho(P^T,Q^T,R^T)=0. Consequently alpha is not in the 3-closure of the equal two-block decomposition action for any d >= 2.
- `claim_root_binary_twoblock_contragredient_failure_d2_rev486` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_4(2), let H=GL_2(2) wr Sym(2) stabilize an unordered decomposition of F_2^4 into complementary 2-spaces, and let α(g)=g^{-T}. There exist x,y in G such that no h in H simultaneously satisfies α(x)H=hxH and α(y)H=hyH. Equivalently, α is not in the 3-closure of the faithful degree-280 action of G on G/H.
- `claim_root_binary_twoblock_contragredient_failure_dge3_rev461` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every d>=3, with G=GL_{2d}(2), H=GL_d(2) wr Sym(2), and alpha(g)=g^{-T}, there exist explicit x_d,y_d in G such that no h in H simultaneously satisfies alpha(x_d)H=hx_dH and alpha(y_d)H=hy_dH. Hence alpha does not preserve every G-orbit on (G/H)^3.
- `claim_root_binary_twoblock_graph_failure_all_d_rev386` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For every integer d>=2, let G=GL_{2d}(2), let H=GL_d(2) wr Sym(2) stabilize an unordered decomposition into two complementary d-spaces, and let alpha(g)=g^{-T}. The permutation induced by alpha on G/H moves a G-orbit on ordered triples. Consequently it lies outside the 3-closure of this faithful coset action and cannot witness non-total 3-closure.
- `claim_root_block_base3_lifting_rev190` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let A act faithfully and transitively on Omega, and let B be a nontrivial A-invariant block system. If the induced action A^B is faithful, 3-closed, and has base size at most three, then A is 3-closed on Omega.
- `claim_root_decorated_selfdual_flag_graph_nogo_rev117` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let V=F_2^n, S=GL(V), and P be the stabilizer of a self-dual two-step flag A_0<B_0 with 0<dim A_0<n/2 and dim B_0=n-dim A_0. If H<=P and a graph automorphism beta normalizes both H and P and induces flag duality on S/P, then the induced permutation of S/H is outside the 2-closure, hence outside the 3-closure, of S. The same pair obstruction excludes a componentwise graph permutation on any two-constituent action containing this constituent.
- `claim_root_gl62_c31_endpoint_obstruction_rev602` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2). Assume that every maximal subgroup M<G with 31 dividing |M| is conjugate to the stabilizer P_1 of a nonzero vector or the stabilizer P_5 of a hyperplane. Then there are no proper maximal subgroups H,K<G such that G=HK and, for L=H intersection K, both defects |L backslash G/H|-|H backslash G/H| and |L backslash G/K|-|K backslash G/K| are zero.
- `claim_root_graphcentralizer_uniform_obstruction_rev69` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime and n>=3 with gcd(n,p-1)=1. Put S=PSL_n(p)=SL_n(p), X=S semidirect <tau> with tau(g)=g^{-T}, and L=C_X(tau). Then there is an ordered triple in X/L whose pointwise stabilizer is contained in S. Consequently X is not contained in the 3-closure of S on X/L. In particular, the graph-centralizer action cannot witness non-total 3-closure for PSL_5(2) or for any member of the residual prime-field family.
- `claim_root_graphstable_geometric_nogo_rev93` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime, n>=3, gcd(n,p-1)=1, S=SL_n(p)=PSL_n(p), and X=S semidirect <tau> with tau(g)=g^{-T}. (i) If P<S is a proper parabolic with N_X(P) not contained in S, then on X/N_X(P) the relative outer base of X over S is at most three, so X is not contained in the 3-closure of S. (ii) If J is the stabilizer of a standard ordered two-block direct decomposition and H=<J,tau>, then on X/H the relative outer base is at most two, so again X is not contained in the 3-closure of S.
- `claim_root_graphstable_multiblock_imprimitive_nogo_rev99` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime, n=rd with r>=3, d>=1, gcd(n,p-1)=1, and S=PSL_n(p) nonabelian simple. Let X=S semidirect <tau>, tau(g)=g^{-T}, and let H be generated by tau and the S-stabilizer of an unordered decomposition of F_p^n into r equal d-dimensional summands. On Omega=X/H, b_rel(X,S;Omega)<=3; hence X intersect S^(3)=S. Thus this full graph-stable imprimitive action cannot witness non-3-closure via the graph extension.
- `claim_root_local_quotient_surjectivity_criterion_rev42` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be normal in a faithful finite permutation group X on Omega. For alpha in Omega^3 let X_alpha be the pointwise stabilizer. Then X is contained in G^(3) if and only if X_alpha G=X for every alpha, equivalently every X_alpha maps surjectively onto X/G. If moreover G<X, this faithful action proves that G is not totally 3-closed.
- `claim_root_mutual_orbital_character_scalar_test_rev150` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite group and H,K≤G. If χ_H=Ind_H^G(1_H), then K and G have the same orbits on (G/H)^2 if and only if ⟨Res_K χ_H,Res_K χ_H⟩_K=⟨χ_H,χ_H⟩_G. Hence H,K form a mutual-orbital pair exactly when this equality and its version with H and K interchanged both hold.
- `claim_root_mutual_orbital_double_coset_defect_criterion_rev588` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite group and let H,K<=G satisfy G=HK. Put L=H intersection K and r(A;B)=|A backslash G/B|. Then H=L(H intersection xHx^(-1)) for every x in G if and only if r(L;H)=r(H;H), and K=L(K intersection xKx^(-1)) for every x in G if and only if r(L;K)=r(K;K). Equivalently, the two mutual pair-orbital equalities hold exactly when both associated nonnegative double-coset defects vanish.
- `claim_root_piecewise_inner_twocoset_criterion_rev140` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G be a finite nonabelian simple group and H,K<G proper. On A=G/H disjoint-union B=G/K, let pi_s act as a nonidentity s in G on A and trivially on B. Then pi_s lies in the 3-closure of diagonal G for some nonidentity s if and only if K and G have the same orbits on A^2 and H and G have the same orbits on B^2. Equivalently, G=HK and, for L=H intersection K, H=L(H intersection xHx^(-1)) and K=L(K intersection xKx^(-1)) for every x in G. If these conditions hold, every pi_s lies in the 3-closure and nonidentity pi_s lies outside diagonal G. Any such pair promotes to a pair of proper maximal overgroups with the same property.
- `claim_root_psl213_exact_maximal_subgroups_rev112` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G = PSL_2(13). Every maximal proper subgroup of G is conjugate to B = C_13:C_6, D_12, D_14, or A_4, where D_m denotes a dihedral group of order m. These four types are maximal; there is no S_4, A_5, subfield, or additional low-parameter maximal subgroup.
- `claim_root_psl213_maximal_subgroups_6b55c08f60` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let S=PSL_2(13). Up to S-conjugacy, the maximal proper subgroups of S are exactly the point stabilizer B≅C_13⋊C_6 of order 78, the split-torus normalizer D_12 of order 12, the nonsplit-torus normalizer D_14 of order 14, and A_4 of order 12. Each listed type is maximal and constitutes one S-conjugacy class.
- `claim_root_psl213_totally_3closed_rev94` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: The finite simple group PSL_2(13) is totally 3-closed.
- `claim_root_psl219_local_design_reduction_rev258` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let Γ be a 57-vertex graph containing a vertex-transitive subgroup G≅PSL_2(19) with vertex stabilizer H≅A_5. If, at a vertex v, the distance-sphere incidence satisfies LS1--LS3 of art_researcher_root_psl219_local_design_reduction_rev258 and Γ[Γ_3(v)] is a dodecahedron whose antipodal pairs are the two-point fibers F_T, then Aut(Γ)=G.
- `claim_root_psl219_local_rigidity_criterion_rev134` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_2(19), let Omega be one degree-57 conjugacy class of A_5 subgroups, and let Gamma join K,L in Omega exactly when K intersect L is D_10. Fix v and let L_i=Gamma_i(v). Assume: (C1) Gamma has intersection array {6,5,2;1,1,3}; (C2) Gamma[L_3] is the dodecahedron; (C3) the sets F_y defined by two-step paths y-x-z with y in L_1 and z in L_3 are exactly the six unions of opposite facial 5-cycles; (C4) the thirty sets Q_x=Gamma(x) intersect L_3 for x in L_2 are distinct; and (C5) the dodecahedral antipode fails to preserve the family {Q_x:x adjacent to y} for some y in L_1. Then Aut(Gamma)=G.
- `claim_root_psl219_totally_3closed_rev138` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: The finite simple group PSL_2(19) is totally 3-closed: every faithful finite permutation representation of PSL_2(19) is 3-closed.
- `claim_root_psl2prime_extension_except19_rev116` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: PSL_2(5) is not totally 3-closed. For every prime p>=17 with p!=19, PSL_2(p) is totally 3-closed.
- `claim_root_psl33_E3_maximal_parabolic_subgroups_rev419` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=SL_3(3), let P be a projective point stabilizer, and let E(P)={H<P: H intersect H^g is nontrivial for every g in G}. Every maximal subgroup of P belongs to E(P). Up to P-conjugacy the maximal subgroups are precisely the geometric stabilizers of orders 48,108,144,216 (anti-flag, incident flag, partition of the four-line pencil, and nonzero vector), occurring inside P with multiplicities 9,4,3,1 respectively.
- `claim_root_psl33_exceptional_mixed_M3_incidence_sync_rev504` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3), let T be the six G-conjugacy types in E(P) certified by art_researcher_root_psl33_E3_exact_ternary_proof_rev490, and let T* be their dual line-parabolic types. For every H,K in T union T*, with repetition allowed, the diagonal action on G/H disjoint union G/K is 3-closed.
- `claim_root_psl33_exceptional_parabolic_E3_rev496` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3), let P be a point stabilizer, and define E(P)={H<P proper : H intersects H^g nontrivially for every g in G}. Then E(P) consists of 24 subgroups forming six G-conjugacy classes, represented by subgroups of orders 48, 54, 72, 108, 144, and 216. For every H in E(P), the faithful transitive action of G on G/H is 3-closed. The corresponding assertion holds for the six dual line-parabolic classes.
- `claim_root_psl33_exceptional_transitive_E3_rev403` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3), let P be a point stabilizer, and let E(P)={H<P proper : H cap H^g is nontrivial for every g in G}. For every H in E(P), the transitive coset action G on G/H is 3-closed. The same conclusion holds for the dual family E(P*) inside a line stabilizer.
- `claim_root_psl33_six_geometric_actions_3closed_rev411` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_3(3). The transitive coset action G/H is 3-closed whenever H is one of the six point-parabolic geometric stabilizers of orders 48,54,72,108,144,216 described in art_researcher_root_psl33_E3_geometric_certificate_repair_rev411, or a contragredient-dual stabilizer.
- `claim_root_psl3_scalar_fiber_3closed_obstruction_rev313` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let p be prime with gcd(3,p-1)=1, let C be any subgroup of F_p^*, and let S=PSL_3(p)=SL_3(p). The natural faithful action of S on (F_p^3 minus {0})/C is 3-closed. Moreover, every determinant-character twist H_(e,C) of the point parabolic restricts to this same S-action, so no such scalar-fiber construction supplies a proper 3-closure witness.
- `claim_root_psl42_not_totally3closed_rev10` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: The finite simple group PSL_4(2) is not totally 3-closed. In its faithful degree-28 action on PSL_4(2)/Sp_4(2), the graph automorphism fixes every orbit on ordered triples but does not belong to the permutation image of PSL_4(2).
- `claim_root_psl62_gammaL28_graph_pair_separator_rev303` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2), let M be the maximal subgroup GammaL_2(8) of type (L_2(8) x 7):3, and let tau be the permutation of G/M induced by the graph automorphism. Then tau does not preserve every G-orbit on (G/M)^2. In particular, there is an ordered triple t in (G/M)^3 such that t^tau is not G-conjugate to t, so tau is not in the 3-closure of G on G/M.
- `claim_root_psl62_gammaL34_graph_separating_triple_rev287` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2)=PSL_6(2), let C be a fixed-point-free cyclic subgroup of order three, let M=N_G(C)=GammaL_3(4), and let tau:g->g^{-T} be a graph automorphism stabilizing M. On Omega=G/M there exists an ordered triple t such that t^tau is not G-conjugate to t. Consequently the permutation induced by tau does not belong to the 3-closure of G on Omega.
- `claim_root_psl62_gammaL34_intertwiner_criterion_rev263` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2), J0=[[0,I3],[I3,I3]], P0=<J0>, M=N_G(P0)=GammaL_3(4) of type 3.L_3(4):S3, Omega=G/M, and tau(g)=g^(-T). For a triple Pi=<Ji>, its G-orbit is tau-stable iff some epsilon in {+1,-1}^3 makes A Ji^(-T)=Ji^(epsiloni) A for i=0,1,2 admit an invertible A. Consequently tau is outside G^(3,Omega) exactly when one triple has only singular solutions in all eight systems, and tau is in G^(3,Omega) exactly when every normalized triple admits an invertible solution.
- `claim_root_psl62_geometric_maximal_actions_3closed_rev190` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2) and let Omega_k be the set of k-dimensional subspaces of F_2^6. For every 1<=k<=5, the permutation group induced by G on Omega_k is 3-closed.
- `claim_root_psl62_geometric_maximal_actions_3closed_rev206` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2)=PSL_6(2), let V=F_2^6, and for 1<=k<=5 let P_k be the stabilizer of a k-dimensional subspace of V. Then the transitive action of G on G/P_k, equivalently on the k-dimensional subspaces of V, is 3-closed for every k.
- `claim_root_psl62_no_mutual_orbital_maxfactorization_rev249` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2). There do not exist proper maximal subgroups H,K<G such that G=HK, K and G have the same pair orbitals on G/H, and H and G have the same pair orbitals on G/K.
- `claim_root_psl62_no_mutual_orbital_maxpair_rev183` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2). There are no proper maximal subgroups H,K<G such that K and G have the same orbits on (G/H)^2 and H and G have the same orbits on (G/K)^2. Consequently the universal mutual-orbital factorization assertion for GL_{2d}(2), d>=3, is false at d=3.
- `claim_root_psl62_prime_order_fpr_sieve_rev564` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let X be a finite group and H<X. Let P(X) be the nonidentity X-conjugacy classes consisting of prime-order elements, and put q_X(H)=sum over C in P(X) of |H intersect C|^2/|C|. If q_X(H)<1, then X acting on X/H has a two-point base and is 3-closed. If K<=H, then q_X(K)<=q_X(H).
- `claim_root_psl62_primitive_closure_normalizer_reduction_rev217` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2), let M<G be maximal, and let C be the 3-closure of G on G/M. Then C is contained in the permutation normalizer of G, [C:G] is at most two, and C>G can occur only through the graph automorphism on a graph-stable conjugacy class of M. In that case C>G if and only if the induced graph permutation preserves every G-orbit on (G/M)^3.
- `claim_root_psl62_radicalfree31_reduction_rev168` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let V=F₂^6 and G=GL(V). If M≤G acts irreducibly on V and 31 divides |M|, then M is absolutely irreducible and primitive, C_G(M)=1, Rad(M)=1, and M is contained in no extension-field normalizer, nontrivial tensor-product stabilizer, or nondegenerate alternating-, quadratic-, or symmetric-form isometry group. Hence every counterexample to I31 is a proper maximal subgroup satisfying these restrictions.
- `claim_root_psl62_reducible31_overgroups_rev156` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let V=F_2^6 and G=GL(V). If M<G is maximal and 31 divides |M|, then either M is conjugate to the 1-space stabilizer P_1, M is conjugate to the 5-space stabilizer P_5, or M acts irreducibly on V. Consequently O31 is equivalent to the assertion that no irreducible maximal subgroup of G has order divisible by 31.
- `claim_root_psl62_sp6_graph_pair_separator_rev223` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=GL_6(2), let M=Sp_6(2) be the stabilizer of the standard nondegenerate alternating form J, let Omega=G/M, and let tau(g)=g^{-T}. There exists an ordered pair u in Omega^2 such that u^tau is not G-conjugate to u. Consequently tau does not belong to the 3-closure of G on Omega.
- `claim_root_psl62_symplectic_graph_pair_separator_rev351` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let G=PSL_6(2)=GL_6(2), H=Sp_6(2), and let pi be the permutation of G/H induced by the inverse-transpose graph automorphism. Then pi does not preserve all G-orbits on ordered pairs, and consequently pi is not in the 3-closure of G on G/H. Equivalently, the simultaneous-inversion assertion for all admissible relative-operator pairs is false.
- `claim_root_psl62_transitive_closure_equivalence_rev183` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For G=GL_6(2)=PSL_6(2), total 3-closure is equivalent to 3-closedness of every transitive coset action G/H with H<G.
- `claim_root_psln_central_vector_exact_nonclosure_rev399` `informally_verified` `superseded` `main_trunk` maturity=superseded root_distance=1: Let n>=4 and q>2, let V=F_q^n and Z=Z(SL(V)), and let G=SL(V)/Z act on Omega=(V-{0})/Z. This action is faithful. If X=GL(V)/Z in the same action, then G<X<=G^(3). Consequently PSL_n(q) is not totally 3-closed.
- `claim_root_psln_central_vector_nonclosure_corrected_rev38` `informally_verified` `superseded` `main_trunk` maturity=superseded root_distance=1: Let q>2 be a prime power and n>=4, and suppose PSL_n(q) is nonabelian simple. Let V=F_q^n and Z=Z(SL_n(q)). On Omega=(V minus {0})/Z, the faithful action G=SL_n(q)/Z satisfies G < GL_n(q)/Z <= G^(3). Consequently PSL_n(q) is not totally 3-closed.
- `claim_root_psln_central_vector_nonclosure_exact_rev283` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let V=F_q^n with n>=4 and q>2, let Z=Z(SL(V)), and let G=SL(V)/Z act on Omega=(V minus {0})/Z. Then this action is faithful and GL(V)/Z is a proper overgroup of G contained in G^(3). Hence PSL_n(q) is not totally 3-closed. More generally, GL(V)/Z<=G^(k) for every k<n.
- `claim_root_psln_central_vector_nonclosure_rev18` `refuted` `superseded` `main_trunk` maturity=superseded root_distance=1: Let q>2 be a prime power and n>=4, and suppose PSL_n(q) is nonabelian simple. Then PSL_n(q) is not totally 3-closed. More precisely, on the set of Z(SL_n(q))-orbits of nonzero vectors, its 3-closure properly contains GL_n(q)/Z(SL_n(q)).
- `claim_root_unordered_twoblock_binary_nogo_rev111` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let d>=3, V=F_2^(2d), S=GL(V)=PSL_(2d)(2), X=S semidirect <tau> with tau(g)=g^(-T), and H=<N_S(D*),tau> for an unordered decomposition D* of V into two d-spaces. On Omega=X/H, the relative outer base b_rel(X,S;Omega) is at most three. Indeed, three explicit decompositions have common stabilizer in X contained in S. Consequently X intersect S^(3)=S on this action, so the unordered two-block graph-normalizer cannot supply a graph-extension witness for non-total 3-closure.
- `root` `untested` `active` `root_theorem` maturity=verifier_gap root_distance=0: # Problem 20.2 restricted target: classify the totally 3-closed groups \(\operatorname{PSL}_n(q)\)

## Definitions

For a finite permutation group \(G\leq\operatorname{Sym}(\Omega)\), its
**3-closure** \(G^{(3)}\) is the largest subgroup of
\(\operatorname{Sym}(\Omega)\) having the same orbits as \(G\) on ordered
triples \(\Omega^3\). A finite abstract group is **totally 3-closed** when
every faithful finite permutation representation of it is 3-closed.

## Restricted classification problem

Classify, up to isomorphism, every nonabelian simple group
\[
S=\operatorname{PSL}_n(q)
\]
that is totally 3-closed, for every \(n\geq2\) and every prime power \(q\)
for which \(\operatorname{PSL}_n(q)\) is nonabelian simple.

This run concerns the projective special linear family only. Do not schedule
research on unitary, symplectic, orthogonal, exceptional, twisted, Suzuki, Ree,
or alternating families, except to record a low-rank exceptional isomorphism
needed to avoid double counting a \(\operatorname{PSL}_n(q)\) parameter.

The final result must be an if-and-only-if theorem. It must:

1. prove total 3-closure for every surviving \(\operatorname{PSL}_n(q)\), in
   every faithful finite permutation representation;
2. exclude every other simple \(\operatorname{PSL}_n(q)\) by a uniform theorem
   or an explicit faithful action with strictly larger 3-closure;
3. cover all \(n\), all prime powers \(q\), the simplicity exceptions, and all
   low-rank exceptional isomorphisms;
4. distinguish uniform arguments from computations of bounded finite cases;
5. give exact references, theorem numbers, and checked hypothesis translations
   for every external classification, maximal-subgroup, base-size, or orbit
   theorem used.

## Certified prior premises

The supervising mathematician authorizes the following results from the earlier
Problem 20.2 Albilich ledger as certified premises of this restricted run. They
may be used without reopening their proofs or repeating strict verification.
Preserve their exact scope and cite their proof and integration artifacts in the
final assembly.

1. **Two-orbit reduction.** For a finite nonabelian simple group \(S\), total
   3-closure is equivalent to 3-closedness of every diagonal action on
   \(S/H\sqcup S/K\), for all proper \(H,K<S\), with repetition allowed.
2. **Complete rank-one classification.** Among simple
   \(\operatorname{PSL}_2(q)\), total 3-closure holds exactly when \(q=p\) is
   a prime with \(p\geq7\). In particular, the positive prime cases
   \(p=7,11,13,19\) and all \(p\geq17\), \(p\neq19\), are certified; every
   proper extension-field case \(q=p^f\), \(f>1\), and \(q=5\) is excluded.
3. **Projective outer-witness theorem.** Let \(n\geq3\) and \(q=p^f\). If
   \(f>1\) or \(\gcd(n,q-1)>1\), then \(\operatorname{PSL}_n(q)\) is not
   totally 3-closed. On projective points its 3-closure contains a proper
   semilinear or diagonal extension.

The higher-rank residual family is therefore
\[
q=p\text{ prime},\qquad n\geq3,\qquad \gcd(n,p-1)=1.
\]
For odd \(p\), this forces \(n\) to be odd. For \(p=2\), it leaves every
rank \(n\geq3\), including even ranks, subject to simplicity and exceptional
isomorphisms.
Do not spend sessions reproving the three certified premises. If a genuine
logical inconsistency is discovered, record it precisely, but otherwise treat
these results as fixed inputs.

Authorized provenance is restricted to the PSL-related artifacts in:

- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_import_prior_two_orbit_reduction.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_import_two_orbit_reduction_rev23.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_import_psl27_totally_3closed_rev34.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_psl211_canonical_source_route_rev79.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_claim_psl213_total3closed_rev104.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_root_psl219_total3closed_rev158.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_root_psl2prime_extension_except19_rev125.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_verification_psl2_extension_field_nonclosure_rev162.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_researcher_psl2_extension_field_symbolic_closure_rev166.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_integration_import_psln_projective_nonclosure_rev48.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_verification_import_psln_projective_nonclosure_rev44.md`
- `agents/generation/results/kourovka/problem_20_2_classification_totally_3_closed_lie_type/phase2/artifacts/art_psl_projective_outer_witness_rev0.md`

Do not use non-PSL artifacts from the earlier ledger as mathematical evidence.

## Research program

Maintain an exhaustive parameter ledger. Each row must end as a certified
survivor, a rigorously excluded family, a finite exception requiring an exact
audit, or one precisely stated theorem-level obstruction.

Run full-proof-first. At regular intervals draft the shortest complete
classification proof and mark every unsupported sentence. Prefer a small
number of high-leverage uniform lemmas to a large inventory of case labels.

Use three genuinely different branches when parallel work is available:

1. a uniform structural proof or reduction for the residual prime-field,
   odd-rank family;
2. an adversarial construction branch seeking an explicit faithful action and
   a proper triple-orbit preserver, testing the full hypotheses;
3. an exact literature and bounded-CAS audit for low-rank parameters,
   exceptional isomorphisms, and any finite residue left by the uniform proof.

Natural graph automorphisms, contragredient duality, flag/Grassmannian actions,
parabolic block systems, diagonal actions on two coset spaces, and
normalizer-coset deck permutations are promising negative mechanisms, but
normalizing the group is not enough: triple-orbit preservation must be proved.
For positive conclusions, checking transitive coset actions alone is not
enough; invoke the certified two-orbit reduction and close every pair of proper
subgroups.

Do not extrapolate a computation beyond its certified finite range. Do not
declare completion while any admissible \((n,q)\) parameter remains uncovered.
- `claim_import_psl211_totally_3closed` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: The finite simple group PSL_2(11) is totally 3-closed: every faithful finite permutation representation of PSL_2(11) has 3-closure equal to its image.
- `claim_import_psl27_totally_3closed` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: The finite simple group PSL_2(7) is totally 3-closed: every faithful finite permutation representation of PSL_2(7) has 3-closure equal to its image.
- `claim_import_psln_projective_nonclosure` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let n>=3 and q=p^f. If f>1 or gcd(n,q-1)>1, then PSL_n(q) is not totally 3-closed; its natural point action on projective space has a proper 3-closure containing a semilinear or diagonal outer automorphism.
- `claim_import_two_orbit_reduction` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: For a finite nonabelian simple group S, total 3-closure is equivalent to 3-closedness of every diagonal action on the disjoint union S/H disjoint union S/K for all proper subgroups H,K of S, with repetition allowed.
- `claim_root_psl52_graphcentralizer_exact_counterexample_rev76` `informally_verified` `integrated` `partial_result` maturity=integrated root_distance=1: Let S=PSL_5(2)=GL_5(2), let X=Aut(S)=S semidirect <tau> with tau(g)=g^{-T}, and let L=C_X(tau). There exist three distinct elements tau_1,tau_2,tau_3 in tau^S such that C_X(tau_1,tau_2,tau_3) is contained in S. Consequently the universal outer-common-centralizer condition for this L is false and the graph-centralizer subgroup choice cannot supply the proposed outer 3-closure witness.

## Active Proof Debts

- `debt_root_residual_primefield_exclusion_rev7` `blocking` on `root`: Prove or refute the residual exclusion theorem R: for every prime p and n>=3 with gcd(n,p-1)=1 and (n,p)!=(3,2), PSL_n(p) is not totally 3-closed. A proof must cover every even-rank binary group PSL_n(2); a refutation must establish total 3-closure of a concrete residual group through all proper-subgroup pair actions using the certified two-orbit reduction.
- `debt_root_residual_exclusion_except_psl42_rev10` `blocking` on `root`: Prove that for every prime p and n>=3 with gcd(n,p-1)=1 and (n,p) not in {(3,2),(4,2)}, PSL_n(p) is not totally 3-closed. Together with the certified survivor PSL_3(2) and claim_root_psl42_not_totally3closed_rev10, this strictly narrower theorem implies the original residual exclusion theorem R.
- `debt_root_rank3_or_binary_residue_rev18` `blocking` on `root`: Prove or refute the strictly narrowed residual theorem: (i) PSL_3(3) and PSL_3(p) for every prime p>=5 with p congruent to 2 modulo 3 are not totally 3-closed; and (ii) PSL_n(2) is not totally 3-closed for every n>=5. A negative proof must give a faithful action and an explicit proper triple-orbit preserver for each family. A refutation must establish total 3-closure of a concrete residual group for every pair of proper-subgroup coset actions via the certified two-orbit reduction.
- `debt_root_psl52_graph_centralizer_triple_test_rev42` `blocking` on `root`: Decide the exact finite bridge for S=PSL_5(2): with X=Aut(S), graph involution tau, and L=C_X(tau), prove that every triple tau_1,tau_2,tau_3 in tau^S has C_X(tau_1,tau_2,tau_3) intersecting X minus S, or exhibit one explicit triple whose common centralizer is contained in S. In the first outcome, the proved quotient-surjectivity lemma gives S<X<=S^(3) on X/L; in the second, abandon this subgroup choice for the binary family.
- `debt_root_psl52_maximal_outer_class_exhaustion_rev56` `blocking` on `root`: Establish the exact X-conjugacy class list of maximal proper subgroups M<X for X=Aut(PSL_5(2)) with M not contained in S=PSL_5(2). Prove that every class is among the seven types tested in art_villain_root_psl52_outer_candidates_cas_rev56, or test each additional class. For every class, certify order, index, core-freeness, and either an explicit ordered triple whose stabilizer is contained in S or universal quotient-surjectivity. Only then may the maximal-overgroup argument rule out or validate the entire single-coset architecture.
- `debt_root_nonparabolic_graph_witness_rev93` `blocking` on `root`: Prove or refute the following strictly narrowed replacement-witness theorem. For every S in {PSL_3(3)} union {PSL_3(p): p>=5 prime and p congruent to 2 mod 3} union {PSL_n(2): n>=5}, there exists a proper graph-stable subgroup J<S which is nonparabolic, is not an ordered two-block Levi stabilizer, and is not the already-failed graph-centralizer, together with H=<J,gamma><S semidirect <gamma>, such that every intersection of at most three conjugates of H contains an outer element. Equivalently b_rel(S semidirect <gamma>,S;(S semidirect <gamma>)/H)>=4. A proof must construct J uniformly, prove faithfulness, and produce the outer element for every triple. A refutation must show b_rel<=3 for every remaining outer-containing maximal subgroup class, thereby forcing a genuinely non-normalizing two-coset mechanism.
- `debt_root_psl52_pair_action_decision_rev93` `blocking` on `root`: Decide the concrete PSL_5(2) pair-action theorem after the exact failure of the natural point and repeated-point witnesses: for every pair of proper subgroups H,K<=PSL_5(2), determine the 3-closure of the diagonal action on G/H disjoint-union G/K. Either exhibit one pair and an explicit permutation outside diagonal G preserving every ordered-triple orbit, or certify all pairs have closure G.
- `debt_root_graphstable_unordered_two_block_decision_rev99` `major` on `root`: Decide the remaining graph-stable imprimitive case n=2d: for X=PSL_{2d}(p) semidirect <tau> and H the full X-stabilizer of an unordered decomposition V=A direct-sum B with dim A=dim B=d, either prove b_rel(X,PSL_{2d}(p);X/H)<=3 or prove for a specified residual parameter that every triple stabilizer contains an outer element, hence b_rel>=4.
- `debt_root_evenbinary_nonnormalizing_twocoset_witness_rev111` `blocking` on `root`: Prove or refute the following narrowed even-binary witness theorem. For every d>=3 and S=PSL_(2d)(2), there exist proper subgroups H_d,K_d<S and a permutation pi_d outside the diagonal copy of S on S/H_d disjoint-union S/K_d that preserves every S-orbit on ordered triples. A proof must specify H_d,K_d uniformly, prove faithfulness, define pi_d, and check all mixed and unmixed triple types. The same-coset point, graph-centralizer, parabolic, ordered decomposition, r>=3 imprimitive, and unordered two-block graph-normalizer mechanisms are excluded and may not be reused without a genuinely new coupling argument.
- `debt_root_psl62_irreducible_graphstable_scan_rev117` `blocking` on `root`: Strictly narrower child of debt_root_evenbinary_nonnormalizing_twocoset_witness_rev111: for S=GL_6(2), enumerate the graph-stable irreducible maximal-subgroup classes H (and relevant pairs H,K) having no rank-labelled parabolic quotient, and either exhibit a class with relative outer base at least four and verify all mixed triple orbits, or prove relative outer base at most three for every such class. This finite seed test decides whether any componentwise graph-normalizer route remains before switching to a genuinely nonnormalizing two-constituent permutation.
- `debt_root_psl62_remaining_outer_maximal_class_exhaustion_rev138` `blocking` on `root`: Complete the strictly narrowed PSL_6(2) seed scan by certifying the X-conjugacy classes of maximal M<X=Aut(PSL_6(2)) with M not contained in S=PSL_6(2) and J=M intersect S irreducible on F_2^6. Prove that every such class is covered by Sp_6(2), GammaL_3(4), GammaL_2(8), GL_2(2) tensor GL_3(2), the already excluded GammaL_1(64), or containment in Sp_6(2); otherwise list each exception and compute its relative outer base. Acceptance requires class representatives, orders, irreducibility, graph-normalization data, completeness up to X-conjugacy, and an explicit relative base of size at most three for every exception. If no exception remains, pause the componentwise graph-normalizer route and activate the genuinely nonnormalizing two-constituent obligation.
- `debt_root_evenbinary_mutual_orbital_factorization_rev140` `blocking` on `root`: Prove or refute the following strictly narrower sufficient bridge for debt_root_evenbinary_nonnormalizing_twocoset_witness_rev111. For every d>=3, G=GL_(2d)(2) has proper maximal subgroups H_d,K_d such that G=H_d K_d and, with L_d=H_d intersection K_d, H_d=L_d(H_d intersection xH_d x^(-1)) and K_d=L_d(K_d intersection xK_d x^(-1)) for every x in G. Equivalently, K_d and G have the same pair orbitals on G/H_d and H_d and G have the same pair orbitals on G/K_d. A proof, combined with claim_root_piecewise_inner_twocoset_criterion_rev140, supplies the required faithful nonnormalizing two-coset witness. A certified refutation for d=3 kills this piecewise-inner architecture but does not refute the broader existential witness theorem.
- `debt_root_psl62_prime31_maximal_overgroups_rev150` `blocking` on `root`: Prove or refute the exact statement (O31): every maximal subgroup M<GL_6(2) whose order is divisible by 31 is conjugate to the point stabilizer P_1 or the hyperplane stabilizer P_5. Acceptance requires a complete maximal-class certificate, including any almost-simple or exceptional classes. If (O31) holds, art_researcher_root_psl62_prime31_maxpair_reduction_rev150 proves that no mutual-orbital maximal pair exists, refuting the uniform piecewise-inner architecture already at d=3. If an additional class exists, test it using the two exact permutation-character norm equalities from claim_root_mutual_orbital_character_scalar_test_rev150.
- `debt_root_psl62_irreducible31_overgroups_rev156` `blocking` on `root`: Prove or refute I31: no irreducible maximal subgroup M<GL_6(2) has order divisible by 31. Acceptance requires either a complete irreducible maximal-class certificate or an exact ppd-element overgroup theorem with every almost-simple and exceptional case for (d,q,e)=(6,2,5) checked. By claim_root_psl62_reducible31_overgroups_rev156, I31 is equivalent to O31. If I31 is false, exhibit the additional maximal class and evaluate its two permutation-character norm differences against every maximal class.
- `debt_root_psl62_radicalfree_primitive31_exclusion_rev168` `blocking` on `root`: Prove or refute A31-S: every proper maximal subgroup M<GL_6(2) that is absolutely irreducible and primitive and has Rad(M)=1 has order not divisible by 31. A proof, combined with claim_root_psl62_radicalfree31_reduction_rev168, proves I31 and kills the universal piecewise-inner mutual-orbital construction at d=3. A refutation must identify an explicit maximal class, its six-dimensional F₂ representation and order, and then submit that class to both character-scalar orbital tests.
- `debt_root_psl62_transitive_coset_3closure_decision_rev183` `blocking` on `root`: Decide T6 exactly: for every proper subgroup H<GL_6(2), prove that the coset action on G/H is 3-closed, or exhibit one concrete H and one permutation outside G preserving every G-orbit on ordered triples. A positive proof must cover all proper-subgroup conjugacy classes, not only maximal subgroups, unless it supplies a verified subgroup-chain lifting theorem. By claim_root_psl62_transitive_closure_equivalence_rev183, a proof makes PSL_6(2) totally 3-closed, while a counterexample directly proves it is not totally 3-closed.
- `debt_root_psl62_t6star_nongeometric_transitive_closure_rev190` `blocking` on `root`: Prove or refute T6*: for G=GL_6(2), every proper subgroup H<G not conjugate to one of the five standard parabolic subgroups P_1,...,P_5 has 3-closed coset action G/H. A proof must cover all nonmaximal H, not only the nine maximal classes. It may use claim_root_block_base3_lifting_rev190 by finding, for each H, an overgroup M with G/M 3-closed and of base size at most three; every residual H for which no such M exists must be handled by a direct fiber-kernel argument. A counterexample must give an explicit permutation in (G/H)^(3) outside G or an equivalent complete triple-orbit certificate.
- `debt_root_psl62_outer_maximal_triple_separation_rev217` `blocking` on `root`: Complete the primitive PSL_6(2) layer using claim_root_psl62_primitive_closure_normalizer_reduction_rev217. First certify the fusion of all nine ATLAS maximal-subgroup classes under the graph automorphism. Then, for every graph-stable nonparabolic class not already settled by art_researcher_root_psl62_geometric_actions_verification_packet_rev206, produce an explicit triple t with t^tau not in Gt, or produce a complete M-orbit certificate showing that tau preserves every ternary orbit. The current local packet predicts unresolved types Sp_6(2), 3.L_3(4):S_3, and (L_2(8) x 7):3. One preservation certificate is a faithful nonclosure witness; separating triples for every surviving class certify all primitive maximal actions as 3-closed. This debt does not include the later imprimitive fiber-kernel problem.
- `debt_root_psl62_extensionfield_graph_triple_separation_rev223` `blocking` on `root`: Let G=GL_6(2) and let tau be the graph automorphism. For each graph-stable maximal subgroup M of type 3.L_3(4):S_3 or (L_2(8) x 7):3, decide whether there exists an ordered triple t in (G/M)^3 with t^tau not G-conjugate to t. A proof must give an explicit invariant or auditable representatives and must check exact graph stability of the class. If every ternary orbit is tau-stable for either class, record tau as an explicit proper 3-closure element and use that action to exclude total 3-closure of PSL_6(2).
- `debt_root_psl62_gammaL34_eight_system_test_rev263` `blocking` on `root`: Decide the exact graph-orbit test for G=GL_6(2) on G/M with M=GammaL_3(4) of type 3.L_3(4):S3. Using claim_root_psl62_gammaL34_intertwiner_criterion_rev263, enumerate representatives of M-orbits on Omega x Omega. Either exhibit J1,J2 and certify that, for every epsilon in {+1,-1}^3, every solution of A Ji^(-T)=Ji^(epsiloni)A for i=0,1,2 is singular, or provide an invertible solution for at least one sign vector for every orbit representative. The first outcome proves this primitive action is 3-closed; the second supplies an explicit faithful nonclosure witness for PSL_6(2).
- `debt_root_psl62_gammaL34_minimal_pair_decision_rev269` `blocking` on `root`: Decide the GammaL_3(4) graph action through the stabilizer-coset criterion: certify the minimum order of D=M intersect M^g; for representatives attaining that minimum determine E=X_{M,gM}; and either exhibit E=D or a third coset outside the union of Fix_Ω(y) for y in E\D, or exhaustively certify outer-coset fixed-set coverage for every pair suborbit. Translate any separator into explicit matrices J_0,J_1,J_2 and certify that all eight simultaneous intertwiner systems have only singular solutions.
- `debt_root_residual_rank3_or_binary_rev283` `blocking` on `root`: Prove or refute the strictly narrowed residual exclusion theorem: every PSL_3(p) with p an odd prime and gcd(3,p-1)=1, and every PSL_n(2) with n>=5, is not totally 3-closed. The assembly must retain PSL_3(2) isomorphic to the certified survivor PSL_2(7) and may use the already excluded PSL_4(2).
- `debt_root_psl62_gammaL28_graph_ternary_decision_rev287` `blocking` on `root`: Strict child of T6 after the explicit GammaL_3(4) separator: for G=GL_6(2) and a graph-stable maximal subgroup M of type (L_2(8) times 7):3, decide whether the graph permutation tau preserves every G-orbit on (G/M)^3. Either exhibit one ordered triple t with t^tau not in Gt, using an auditable invariant or representatives, or prove complete ternary-orbit preservation and thereby obtain an explicit non-3-closed faithful action. A separating triple closes only this outer-normalizer branch and must not be promoted to T6 without the source-certified primitive closure-to-normalizer theorem and the remaining nonmaximal coverage argument.
- `debt_root_psl33_outside_scalar_fiber_decision_rev313` `blocking` on `root`: Decide the full original total-3-closure question for S=PSL_3(3) outside the now-closed scalar-fiber parabolic family: either exhibit proper subgroups H,K<S and a permutation outside the diagonal S on S/H disjoint-union S/K that preserves every S-orbit on ordered triples, or prove that every such proper-subgroup pair action is 3-closed.
- `debt_root_psl62_post_symplectic_exact_decision_rev351` `blocking` on `root`: After elimination of the graph permutation on PSL_6(2)/Sp_6(2), decide the finite theorem T6: either exhibit a faithful transitive action PSL_6(2)/H and a concrete permutation outside PSL_6(2) that fixes every ordered-triple orbit, with a proof not using the refuted symplectic graph permutation, or prove every proper-subgroup coset action of PSL_6(2) is 3-closed and invoke the certified transitive-action equivalence.
- `debt_root_psl33_exceptional_parabolic_orbital_E3_rev369` `blocking` on `root`: Prove or refute E3. Let G=PSL_3(3), P a point stabilizer, and E(P)={H<P proper : H cap H^g is nontrivial for every g in G}. The exhaustive finite sieve identifies exactly 24 actual members of E(P), of orders 48^9, 54^4, 72^3, 108^4, 144^3 and 216^1. Classify them up to G-conjugacy and, for each representative H, prove that every permutation fixing H and preserving every H-orbit on (G/H)^2 is induced by H, or exhibit a nonidentity such permutation. Trivial color automorphism groups prove all exceptional transitive actions 3-closed; a survivor is an explicit proper 3-closure witness. Explain the implication back to the PSL_3(3) two-orbit route and keep the maximal-subgroup completeness requirement explicit.
- `debt_root_binary_twoblock_decomposition_triple_test_rev373` `blocking` on `root`: Decide the remaining equal-block C2 case. For every d>=2 let G=GL_{2d}(2), let H=GL_d(2) wr Sym(2) stabilize an unordered decomposition into two complementary d-spaces, and let α(g)=g^{-T}. Either prove that for all x,y in G there is h in H with α(x)H=hxH and α(y)H=hyH, or give uniform explicit x,y for which no such h exists. In the idempotent model, points are unordered pairs {E,I+E}; a separating invariant must therefore be unchanged under independently replacing each represented idempotent by its complement.
- `debt_root_psl62_transitive_witness_gate_rev474` `blocking` on `root`: PSL_6(2) transitive-witness gate. Let G=GL_6(2). Either exhibit a proper subgroup H<G, not conjugate to the rank-one Levi GL_5(2) eliminated by claim_root_binary_antiflag_action_3closed_rev474, and an explicit permutation pi outside the induced G on G/H that preserves every G-orbit on (G/H)^3; or prove that every remaining proper-subgroup coset action G/H is 3-closed. In the first outcome, give a complete orbit-preservation argument rather than only a normalizer calculation. In the second outcome, combine the result with claim_root_binary_antiflag_action_3closed_rev474 and the integrated claim_root_psl62_transitive_closure_equivalence_rev183 to conclude that PSL_6(2) is totally 3-closed, thereby refuting residual exclusion theorem R at (n,p)=(6,2).
- `debt_root_psl33_E3_sixcolor_certificate_rev480` `blocking` on `root`: For G=PSL_3(3), construct the six explicit subgroups H of orders 48, 54, 72, 108, 144, and 216 classified in art_researcher_root_psl33_E3_affine_quotient_reduction_rev480. For each Ω=G/H, certify that every permutation fixing H and preserving every H-orbit on Ω² is induced by H. Acceptance requires explicit generators for H, the exact colored-orbital automorphism group and its order, and an auditable equality with the induced H. If a larger color group occurs, give an explicit extra permutation and separately decide whether it preserves every G-orbit on Ω³. No further subgroup-lattice enumeration is permitted.
- `debt_root_psl33_exceptional_mixed_M3_rev490` `blocking` on `root`: Prove or refute M3. Let G=PSL_3(3), let T be the six G-conjugacy types in E(P) certified by art_researcher_root_psl33_E3_exact_ternary_proof_rev490, and let T* be their dual line-parabolic types. For every H,K in T union T*, with repetition allowed, decide whether the diagonal action on G/H disjoint union G/K is 3-closed. A proof must audit point-point, line-line, point-line, and repeated-type pairs and explain the assembly with the two-point-base synchronization lemma, E3, the certified two-orbit reduction, and the still-separate maximal-subgroup completeness theorem. A refutation must exhibit an explicit permutation outside diagonal G that preserves every ordered-triple orbit.
- `debt_root_psl62_fpr_residual_rigidity_F6_rev564` `blocking` on `root`: Prove or refute residual rigidity F6. For G=GL_6(2), define q_G(H)=sum_C |H intersect C|^2/|C| over the G-classes of prime-order elements, necessarily of orders 2,3,5,7,31. Enumerate, with a complete G-fusion certificate, only the proper subgroup classes H satisfying q_G(H)>=1, using monotonicity to prune every descendant of a node L with q_G(L)<1. For every residual H, prove that G/H is 3-closed by computing the full automorphism group of its ternary orbital structure, or exhibit H and a concrete permutation outside G preserving every ordered-triple orbit. If every residual action is 3-closed, combine the result with claim_root_psl62_prime_order_fpr_sieve_rev564 and inference_root_psl62_transitive_closure_equivalence_rev183 to prove that PSL_6(2) is totally 3-closed.
- `debt_root_gl62_mutual_orbital_defect_table_rev588` `blocking` on `root`: For G=GL_6(2), enumerate the simultaneous G-conjugacy classes of ordered maximal-subgroup pairs (H,K) satisfying G=HK. For every pair put L=H intersection K and compute the exact defects D_H=|L backslash G/H|-|H backslash G/H| and D_K=|L backslash G/K|-|K backslash G/K|. Either certify that every pair has D_H>0 or D_K>0 and give a concrete split-orbit representative x witnessing the failed product identity, thereby refuting the d=3 instance of the piecewise-inner factorization architecture, or return a pair with D_H=D_K=0 together with generators and complete orbital certificates.
- `debt_root_gl62_c31_certificate_rev602` `blocking` on `root`: Certify C31 for G=GL_6(2): every maximal subgroup M<G whose order is divisible by 31 is conjugate to the one-space stabilizer P_1 or the five-space stabilizer P_5. The preferred bounded GAP certificate must enumerate maximal-subgroup conjugacy classes, filter by divisibility by 31, and return representative generators, orders, indices, and invariant-subspace dimensions. If a nonendpoint class survives, return its generators and restore defect calculations only for factor pairs involving that class.
- `debt_root_gl62_sylow31_mixed_pair_generation_rev606` `blocking` on `root`: Decide M31 for G=GL_6(2): fix a Sylow-31 subgroup P, U=C_V(P), and W=[V,P]. For every G-conjugate Q of P with C_V(Q) != U and [V,Q] != W, prove <P,Q>=G, or return one explicit mixed-endpoint Q with <P,Q><G. By the proved equivalence in art_researcher_root_gl62_sylow31_pair_generation_reduction_rev606, a positive certificate proves C31 and a negative certificate refutes C31.
