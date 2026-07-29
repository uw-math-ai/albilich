# A conceptual proof of the PSL_2(19) Perkel intersection array

## Theorem

Let G=PSL_2(19), and let Ω be either G-conjugacy class of 57 subgroups isomorphic to A_5. Define a graph Γ on Ω by joining distinct K,L when |K∩L|=10. Then Γ is distance-regular with intersection array {6,5,2;1,1,3}.

This proves condition C1 without the unreproducible enumeration in art_researcher_psl219_repaired_certificate_cas_rev138. The argument applies separately to both A_5 classes.

## 1. Torus normalizers and incidence counts

Fix H∈Ω. We use D_{2m} for a dihedral group of order 2m. Since |G|=3420, the standard split/nonsplit torus calculation in PSL_2(19) gives

- |N_G(P)|=20 for P≅C_5: P lies in a nonsplit torus C_10 with normalizer D_20;
- |N_G(P)|=18 for P≅C_3: P lies in the split torus C_9 with normalizer D_18;
- |C_G(t)|=20 for an involution t: because 19≡3 mod 4, t is the central involution of a nonsplit-torus normalizer D_20.

There is one G-class of each of these prime-order subgroups. Hence G has respectively 171 subgroups C_5, 190 subgroups C_3, and 171 involution subgroups. An A_5 contains respectively 6, 10, and 15 such subgroups. Double-counting pairs (P,K) with P≤K∈Ω therefore shows that a fixed C_5, C_3, or C_2 lies in respectively

57·6/171=2, 57·10/190=3, 57·15/171=5

members of Ω.

We also need three small normalizer facts. For P≅C_5, N_G(P)=D_20 contains two subgroups D_10 containing P. Each is normalized by D_20 and has no larger normalizer because P is characteristic in it. Thus the D_10 subgroups form two G-classes of size 171. The six D_10 subgroups of H are H-conjugate and hence lie in one of these classes.

For P≅C_3, each D_6=N_H(P) is self-normalizing in N_G(P)=D_18: writing D_18=⟨r,s | r^9=s^2=1, srs=r^{-1}⟩, the normalizer of ⟨r^3,s⟩ is that subgroup itself. Thus the relevant D_6 class has size 3420/6=570.

Finally, N_G(V_4)=A_4 and N_G(A_4)=A_4. One way to see this using the source-free tame-subgroup lemma already proved in art_researcher_prime_field_a1_extension_except19_rev116 is that a proper 19-prime overgroup is cyclic, dihedral, A_4, S_4, or A_5. The normalizer of V_4 contains A_4; S_4 is impossible because 24 does not divide 3420, and A_5 does not normalize one of its five V_4 subgroups. Hence the normalizer is A_4. The assertion for A_4 follows. Consequently G has 285 A_4 subgroups and 285 V_4 subgroups.

## 2. The rank-four orbit decomposition

The class of D_10 subgroups occurring in H has size 171. Incidence counting gives

57·6/171=2

members of Ω through each such D_10. Therefore every one of the six D_10 subgroups of H determines a unique second vertex K. These six vertices are distinct, and H∩K is exactly D_10 because D_10 is maximal in A_5. Denote this H-orbit by O_1; it has size 6 and is precisely Γ(H).

Each C_3≤H lies in two further Ω-members. No D_6 can lie in two Ω-members, since the number of incidences is 57·10=570, equal to the total number of D_6 subgroups. Nor can an A_4 lie in two Ω-members, since 57·5=285 is the total number of A_4 subgroups. Hence the two further A_5 subgroups through each C_3 intersect H exactly in that C_3. Distinct C_3 subgroups give distinct vertices: any subgroup of A_5 properly containing two C_3 subgroups contains an A_4 or is A_5. We obtain one H-orbit O_3 of size 20, with stabilizer C_3.

It remains to account for involutions. A fixed involution of H lies in four Ω-members other than H. In A_5 every involution lies in exactly two of its six D_10 subgroups, so two of those four vertices already belong to O_1. This leaves 15·2=30 incidences with vertices outside {H}∪O_1. Such a vertex cannot share two involutions with H unless their generated dihedral subgroup is V_4, D_6, or D_10. A V_4 or D_6 lies in a unique Ω-member by the preceding normalizer counts, while the D_10 case is already O_1. Thus the 30 incidences give 30 distinct vertices, each intersecting H in C_2. They form one H-orbit O_2 of size 30.

All 57 vertices have now been accounted for:

Ω={H} disjoint union O_1 disjoint union O_2 disjoint union O_3,

with sizes 1,6,30,20. In particular, the permutation action has rank four.

## 3. Local 2-transitivity and the quotient matrix

The action of H≅A_5 on O_1 is its action on the six Sylow-5 normalizers. Under A_5≅PSL_2(5), this is the natural 2-transitive action on P^1(F_5). Hence the graph induced on O_1 is either complete or empty. It cannot be complete: then {H}∪O_1 would be a K_7 component because every vertex already has all six neighbors there, contradicting vertex-transitivity on 57 vertices. Thus Γ is triangle-free.

For i,j∈{0,1,2,3}, let q_ij be the number of neighbors in O_j of a fixed vertex in O_i, where O_0={H}. Undirectedness gives |O_i|q_ij=|O_j|q_ji. We have

q_10=1, q_11=0, q_12+q_13=5.

The balance identities 6q_12=30q_21 and 6q_13=20q_31 force q_13=q_31=0 and q_12=5, q_21=1. Hence q_22+q_23=5. Balancing O_2 against O_3 gives

30q_23=20q_32,

so q_23 is even. The value q_23=0 is impossible: then the component containing H would have exactly 1+6+30=37 vertices, whereas equal component sizes in a vertex-transitive 57-vertex graph must divide 57. Therefore q_23 is 2 or 4.

If q_23=2, the quotient matrix is

Q=[[0,6,0,0],[1,0,5,0],[0,1,3,2],[0,0,3,3]],

which is the desired intersection matrix. It remains only to exclude q_23=4. In that case balancing and row sums give

Q_alt=[[0,6,0,0],[1,0,5,0],[0,1,1,4],[0,0,6,0]].

## 4. The Galois-multiplicity exclusion of Q_alt

Let π be the permutation character of G on Ω. Its rank is

⟨π,π⟩=4.

The trivial constituent has multiplicity one, and the only way the remaining multiplicity squares can sum to 3 is as 1+1+1. Thus CΩ is a multiplicity-free sum of four irreducible G-modules. Every G-invariant adjacency operator consequently has at most four eigenvalues. The equitable rank-four quotient supplies four distinct eigenvalues, so these are all eigenvalues of Γ.

For Q_alt one computes

det(tI-Q_alt)=(t-6)(t^3+5t^2-5t-24).

The cubic has no rational root among the divisors of 24, hence is irreducible over Q. Its three roots are therefore Galois conjugate. Since the adjacency matrix has integer entries, these three roots must occur with equal algebraic multiplicity, say m. The graph is connected: the already established edges connect H, O_1, and O_2, giving a component with at least 37 vertices, while a component size in a vertex-transitive graph divides 57. Hence the eigenvalue 6 has multiplicity one. We would obtain

57=1+3m,

which is impossible. Therefore Q_alt cannot occur, and q_23=2.

It follows that relative to H the neighbor-count rows are

(0,6,0,0), (1,0,5,0), (0,1,3,2), (0,0,3,3).

Thus O_1,O_2,O_3 are exactly the distance layers, and Γ has intersection array {6,5,2;1,1,3}. Vertex-transitivity makes the same array valid at every root. This proves the theorem.

## 5. Assembly into the PSL_2(19) route

The proof applies separately to both degree-57 A_5 classes. The exact source interfaces in art_researcher_psl219_source_coupling_invariant_rev142 now apply without any computational premise: Coolsaet–Degraer identify every distance-regular graph with this array as the Perkel graph, and Alfuraidan–Hall state that the Perkel graph has full automorphism group PSL_2(19). Since G already acts faithfully and adjacency-preservingly, each degree-57 action is 2-closed and therefore 3-closed.

The local subdirect-product lemma in that same dossier couples the two classes because a point stabilizer A_5 of order 60 cannot be transitive on 57 points; it also handles repeated copies. The scalar-fiber and mixed-constituent arguments in art_researcher_prime_field_a1_extension_except19_rev116 cover every remaining proper-subgroup pair. The verified two-orbit reduction then implies that PSL_2(19) is totally 3-closed.

Accordingly, neither the 532-coordinate fingerprint nor conditions C2–C5* are needed on the shortest route. The old finite report is corroborative only.

## Proof spine

1. Torus and small-subgroup normalizers imply H-orbit sizes 1,6,30,20.
2. Local 2-transitivity and balance reduce C1 to two quotient matrices.
3. Rank-four multiplicity-freeness and Galois multiplicities exclude the false matrix.
4. The resulting intersection array, the manifest-listed Perkel source interface, constituent coupling, and the two-orbit reduction imply total 3-closure.

## Self-check

The proof treats both A_5 classes, uses subgroup counts rather than unexposed computation, and distinguishes D_10 of order 10 from D_20 of order 20. The uniqueness assertions for D_6, V_4, and A_4 are justified by normalizers and incidence counts. The Galois argument uses connectedness and multiplicity-freeness explicitly. The proof establishes only the PSL_2(19) target and does not claim completion of the global Lie-type classification. No verification status is asserted.
