# Binary Lemma B: two uniform graph-stable subgroup families fail already on pairs

Let G=GL_n(2)=PSL_n(2) and let α(g)=g^{-T}. Binary Lemma B asks for a proper α-stable subgroup H such that the permutation induced by α on G/H preserves every G-orbit on ordered triples. The following two symbolic obstructions eliminate the nonalternating-polarity family and every equal-block decomposition family having at least three blocks.

## 1. Double-coset test

If the simultaneous interpolation condition holds for H, set y=1. For every x in G there must then be h in H such that α(x)H=hxH. Equivalently,

α(x) belongs to HxH for every x in G.                              (1)

Thus one H-double coset moved by α separates the pair (H,xH) from (H,α(x)H). It follows at once that the induced graph permutation is outside the 2-closure and hence outside the 3-closure, since pair orbitals are recovered from triples with a repeated coordinate.

## 2. Equal-block decomposition stabilizers with at least three blocks

Write n=dm with m at least 3 and fix a decomposition

V=V_1 direct-sum ... direct-sum V_m,  dim(V_i)=d.

Let H be its setwise stabilizer. In block coordinates, H is GL_d(2) wr Sym(m): its elements are block-monomial matrices, with exactly one invertible d by d block in every block row and block column. Hence H is proper and α-stable.

For a block matrix z, let b(z) be the number of its nonzero d by d blocks. Left or right multiplication by an element of H only permutes block rows or columns and multiplies individual blocks by invertible matrices. Consequently

b(h_1 z h_2)=b(z) for all h_1,h_2 in H.                             (2)

Let N have identity blocks in positions (1,2) and (2,3), and zero blocks elsewhere, and put x=I+N. Then N^3=0 and, in characteristic two,

x^{-1}=I+N+N^2.

The matrix x has its m diagonal blocks and the two indicated off-diagonal blocks, so b(x)=m+2. The extra block (1,3) of N^2 is nonzero, so b(x^{-1})=m+3. Transposition does not change block-support cardinality; therefore

b(α(x))=b(x^{-T})=m+3 != m+2=b(x).

By (2), α(x) is not in HxH. This contradicts the necessary condition (1). Thus the graph permutation on the set of unordered decompositions into m at least 3 equal summands moves a pair orbital and cannot witness Binary Lemma B.

Geometrically, the nonzero-block support of x is a directed path 1→2→3 together with loops. Inversion adds the transitive shortcut 1→3. Relabelling summands and changing bases inside them cannot remove that shortcut.

## 3. Stabilizers of nonalternating symmetric bilinear forms

Let H=O(I_n,2)={h in G: h^T h=I}. Then H is proper and α fixes H pointwise, because h^{-T}=h for h in H.

Identify G/H with the congruence orbit of I by

 gH maps to A_g=g^{-T}g^{-1}.

This is well defined, and α sends A_g to

A_{α(g)}=g g^T=A_g^{-1}.                                           (3)

The stabilizer H acts on these matrices by A maps to hAh^{-1}; hence the characteristic polynomial is constant on every H-orbit.

Over F_2 put

S=((1,1,1),(1,1,0),(1,0,0)),
C=((1,1,1),(0,1,1),(0,1,0)).

Direct multiplication gives C^T C=S, so S is nonsingular and congruent to I_3. A determinant expansion gives

χ_S(t)=t^3+t+1.

For n at least 3 set A=S direct-sum I_{n-3}. With D=C direct-sum I_{n-3} and g=D^{-1}, one has A=A_g. Its characteristic polynomial is

χ_A(t)=(t^3+t+1)(t+1)^{n-3}.

Since det(A)=1, the characteristic polynomial of A^{-1} is the reciprocal polynomial

χ_{A^{-1}}(t)=(t^3+t^2+1)(t+1)^{n-3},

which differs from χ_A(t). Thus A and A^{-1} are not conjugate even in GL_n(2), and in particular are not H-conjugate. By (3), graph duality moves the pair orbital containing (I,A). Therefore the graph permutation on G/O(I_n,2) is outside the 2-closure and the 3-closure for every n at least 3.

## 4. The induced permutations are genuinely outer

Both coset actions above are faithful: G is simple for n at least 3 and the displayed H is proper, so its core is trivial. The automorphism α is outer, since it interchanges point and hyperplane parabolics, whereas an inner automorphism sends a point stabilizer to another point stabilizer. If the permutation induced by α on either faithful coset action were induced by an element a of G, conjugation on the faithful image of G would give α=Inn(a), a contradiction.

Thus these candidates meet the properness and outer-permutation requirements of Binary Lemma B but fail its orbit-interpolation requirement.

## 5. Compressed proof spine and remaining local gap

L1 (double-coset necessity): triple interpolation implies α(x) in HxH for every x.

L2 (multi-block support): for H=GL_d(2) wr Sym(m), m at least 3, the element I+N has m+2 nonzero blocks while its inverse transpose has m+3.

L3 (orthogonal reciprocal spectrum): for H=O(I_n,2), the explicitly congruent form A has characteristic polynomial t^3+t+1 times (t+1)^{n-3}, while A^{-1} has the distinct reciprocal polynomial.

L4 (closure consequence): L1+L2 and L1+L3 imply that both graph permutations move pair orbitals and lie outside G^(3).

L5 (exactly one remaining C2 theorem-level gap): for n=2d and H=GL_d(2) wr Sym(2), decide whether duality preserves all triple orbits on unordered two-summand decompositions. This is the only equal-block decomposition case not decided by L2.

Dependencies: L2→L1→L4 and L3→L1→L4. In the root assembly, the certified rank-one, projective-outer, and central-vector theorems remain unchanged. The present result does not prove residual exclusion R; it removes two natural uniform choices for H and narrows the C2 construction branch to L5.

## Self-check

The block-support invariant is unchanged by both sides of the H-double action because block-monomial multiplication introduces no sums of distinct source blocks. The inverse formula uses N^3=0 and remains valid for every d and every m at least 3. The matrices C and S are invertible and satisfy C^T C=S. Multiplication by the common nonzero factor (t+1)^{n-3} cannot make the two reciprocal cubic factors equal in F_2[t]. Repeated-coordinate triples justify the implication from a moved pair orbital to failure of 3-closure. No claim about total 3-closure or nonclosure of any binary group is inferred from these candidate eliminations.
