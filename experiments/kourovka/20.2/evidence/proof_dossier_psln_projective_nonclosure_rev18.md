# Projective-point obstruction for PSL(n,q), n≥3

## Local theorem

Let n≥3 and q=p^f. If f>1 or gcd(n,q−1)>1, then G=PSL(n,q) is not totally 3-closed. In fact, its natural faithful action on Ω=P^{n−1}(F_q) is not 3-closed.

## Determinant-correction lemma

Let δ:PGL(n,q)→F_q^×/(F_q^×)^n be defined by δ([A])=det(A)(F_q^×)^n. This is well-defined because replacing A by cA multiplies its determinant by c^n, and ker(δ)=PSL(n,q).

For every ordered triple T=(L_1,L_2,L_3) of projective points, the pointwise stabilizer PGL(n,q)_(T) maps surjectively under δ. Indeed, let r be the dimension of the span of representative vectors for the distinct lines occurring in T. If three independent lines occur, scale one basis vector by an arbitrary a∈F_q^× and fix the remaining basis vectors. If at most two distinct lines occur, choose a basis containing representatives of those lines and again scale one representative by a. The only exceptional-looking configuration is three distinct collinear points: every linear map on their two-dimensional span fixing all three lines is scalar, but n≥3 supplies a complementary basis vector, which may be scaled by arbitrary a while the two-dimensional span is fixed pointwise. In every case there is a projectivity fixing T pointwise whose determinant has any prescribed class in F_q^×/(F_q^×)^n.

Consequently PSL(n,q) and PGL(n,q) have exactly the same orbits on Ω^3. To see this, take h∈PGL(n,q) and T∈Ω^3, and put U=h(T). Choose s∈PGL(n,q)_(U) with δ(s)=δ(h)^{-1}. Then sh∈PSL(n,q) and sh(T)=U=h(T). Thus every PGL-image of every ordered triple already lies in its PSL-orbit, so PGL(n,q)≤G^(3).

## Proper closure witnesses

Put d=gcd(n,q−1). Since PGL(n,q)/PSL(n,q) has order d, if d>1 then any element of PGL(n,q)\PSL(n,q) is an explicit element of G^(3)\G.

Suppose instead that f>1. The PGL(n,q)-orbits on ordered triples of projective points are determined as follows: first by the equality pattern; for three distinct points, by whether they are collinear. PGL is transitive on each such class. For the collinear class this follows from the sharply 3-transitive action of PGL(2,q) on a projective line, and for the noncollinear class it follows by sending three independent representative lines to three coordinate lines.

The Frobenius permutation σ induced by raising every homogeneous coordinate to its p-th power preserves equality and collinearity, hence preserves every PGL-orbit and therefore every PSL-orbit on Ω^3. Thus σ∈G^(3). It is not a projectivity: it fixes the projective frame [e_1],…,[e_n],[e_1+⋯+e_n], so any projectivity inducing σ would be the identity, whereas σ moves [e_1+a e_2] for a∈F_q\F_p. Hence σ∉PGL(n,q), and in particular σ∉G. This proves the local theorem.

## Exact intransitive-action interface for the residual case

Let a faithful G-set be a disjoint union Ω=⊔_i Ω_i, and suppose a permutation π preserves every Ω_i and restricts on Ω_i to the action of some g_i∈G. With right-action notation, π belongs to G^(3) exactly when, for every ordered triple x_1,x_2,x_3 with x_j∈Ω_{i_j}, the three right cosets

G_{x_1}g_{i_1}, G_{x_2}g_{i_2}, G_{x_3}g_{i_3}

have nonempty intersection. Indeed, a single g∈G matches π on that triple precisely when x_j^g=x_j^{g_{i_j}} for all j, equivalently g∈G_{x_j}g_{i_j} for all j. The permutation π is outside the diagonal copy of G precisely when no single g matches it on all of Ω. Thus a non-3-closed intransitive action is a three-wise compatible but globally incompatible system of stabilizer cosets. This is the appropriate replacement for the failed low-degree transitive-coset search for PSL(3,2)≅PSL(2,7).

## Source adaptation

Freedman, Giudici and Praeger, “Total closure for permutation actions of finite nonabelian simple groups,” Monatshefte für Mathematik (2023), DOI 10.1007/s00605-023-01822-5, arXiv:2206.02347, Corollary 3.3, state: if X is a finite nonabelian simple group and b_maxprim(X) is the maximum base size among its faithful primitive permutation actions, then its closure number satisfies k(X)≤b_maxprim(X)+1. Here k(X) is the least k for which X is totally k-closed, and a base is a set of points with trivial pointwise stabilizer.

The hypotheses apply to PSL(n,q), but the implication is only an upper bound. It cannot prove failure of total 3-closure from a large primitive base and supplies no element outside a 3-closure. Its reusable move is the reduction of arbitrary faithful actions to primitive actions through maximal block systems; the missing negative interface is an orbit-preserving external permutation. The determinant-correction and Frobenius arguments above supply that interface directly for the stated family.

## Relation to the current PSL(2,7) obstruction

The manifest-listed exhaustive GAP report for PSL(2,7) states that every transitive coset action arising from a proper subgroup of index at most 32 has 3-closure equal to PSL(2,7). Therefore the advisor's proposed low-degree transitive witness is refuted within its complete finite scope. This does not establish total 3-closure: the intransitive three-wise coset-consistency mechanism above is not tested by that sweep.

## Root assembly and remaining boundary

Combining this theorem with the already verified projective-line result excludes PSL(2,p^f) for f>1, PSL(2,5), and PSL(n,p^f) for n≥3 whenever f>1 or gcd(n,p^f−1)>1. The root remains open for PSL(2,p) with odd p≥7, for PSL(n,p) with n≥3 and gcd(n,p−1)=1, and for the other Lie-type families. The smallest residual type-A group is PSL(3,2)≅PSL(2,7).

## Self-check

The projective action is faithful. The determinant class is independent of the matrix representative, and every equality/collinearity configuration of triples is covered. The critical configuration of three distinct collinear points uses n≥3 exactly through a complementary vector. Frobenius is shown to preserve each triple orbit rather than merely permute the orbit set, and its exclusion from PGL uses a full projective frame plus an explicitly moved point. No conclusion is drawn for prime-field cases with gcd(n,p−1)=1 or from the bounded PSL(2,7) computation beyond its stated scope.
