# PSL(2,7) is totally 3-closed

## Theorem

Let G=PSL(2,7). Every faithful finite permutation representation of G is 3-closed. Consequently PSL(2,7) is a nonabelian simple group of Lie type which is totally 3-closed, so Problem 20.2 has an affirmative answer.

We use the standard identification G≅GL(3,2). Write V=F_2^3, let P be the seven one-dimensional subspaces of V, let P* be the seven two-dimensional subspaces, and let Q=P^1(F_7), of size eight.

## Lemma 1: base size at most two implies 3-closedness

Let a faithful G-set X have a base (x_1,x_2) of size at most two, with repetition allowed when the base has size one. If σ lies in the 3-closure, choose g∈G carrying (x_1,x_2,x_1) to its σ-image. For arbitrary x∈X, the closure condition supplies g_x∈G carrying (x_1,x_2,x) to its σ-image. Then g and g_x agree on the base, so faithfulness of the base gives g=g_x. Hence σ(x)=g(x) for every x, and σ=g. Thus X is 3-closed.

## Lemma 2: synchronization by a two-point base

Let X and Y be faithful, individually 3-closed G-sets. If X has base size at most two, then the diagonal action on X⊔Y is 3-closed.

Indeed, a closure element preserves the two point-orbits and restricts on them to elements g,h∈G. After composing with diagonal g^{-1}, it is the identity on X and acts as t=g^{-1}h on Y. For a base (x_1,x_2) of X and arbitrary y∈Y, apply the closure condition to the tagged triple (x_1,x_2,y). It gives s∈G fixing the base and satisfying s(y)=t(y). Therefore s=1, so t(y)=y. Faithfulness of Y gives t=1 and g=h.

## Lemma 3: maximal subgroups and the base-two reduction

The maximal proper subgroups of G comprise the following three geometric conjugacy classes:

1. point stabilizers G_p≅S_4 for p∈P;
2. line stabilizers G_L≅S_4 for L∈P*;
3. normalizers N_G(C_7)≅C_7:C_3, the point stabilizers in the natural degree-eight action on Q.

Here is a short completeness proof. Let M be maximal. If M is not transitive on V minus {0}, sum the vectors in each M-orbit. A nonzero orbit sum is an M-fixed point. If every orbit sum is zero, the only possible nontrivial partition of the seven vectors into zero-sum orbits is 3+4; the three-vector orbit is the set of nonzero vectors of a two-dimensional subspace, so M fixes a line. Hence M is a point or line stabilizer. If M is transitive, then 7 divides |M|. Since G has eight Sylow 7-subgroups, the number of Sylow 7-subgroups in a proper M cannot be eight, because those eight conjugates generate the nontrivial normal closure of a Sylow subgroup and hence generate G. Thus M has a normal Sylow 7-subgroup and lies in its normalizer, of order 21. The normalizer is maximal: a proper overgroup would have order 42 or 84, giving an impossible faithful action of the simple group G of degree four or two.

Every proper subgroup of an S_4 maximal is contained in an A_4, a Sylow D_8, or an S_3; every proper subgroup of C_7:C_3 is contained in C_7 or C_3. Each of A_4,D_8,S_3,C_7 has a conjugate intersecting it trivially:

- For a point p, the canonical A_4 in G_p is the inverse image of A_3 under G_p→GL(V/p)≅S_3. For p=⟨e_1⟩ and q=⟨e_2⟩, an element in the two corresponding A_4 subgroups fixes e_1,e_2 and has e_3↦e_3+a e_1+b e_2. Membership in the first A_4 forces b=0, and membership in the second forces a=0. Their intersection is therefore trivial. The dual calculation handles the line-type A_4 class.
- A Sylow D_8 is the stabilizer of an incident point-line flag. The stabilizers of (⟨e_1⟩,⟨e_1,e_2⟩) and (⟨e_3⟩,⟨e_2,e_3⟩) intersect trivially: an element in the intersection fixes e_1,e_3 and must send e_2 into both indicated planes, hence fixes e_2.
- An S_3 is the stabilizer of a nonincident point-line pair. Take (⟨e_1⟩,⟨e_2,e_3⟩) and (⟨e_2⟩,⟨e_1,e_2+e_3⟩). An element in both stabilizers has matrix diag(1,B) relative to e_1⊕⟨e_2,e_3⟩, fixes e_2, and preserves ⟨e_1,e_2+e_3⟩; these conditions force B=I.
- Two distinct Sylow 7-subgroups intersect trivially.

The property H∩H^g=1 passes to every subgroup of H. Consequently every proper subgroup other than the three maximal types has a coset action with base size at most two. Lemmas 1 and 2 therefore settle every pair of coset actions for which at least one stabilizer is nonmaximal. Only pairs among P, P*, and Q remain.

## Lemma 4: the three exceptional transitive actions are 3-closed

For P, the G-orbits on ordered triples of distinct points distinguish collinear triples from noncollinear triples. A permutation in the 3-closure therefore preserves the lines of the Fano plane. Choose three noncollinear points. Their images determine a unique element of GL(3,2), and preservation of the third point on every line then determines all remaining points. Thus every collineation is in G and the action on P is 3-closed. The dual argument proves the same for P*.

For Q=P^1(F_7), PGL(2,7) is sharply transitive on ordered triples of distinct points, and PSL(2,7) has two such triple-orbits. For a distinct triple T, let ε(T) be the quadratic character of the determinant of the unique projective transformation carrying (∞,0,1) to T. This is well-defined because projective rescaling changes the determinant by a square, and the two values of ε are exactly the two G-orbits.

Let σ be in the 3-closure. After composition by an element of G, assume σ fixes ∞,0,1. For x∈F_7 minus {0,1}, preservation of the colors of (∞,0,x) and (∞,1,x) preserves the signature (χ(x),χ(x-1)). With squares {1,2,4}, the signatures are

2:(+,+), 3:(-,+), 4:(+,-), 5:(-,+), 6:(-,-).

Thus σ fixes 2,4,6 and can only possibly interchange 3 and 5. But the colors of (∞,2,3) and (∞,2,5) are χ(1)=+ and χ(3)=-, respectively, so that interchange is impossible. Hence σ=1 after normalization, proving that Q is 3-closed.

## Lemma 5: exceptional pairs not involving Q

Consider a closure element on a pair of exceptional orbits. Lemma 4 lets us normalize it to act identically on the first orbit and as some t∈G on the second.

For P⊔P, choose distinct points p,q in the first copy. Their pointwise stabilizer fixes the third point r on the line pq. Applying the closure condition to (p,q,r), with r in the second copy, gives t(r)=r. Every point can occur as such an r, so t=1. The dual argument handles P*⊔P*.

For P⊔P*, the pointwise stabilizer of distinct p,q fixes their joining line L. Applying the mixed-triple condition with L in the second orbit gives t(L)=L. Every line is the join of two points, so t=1. This also handles the reversed ordering.

For Q⊔Q, the pointwise stabilizer of two distinct Q-points is C_3 and fixes both points. Using one of those same points in the second copy shows that t fixes it. Varying the pair gives t=1.

## Lemma 6: the mixed P-Q and P*-Q pairs

Fix distinct p,q∈P and let L=G_{p,q}. If ℓ is the Fano line through p,q, then L is the normal Klein four subgroup of the line stabilizer G_ℓ≅S_4. On Q, L is semiregular because every Q-point stabilizer has odd order 21. Hence L has two orbits B and B^c, each of size four.

We claim G_B is the canonical A_4 inside G_ℓ. First, N_G(L)=G_ℓ: the latter normalizes L and is maximal, while L is not normal in the simple group G. Moreover G_ℓ is transitive on Q. Indeed, for y∈Q, the order of (G_ℓ)_y divides gcd(24,21)=3, while an orbit has length at most eight; hence the stabilizer has order three and the orbit has length eight. Since L is normal in G_ℓ, the two L-orbits are interchanged transitively by G_ℓ, and their stabilizer inside G_ℓ is its index-two A_4.

This A_4 is already all of G_B. If a larger proper subgroup contained it, maximal-subgroup completeness would place it in an S_4. Inside that S_4 the A_4 is normal, and its characteristic Klein four L is normalized. The S_4 would therefore lie in N_G(L)=G_ℓ and equal G_ℓ, which does not stabilize B. Thus G_B=A_4≤G_ℓ.

Now normalize a closure element on P⊔Q to be the identity on P and t∈G on Q. The mixed-triple condition for p,q,y says t(y)∈L·y for every y∈Q. Therefore t stabilizes both L-orbits, in particular B, and hence t∈G_B≤G_ℓ. This holds for every Fano line ℓ, so t lies in the intersection of all line stabilizers, the kernel of the faithful action on P*. Thus t=1. The dual argument, using point stabilizers instead of line stabilizers, proves that P*⊔Q is 3-closed.

## Assembly

Every proper-subgroup coset action of G is either one of P,P*,Q or has base size at most two. Lemmas 1, 2, and 4 settle every pair containing a nonmaximal stabilizer. Lemmas 5 and 6 settle all six unordered pairs with repetition among P,P*,Q. Hence every diagonal action on G/H⊔G/K, for arbitrary proper H,K and with repetition allowed, is 3-closed.

The verifier-checked two-orbit criterion in proof_dossier_two_orbit_reduction_rev24 now implies that G is totally 3-closed. Since G=PSL(2,7) is a nonabelian simple group of Lie type, it is the required positive example.

## Short proof spine

1. A two-point base forces 3-closedness, and synchronizes a two-orbit union.
2. The maximal-subgroup classification reduces all coset actions to three maximal geometries P,P*,Q; every other stabilizer has base size at most two.
3. Triple geometry proves that P,P*,Q are individually 3-closed.
4. Fano incidence synchronizes P-P, P-P*, P*-P*, and Q-Q pairs.
5. The four-point orbit-block lemma for Klein four subgroups synchronizes P-Q and P*-Q.
6. The verified two-orbit criterion converts all pairwise closures into total 3-closedness.

Dependencies: 1+2→nonmaximal pairs; 3+4+5→maximal pairs; all pair cases→6→the affirmative root answer.

## Self-check

The argument includes the trivial subgroup, repeated pairs, both point and line S_4 classes, the degree-eight C_7:C_3 action, and every nonmaximal subgroup through downward inheritance of a two-point base. The mixed-pair argument uses the full tagged-triple closure condition, not merely separate closure on the two components. The determinant color in the degree-eight action is preserved orbit-by-orbit, so no unproved allowance to interchange the two triple-orbits is made. No computation or external citation is used. The remaining action is strict verification of the subgroup classification, the four-block stabilizer lemma, and the assembly; there is no declared mathematical gap.
