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
