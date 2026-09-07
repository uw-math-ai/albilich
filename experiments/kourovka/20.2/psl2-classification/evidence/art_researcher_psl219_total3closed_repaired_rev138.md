# PSL_2(19) is totally 3-closed

## Corrected local-rigidity lemma

Let G=PSL_2(19), let H be an A_5 subgroup, let Omega=H^G, and let Gamma join K,L in Omega when |K∩L|=10. Fix v in Omega, let L_i be the distance layers around v, and put Delta=Gamma[L_3]. For y in L_1 and x in L_2 define
F_y={z in L_3: there exists x in L_2 with y~x~z},
Q_x=Gamma(x)∩L_3,
and M_y={Q_x:x~y}.

The exact report art_researcher_psl219_repaired_certificate_cas_rev138 establishes:

(C1) Gamma has intersection array {6,5,2;1,1,3}, with layer sizes 1,6,30,20.
(C2) Delta is the dodecahedron.
(C3*) The six F_y are pairwise distinct and invariant under the antipode iota of Delta.
(C4) The thirty two-sets Q_x are pairwise distinct.
(C5*) For the displayed y=11, iota(M_y) is not M_y.

These conditions imply Aut(Gamma)=G. Put A=Aut(Gamma). Since G≤A is vertex-transitive, it suffices to determine A_v. Restriction to L_3 gives rho:A_v→Aut(Delta). It is injective: if rho(a)=1, then F_{a(y)}=a(F_y)=F_y, so (C3*) fixes L_1 pointwise; then Q_{a(x)}=a(Q_x)=Q_x, so (C4) fixes L_2 pointwise. Thus a fixes every vertex.

Aut(Delta)=A_5×<iota> has order 120. The subgroup G_v=H is A_5 and acts faithfully on L_3, hence its image is the rotation subgroup. If rho(a)=iota, then iota(F_y)=F_y and distinctness again force a to fix L_1 pointwise. Therefore a permutes the five L_2-neighbors of y=11 and Q_{a(x)}=iota(Q_x), forcing iota(M_11)=M_11, contrary to (C5*). Hence iota is not in rho(A_v). Since rho(A_v) contains the rotation subgroup, it contains no element of the other coset. Thus |A_v|=60 and |A|=57·60=3420=|G|. Because G≤A, Aut(Gamma)=G.

The 2-closure of the action on Omega preserves every orbital graph, so
G≤G^(3)≤G^(2)≤Aut(Gamma)=G.
Thus this A_5-coset action is 3-closed.

## The second A_5 class and mixed synchronization

The exact report also checks that the projectivity D:x↦2x normalizes G, is outside G, and exchanges the two G-conjugacy classes of A_5 subgroups. It maps the first orbital graph isomorphically to the second. Hence the second degree-57 action is also 2-closed and 3-closed.

It remains to synchronize one constituent Y_+ from the first class with one constituent Y_- from the second. Let pi lie in the 3-closure of the diagonal action on Y_+ disjoint union Y_-. Its restrictions belong to G because both individual actions are 3-closed. Multiplying pi by a diagonal element of G, assume that pi fixes Y_+ pointwise and acts on Y_- as some h in G.

For a,b in Y_+ and z in Y_-, preservation of the orbit of (a,b,z) gives
h(z) in (G_a∩G_b)z.
The exact cross-class computation forms the orbit-label vector of z under every one of the 532 distinct groups G_a∩G_b and finds 57 distinct vectors. Therefore the displayed containment for every a,b forces h(z)=z for every z in Y_-. The action is faithful, so h=1. Thus Y_+ disjoint union Y_- is 3-closed. Repeated copies of either class synchronize by corresponding-point triples.

## Arbitrary faithful actions

The constituent analysis in art_researcher_prime_field_a1_extension_except19_rev116 handles every other proper subgroup at p=19. Every coset action outside the two A_5 classes and the scalar-fiber actions X_1,X_3,X_9 has a two-point base. All pairs X_d disjoint union X_e are 3-closed by scalar-fiber rigidity. A pair consisting of an A_5 action and X_1 has a two-point base because A_5 has no element of order 19. For X_3 and X_9, two A_5 vertices can be chosen whose stabilizer intersection is a prescribed C_3; once the A_5 constituent is fixed, the resulting mixed triple fixes the scalar-fiber point. The same argument transfers to the second A_5 class through D.

Hence every pair of nontrivial transitive constituents is 3-closed. The verified two-orbit reduction claim_import_two_orbit_reduction now implies that every faithful finite permutation representation of G is 3-closed. Therefore PSL_2(19) is totally 3-closed.

## Proof spine and self-check

1. Exact rooted certificate implies Aut(Gamma)=G for the first A_5 class.
2. The outer projectivity D transfers the result to the second A_5 class.
3. The 532-intersection fingerprint synchronizes the two different A_5 constituents.
4. The prior scalar-fiber and two-point-base arguments cover all other constituent pairs.
5. The verified two-orbit reduction gives total 3-closure.

The old opposite-face condition is explicitly rejected. Both A_5 classes and their mixed pair are covered. Faithfulness follows from simplicity of G and properness of every stabilizer. The closure inclusions have the correct direction. The computation proves only statements about this one finite group. No verification status is asserted here.
