# Self-contained symbolic exclusion of extension-field PSL_2(q)

## Scope of this successor section

This changes only the non-prime-field A1 exclusion section and the separate PSL_2(5) witness. The integrated PSL_2(19) argument is retained unchanged. No citation or finite computation is used.

## Theorem

Let q=p^f >= 4. If f>1, then the natural faithful action of G=PSL_2(q) on Ω=P^1(F_q) is not 3-closed. Moreover PSL_2(5) has a faithful degree-five action that is not 3-closed. Consequently every proper-extension parameter in the A1 family, and also PSL_2(5), is not totally 3-closed.

## 1. A closure criterion

A permutation s of Ω belongs to G^(3) exactly when, for every ordered triple T in Ω^3, the triples T and s(T) lie in the same G-orbit. Indeed, this condition says that s preserves every G-orbit on Ω^3 setwise; adjoining s therefore neither merges nor splits any such orbit. Thus it is enough to construct a permutation outside G that fixes every triple orbit.

The projective action is faithful: an element of PGL_2(q) fixing 0, 1, and infinity is the identity, and PSL_2(q) is already the image after quotienting scalar matrices.

## 2. Two representations of the distinct-triple orbits

First representation: projective frames. PGL_2(q) acts sharply 3-transitively on P^1(F_q), since there is a unique fractional-linear transformation carrying any ordered triple of distinct points to any other. If q is odd, PSL_2(q) is the index-two subgroup consisting of projective classes represented by matrices of square determinant. If q is even, every field element has a square root, so PSL_2(q)=PGL_2(q).

Second representation: a homogeneous-coordinate invariant. For an ordered triple T=(x_1,x_2,x_3) of distinct projective points, choose nonzero column representatives v_i in F_q^2 and put

δ(T)=det(v_1,v_2) det(v_2,v_3) det(v_3,v_1),

viewed in F_q^*/(F_q^*)^2. Replacing v_i by λ_i v_i multiplies δ by (λ_1 λ_2 λ_3)^2, so its square class is well-defined. For A in GL_2(q),

δ(A T)=det(A)^3 δ(T),

and hence [δ(A T)]=[det(A)][δ(T)] in the square-class quotient.

This invariant completely classifies the PSL_2(q)-orbits on distinct triples when q is odd. Indeed, let A be the unique projectivity carrying T to T'. The displayed formula gives

[δ(T')/δ(T)]=[det(A)].

Thus T and T' are PSL_2(q)-equivalent exactly when their δ-classes agree. This also proves the round-trip equivalence with the projective-frame representation: the two distinct-triple orbits are precisely the two cosets of PSL_2(q) in PGL_2(q), labeled by δ.

For triples with fewer than three distinct entries, the exact equality pattern is a complete orbit invariant. To see completeness, note that PSL_2(q) is 2-transitive: its upper unipotent matrices act as all translations on the affine line, while a determinant-one inversion moves infinity into that line. Therefore there is one orbit for each ordered equality pattern.

## 3. Even extension fields

Suppose q is even. Then G=PGL_2(q), so sharp 3-transitivity shows that its triple orbits are exactly the equality-pattern classes. Every permutation of Ω preserves those classes. Hence

G^(3)=Sym(Ω).

For q>=4 this containment is strict, since

|Sym(Ω)|/|G|=(q+1)!/[q(q^2-1)]=(q-2)!>1.

Thus the natural action is a faithful non-3-closed action.

## 4. Odd extension fields

Now suppose q=p^f is odd with f>1. Let σ be the prime-field Frobenius permutation

σ([u:v])=[u^p:v^p].

It preserves every equality pattern. If T has three distinct entries, then

δ(σ T)=δ(T)^p.

The quotient F_q^*/(F_q^*)^2 has order two, and p is odd, so raising to the p-th power acts trivially on it. Hence [δ(σ T)]=[δ(T)]. By the orbit classification above, σ sends every ordered triple to a triple in the same PSL_2(q)-orbit. Therefore σ belongs to G^(3).

On the other hand σ is not in PGL_2(q), hence not in G. It fixes 0, 1, and infinity; a projectivity fixing those three points is the identity. But σ is not the identity because the fixed field of x↦x^p is F_p and f>1. Thus G<G^(3), proving non-3-closure.

This argument explicitly repairs the normalizer-only near miss: merely knowing that Frobenius normalizes PSL_2(q) would not suffice, because a normalizer element can permute triple orbits. The δ computation proves that Frobenius fixes, rather than swaps, the two distinct-triple orbits.

## 5. A self-contained degree-five witness for PSL_2(5)

Let G=PSL_2(5)=SL_2(5)/{±I}; it has order 60. We construct its faithful action on its five Sylow 2-subgroups without invoking the exceptional isomorphism in advance.

A projective involution is represented by a trace-zero matrix A in SL_2(5), and conversely trace zero gives A^2=-I. Write

A=[[a,b],[c,-a]].

The determinant equation is bc=-1-a^2. For a=±2 the right side is zero, giving 9 ordered pairs (b,c) for each a; for each of the other three values of a it is nonzero, giving 4 pairs. Thus SL_2(5) contains 30 trace-zero matrices, paired by A and -A, so G has 15 involutions.

Every such A is SL_2(5)-conjugate to diag(2,-2). A projective element centralizes its class exactly when an SL_2(5) lift preserves or interchanges the two eigenspaces. There are four diagonal determinant-one lifts and four anti-diagonal determinant-one lifts; quotienting by {±I} gives a centralizer of order four. Its three nonidentity elements are involutions, so it is a Sylow 2-subgroup isomorphic to C_2×C_2. Any Sylow 2-subgroup containing an involution t is abelian and hence lies in C_G(t); it must therefore equal C_G(t). Each involution lies in a unique Sylow 2-subgroup, and the 15 involutions consequently partition into five triples. Hence G has exactly five Sylow 2-subgroups.

Let X be this five-element set and let K be the kernel of the conjugation action G→Sym(X). The action is transitive, so a Sylow normalizer has order 60/5=12, and K lies in every such normalizer; therefore |K| divides 12. All 15 involutions form one conjugacy class because their centralizers have order four. If K contained an involution, normality would force it to contain all 15, contradicting |K|<=12. Thus |K| is odd and is either 1 or 3. The latter is impossible: it would be the unique Sylow 3-subgroup, whereas the matrices

M=[[0,-1],[1,-1]] and N=M^T

both have determinant one and satisfy X^2+X+I=0, and direct inspection of M, M^2, and their negatives shows that their projective classes generate two distinct order-three subgroups. Hence K=1.

The image therefore has order 60 and index two in S_5, so it is A_5. This action is sharply 3-transitive: a bijection between two ordered triples of distinct points has two extensions to a permutation of five points, differing by the transposition of the two unused points, and exactly one extension is even. Consequently the G-orbits on X^3 are again exactly the equality-pattern classes. The whole S_5 preserves these classes, so

G^(3)=S_5>G.

Thus PSL_2(5) is not totally 3-closed.

## 6. Proof-spine assembly

1. The integrated two-orbit reduction converts total 3-closure into control of all paired transitive constituents.
2. The integrated prime-field A1 dossiers establish the positive prime-field cases, including PSL_2(13), PSL_2(19), and the earlier PSL_2(7), PSL_2(11) certificates.
3. The theorem proved above excludes every proper-extension PSL_2(q) and separately excludes PSL_2(5) by explicit faithful actions.
4. The integrated projective-space theorem excludes higher-rank PSL_n(q) whenever f>1 or gcd(n,q-1)>1.
5. Exactly one root-level theorem remains: exclude every residual higher-rank classical, exceptional, twisted, Suzuki, and Ree parameter not covered by Step 4, together with a complete exceptional-isomorphism ledger.

Dependency spine: two-orbit reduction plus positive prime-field A1 certificates plus the present extension-field exclusion plus the integrated projective-space exclusion implies the full root classification once the single residual-family theorem in Step 5 is proved.

## Self-check

The proof separately covers q even, q odd with f>1, and q=5. It includes the boundary cases q=4 and q=9. Faithfulness is checked in both witness actions. Repeated-coordinate triples are handled through 2-transitivity and equality patterns. Frobenius is proved to preserve each orbit, not merely to normalize G. The determinant invariant is independent of homogeneous-coordinate choices, and its equivalence with the PGL_2/PSL_2 quotient proves completeness of the orbit classification. No source theorem or CAS output is used.
