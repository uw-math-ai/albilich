# GL_6(2) prime-31 endpoint obstruction

## Exact local target

Let G=GL_6(2), let H,K be proper maximal subgroups with G=HK, and put L=H intersection K. Write

D_H=|L backslash G/H|-|H backslash G/H|,
D_K=|L backslash G/K|-|K backslash G/K|.

The scheduled universal factorization bridge requires such a pair with D_H=D_K=0 when d=3. The following argument reduces its refutation to one much smaller finite certificate.

## The single finite hypothesis C31

(C31) Every maximal subgroup M<G whose order is divisible by 31 is conjugate either to P_1, the stabilizer of a nonzero vector, or to P_5, the stabilizer of a hyperplane.

This is strictly weaker than an exact maximal-factor-pair defect table and weaker than a complete maximal-subgroup classification.

## Prime-31 endpoint lemma

Assume C31. Then no proper maximal subgroups H,K<G with G=HK satisfy D_H=D_K=0.

### Proof

The group order is

|G|=2^15 3^4 5 7^2 31.

Since G=HK,

|G|=|H||K|/|H intersection K|,

so 31 divides |H||K|. After interchanging H and K, suppose 31 divides |K|. Hypothesis C31 makes K an endpoint parabolic, of type P_1 or P_5.

The action of G on G/K has degree 63 and is 2-transitive. For K=P_1 this is the action on the 63 nonzero vectors of F_2^6: two distinct nonzero vectors are automatically linearly independent and any ordered independent pair can be mapped to any other. The P_5 case is the dual action on hyperplanes.

The verified double-coset dictionary says that D_K=0 is equivalent to H and G having the same pair orbitals on G/K. Since G is 2-transitive, D_K=0 therefore forces H to be 2-transitive on this 63-point set. Orbit-stabilizer then gives

63·62 divides |H|.

In particular 31 divides |H|, so C31 also makes H an endpoint parabolic.

It remains to check the four endpoint orientations. On nonzero vectors, a P_1-type subgroup fixes its defining vector, while a P_5-type subgroup preserves the two nonempty subsets consisting of the 31 nonzero vectors inside its defining hyperplane and the 32 vectors outside it. Thus neither endpoint type is transitive, let alone 2-transitive, on G/P_1. Dually, on hyperplanes a P_5-type subgroup fixes its defining hyperplane, while a P_1-type subgroup preserves the nonempty classes of hyperplanes containing or not containing its defining vector. Thus neither endpoint type is transitive on G/P_5.

This contradicts the 2-transitivity forced by D_K=0. Hence no maximal factor pair has D_H=D_K=0. QED.

## Consequence for the decisive obligation

Once C31 is certified, the d=3 instance of the proposed statement for every d>=3 is false. Therefore debt_root_evenbinary_mutual_orbital_factorization_rev140 is refuted and the piecewise-inner mutual-orbital architecture must be abandoned. This does not refute the broader two-coset witness theorem and does not decide residual exclusion theorem R.

## Representation switch

The original representation asks for all maximal factor pairs and four double-coset counts for each pair. The first switch records only the prime divisor 31 in |G|: every factorization has a factor whose order is divisible by 31. The second switch uses D_K=0 as equality of pair orbitals; because the endpoint action has rank two, this becomes ordinary 2-transitivity of the opposite factor. The order of a 2-transitive group of degree 63 is divisible by 63·62 and hence again by 31. Thus both factors are forced into the two endpoint geometries, where transitivity fails visibly.

The round trip is exact: C31 plus the prime-divisor argument implies the nonexistence of a zero-zero defect pair, which refutes the d=3 instance and hence the universal factorization bridge.

## Two proof attacks

Attack A, the factor-order attack, uses |G| dividing |H||K| to force one factor into the 31-local maximal-overgroup problem. It replaces enumeration of factor pairs by certification of C31.

Attack B, the orbital-rank attack, converts the remaining defect equality into 2-transitivity on projective points or hyperplanes. The divisibility 63·62 divides |H| forces the other factor into the same endpoint list, and elementary incidence geometry then gives the contradiction.

These attacks meet at C31 but use different invariants: prime support of subgroup orders and rank-two permutation geometry.

## Bounded certification request

A later CAS-mode pass can certify C31 in GAP for the single finite group GL(6,2): enumerate conjugacy classes of maximal subgroups, filter those whose orders are divisible by 31, and identify each survivor as a one-space or five-space stabilizer. The decisive output is the complete filtered list, representative generators, subgroup orders and indices, and the dimensions of invariant subspaces. If a nonendpoint survivor appears, return its generators; that outcome invalidates C31 and restores the full defect calculation for that class only.

## Strongest failed route and route decision

The equal-block C2 graph-normalizer route is already dead because the commutator-rank invariant separates a triple from its transpose; it is not retried here. The distinct piecewise-inner factorization route is conditionally killed at d=3 by the prime-31 endpoint lemma and should be abandoned once C31 receives its bounded certificate.

## Compressed root proof spine

1. The certified rank-one classification settles n=2.
2. The certified projective outer witness excludes extension fields and parameters with gcd(n,q-1)>1.
3. C31 together with the prime-31 endpoint lemma refutes the proposed uniform piecewise-inner factorization bridge at PSL_6(2).
4. The equal-block graph route and the piecewise-inner route are therefore unavailable for residual exclusion.
5. The unique remaining theorem-level gap is residual exclusion theorem R, which now requires a genuinely different witness mechanism or a proof of total 3-closure for a concrete residual group.

Dependencies: 1 and 2 reduce the classification to R; C31 implies 3, and 3 implies abandonment in 4. Step 5 is the only remaining theorem-level gap. C31 itself is a bounded finite certification obligation rather than a new infinite theorem.

## Self-check

Maximality is used only in C31. The orientation of the defect is checked: D_K=0 says that H and G have the same pair orbitals on G/K. Both point and hyperplane endpoint cases are treated. The argument uses no external theorem as a proof premise, does not infer an infinite statement from computation, and quarantines the sole unverified finite input C31. It refutes only the universal factorization architecture, not residual exclusion theorem R.
