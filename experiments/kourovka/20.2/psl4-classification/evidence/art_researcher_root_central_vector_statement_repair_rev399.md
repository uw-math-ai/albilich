# Exact statement repair for the central-vector route

## Corrected theorem

Let V=F_q^n with n>=4 and q>2, let Z=Z(SL(V)), and let Omega=(V-{0})/Z. In the natural faithful action on Omega, put

G=SL(V)/Z isomorphic to PSL_n(q),
X=GL(V)/Z.

Then

G < X <= G^(3).

Consequently PSL_n(q) is not totally 3-closed. The stronger auxiliary assertion X<G^(3) is neither required nor generally true.

## Attack 1: direct determinant correction

First compute the action kernels. Suppose A in GL(V) fixes every point of Omega. For every nonzero v there is z_v in Z such that Av=z_v v. Choose a basis e_1,...,e_n. Applying linearity to e_i+e_j gives

z_{e_i}e_i+z_{e_j}e_j=A(e_i+e_j)=z_{e_i+e_j}(e_i+e_j),

so z_{e_i}=z_{e_j} for every i,j. Thus A=zI for a single z in Z. Conversely every element of Z acts trivially. Hence both GL(V)/Z and SL(V)/Z act faithfully on Omega.

Because Z is contained in SL(V),

[X:G]=[GL(V):SL(V)]=q-1>1,

and therefore G<X.

Now fix A in GL(V) and an ordered triple t=([v_1],[v_2],[v_3]) in Omega^3. Let W=span(v_1,v_2,v_3). Then dim W<=3<n. Choose V=W direct-sum U. Consequently V=A(W) direct-sum A(U), with A(U) nonzero. There exists D in GL(V) which is the identity on A(W) and whose determinant on A(U) is det(A)^(-1): in a basis of A(U), take the diagonal map with entries det(A)^(-1),1,...,1. Put B=DA. Then det(B)=1 and Bv_i=Av_i for i=1,2,3. Thus A(t)=B(t) with B in SL(V).

This holds for every A and every ordered triple, including repeated or linearly dependent triples. Hence every element of X maps each G-orbit on Omega^3 to itself, so X<=G^(3). Together with G<X this proves the corrected theorem and supplies a faithful action whose 3-closure properly contains G.

## Attack 2: permutation-factorization formulation

For the same triple t, let P_t be the subgroup of GL(V) fixing v_1,v_2,v_3 pointwise. Since their span has codimension at least one, the determinant map P_t -> F_q^* is surjective: arbitrary determinant can be placed on a one-dimensional subspace of a complement while the span is fixed pointwise. Therefore

GL(V)=SL(V)P_t.

Since P_t is contained in the stabilizer of t, this factorization is equivalent to equality of the GL(V)- and SL(V)-orbits of every ordered triple. Passing through the faithful quotient by Z gives X<=G^(3). This reformulation isolates the exact hypothesis: the pointwise stabilizer of every tested triple must have surjective determinant.

## Refutation of the stale stronger assertion

Take (n,q)=(4,3). Here Z=F_3^*I, so Omega is PG(3,3) and X=PGL_4(3). The determinant-correction argument shows that PSL_4(3) and PGL_4(3) have identical ordered-triple orbits.

Conversely, every permutation in G^(3) preserves the set of triples of distinct collinear projective points. Hence it maps projective lines to projective lines. To see directly that such a permutation is projective linear, compose it with an element of PGL_4(3) so that it fixes a projective frame. On a coordinate line it then has the form

[e_i+t e_j] -> [e_i+sigma(t)e_j].

Incidences among coordinate lines and coordinate planes force the same map sigma on every coordinate line, force sigma to preserve addition and multiplication, and then determine every projective point from its coordinates. Thus sigma is a field automorphism. The field F_3 has no nonidentity automorphism, so the normalized permutation is the identity. Therefore every collinearity-preserving permutation lies in PGL_4(3), and

G^(3)=PGL_4(3)=X.

Thus X<G^(3) is false in this concrete case. Replacing it by G<X<=G^(3) is a necessary statement repair, not a weakening of the nonclosure conclusion.

## Implication and boundary audit

The implication needed by the classification route is only

G<X<=G^(3) implies G<G^(3),

so the displayed faithful action is not 3-closed. No assertion about whether X is the whole 3-closure is used.

The condition q>2 is exact for this witness: when q=2, [X:G]=q-1=1, so X=G and the determinant overgroup disappears. The condition n>=4 is exact for the universal triple correction: in dimension three, a triple can span V, its pointwise stabilizer can be trivial, and there is then no complementary direction on which to change the determinant. These are obstructions to this method, not counterexamples to the classification target.

## Root proof spine after the repair

1. The certified rank-one theorem classifies all simple PSL_2(q), with precisely PSL_2(p), p prime and p>=7, surviving.
2. The certified projective outer-witness theorem excludes every higher-rank case with a proper extension field or gcd(n,q-1)>1.
3. The corrected central-vector theorem above excludes every n>=4, q>2 case, including all residual odd-prime ranks n>=5.
4. Therefore the only higher-rank parameters not yet decided are PSL_n(2) for n>=4 and PSL_3(p) for odd primes p with gcd(3,p-1)=1. The parameter PSL_3(2) is the certified survivor PSL_2(7).

The single remaining theorem-level gap is to exclude exactly those two residual families.

## Self-check

The quotient kernels are exactly Z; the index computation uses Z<=SL(V); determinant correction works for repeated and dependent triples; the complement is nonzero precisely because n>=4; and q>2 is used precisely to make G<X. The equality example proves that the discarded strict inclusion can fail. No external theorem or computation is used, and no conclusion is drawn for q=2 or n=3.
