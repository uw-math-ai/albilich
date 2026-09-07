# Route-conversion diagnostic

## Verdict
The named proof candidate `advisor_post_psp_unitary_bottleneck_rev41` is not verifier-ready evidence for a sufficient route to `root`. It is a mathematically useful steering report, but it contains no proof of the remaining unitary or orthogonal common-overgroup theorems and no final chief-factor/CFSG assembly. Creating a sufficient root route from it would therefore expose a verifier-known gap.

The graph-derived PSL obligation is stale: `claim_psl_outer_coset_decomposition_normalizer` is already integrated through the informally verified inference `inf_psl_outer_normalizer_descent_forms`. The symplectic analogue is likewise integrated through `inf_psp_outer_normalizer_module_descent`. Neither node should be reopened.

## Compressed current proof spine
1. Chief-factor reduction: a sufficiently large alternating subgroup of a putative host must survive inside a nonabelian simple constituent of a minimal nonabelian chief factor.
2. Alternating-factor obstruction excludes sufficiently large alternating constituents.
3. `inf_psl_outer_normalizer_descent_forms` supplies the high-dimensional linear product-normalizer obstruction, including outer cosets and wreath-product gauge correction.
4. `inf_psp_outer_normalizer_module_descent` supplies the corresponding high-dimensional symplectic obstruction.
5. The next arrow toward the residual classical theorem is the unitary product-normalizer bridge stated below.

Dependency spine: chief-factor reduction -> familywise common-proper-overgroup theorems -> exclusion of high-dimensional constituents -> bounded-rank/projective-degree argument -> a large alternating counterexample to the proposed embedding property.

## Single next theorem-level gap
Fix distinct primes p and q and put R=max(p,q). Prove that there are integers E=E(p,q) and n0=n0(p,q)>2E such that, for every prime power Q, every nondegenerate Hermitian space V over F_(Q^2) of dimension n>=n0, S=PSU(V), every r in {p,q}, and every alpha in Aut(S) of order dividing r, some S-conjugate of alpha lies in the proper subgroup

D_E=N_Aut(S)(M_E),

where M_E is the projective unitary decomposition subgroup preserving a fixed orthogonal decomposition V=U perpendicular W with dim(U)=E. The proof must cover inner-diagonal, field, graph, and graph-field cosets; D_E must meet every outer coset used in the conjugator correction. It must also prove that every order-r element of Aut(S) wr S_t is S^t-conjugate into D_E wr S_t for every t>=1.

A verifier-ready proof must establish: (i) a uniform Hermitian self-dual block lemma giving bounded-dimensional nondegenerate invariant summands when a unitary similitude has prime projective order; (ii) form-compatible semilinear descent for field and graph-field cosets; (iii) correction of a projective semilinear conjugator into PSU(V) using an element of the fixed decomposition subgroup without changing the outer coset; (iv) properness of D_E; and (v) the factor-cycle gauge argument in the wreath product.

## Sanity check and obstruction
The symplectic proof cannot be cited verbatim: a Hermitian form is sesquilinear, so the relevant module duality twists scalars by the Q-Frobenius involution. Any Krull-Schmidt argument must use this twisted duality, and semilinear descent must preserve the Hermitian form up to multiplier. Omitting either twist leaves the field and graph-field cases unjustified.

No sufficient route or plausible inference is added in this patch because the candidate artifact proves none of these unitary assertions.
