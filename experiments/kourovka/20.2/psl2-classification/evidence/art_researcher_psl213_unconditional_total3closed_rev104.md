# Unconditional candidate proof that PSL_2(13) is totally 3-closed

## Theorem

Let S=PSL_2(13). Every faithful finite permutation representation of S is 3-closed.

## 1. Certified maximal-subgroup interface

The source-adaptation dossier art_researcher_psl213_dickson_source_adaptation_rev98 certifies the following local specialization of Dickson's subgroup theorem:

(M) Every maximal proper subgroup of S is of type B=13:6, D_12, D_14, or A_4, where D_m denotes a dihedral group of order m.

The certification uses Guralnick--Zieve, Appendix A, Theorem A.1 (paper_id DOI 10.4007/annals.2010.172.1315; theorem_id Appendix A, Theorem A.1; arXiv id 0707.1835), independently checked against Buekenhout--De Saedeleer--Leemans, Table 8. At q=13, the Borel and torus-normalizer orders are 78, 12, and 14. The S_4 and A_5 cases are excluded by the applicable congruence clauses (also by divisibility of their orders into |S|=1092), and there is no proper subfield subgroup. Thus (M) is exactly the source-certified input needed below.

## 2. The two-point-base mechanism

If a faithful action of a group G has a base (a,b), then it is 3-closed. Indeed, for pi in the 3-closure, the orbit of (a,b,a) supplies g in G agreeing with pi on a and b. After replacing pi by g^{-1}pi, it fixes a and b. For every x, preservation of the orbit of (a,b,x) supplies h in G fixing a and b and satisfying h(x)=pi(x). Since (a,b) is a base, h=1, so pi fixes every x.

We now show that almost every coset action of S has such a base.

For D_12, use its action as the stabilizer of an unordered pair of rational projective points. The stabilizers of {infinity,0} and {infinity,1} intersect trivially: an element stabilizing both pairs fixes their common point infinity and then fixes 0 and 1.

For D_14, its cosets may be identified with the 78 Frobenius pairs {z,z^13} in P^1(F_13^2)\P^1(F_13). Fix K=D_14. Its six nonidentity rotations fix only the eigenline pair of its nonsplit torus. Each of its seven involutions is split because -1 is a square in F_13; after a projective change of coordinates it is z↦-z. Such an involution fixes exactly the six Frobenius pairs arising from the twelve nonzero trace-zero elements satisfying z^13=-z. Hence the union of fixed-point sets of nonidentity elements of K has size at most 1+7·6=43<78. Some Frobenius pair has trivial K-stabilizer, equivalently K has a conjugate meeting it trivially.

For K=A_4, an involution of S has centralizer D_12 and class size 91, while an element of order three has centralizer of order six and class size 182. For uniformly chosen g in S, the union bound gives

Pr(K∩K^g≠1) ≤ 3(3/91)+8(8/182)=41/91<1.

Thus some conjugate of every embedded A_4 meets it trivially. Consequently every subgroup contained in D_12, D_14, or A_4 has a two-point base.

Let P=C_13 be the unipotent radical of B=P:C_6. If H≤B and 13 does not divide |H|, coprime conjugacy of complements places H in a complement C_6, which lies in D_12; hence H has a two-point base. If 13 divides |H|, then P≤H and H is one of P, P:C_2, P:C_3, or B. The subgroup P has a two-point base because two distinct Sylow-13 subgroups intersect trivially. Therefore the only actions not already covered by the base argument have stabilizer B, P:C_2, or P:C_3.

## 3. Projective and fiber rigidity

The action on S/B is the degree-fourteen action on P^1(F_13). Normalize an element pi of its 3-closure to fix infinity. For distinct a,b in F_13, the S-orbit of (infinity,a,b) is determined by whether b-a is a square, so pi induces an automorphism of the Paley graph on F_13.

The neighbors of 0 are Q={1,3,4,9,10,12}, inducing the six-cycle

1--4--3--12--9--10--1.

The nonsquares 2,5,6,7,8,11 have respective, distinct neighborhoods in Q

{1,3,12}, {1,4,9}, {3,9,10}, {3,4,10}, {4,9,12}, {1,10,12}.

Thus an automorphism fixing 0 acts faithfully on the displayed cycle. In cyclic coordinates these six triples admit the six rotations but no reflection: the reflection i↦-i sends {0,2,3} to the absent set {0,3,4}. Hence the stabilizer of 0 has order at most six. The six square multipliers attain this bound, and translations then give the full graph automorphism group 13:6, exactly S_infinity. Therefore the projective action is 3-closed.

For E≤F_13^* containing -1, set Omega_E=(F_13^2\{0})/E. When |E|=4 and 6, the point stabilizers in S are respectively P:C_2 and P:C_3. Let pi lie in the 3-closure on Omega_E. Pair orbits determine whether two points lie above the same projective point, so pi induces a permutation f of P^1(F_13). Projecting lifted triple orbits shows f lies in the 3-closure of the projective action, hence f∈S. Normalize by f, so pi fixes every projective fiber setwise.

Identify a fiber with C=F_13^*/E. Exact preservation of the within-fiber pair orbitals forces pi to act on the fiber over x as multiplication by a coset c_x∈C. For two distinct projective points represented by v,w, the S-orbit of ([v],[w]) is determined by det(v,w)E. Therefore

c_x c_y=1 for every x≠y.

If |E|=4, then |C|=3; applying the equations to three distinct fibers yields c_x^2=1 and hence every c_x=1. If |E|=6, then |C|=2 and all c_x equal one common coset. The sole possible nonidentity permutation is the global deck involution tau([v])=[nu v] for a nonsquare nu. It does not preserve the orbit of

([e_1],[e_2],[e_1+e_2]).

Indeed, if A∈SL_2(13) carried this triple to its tau-image, then for d_i∈E one would have A e_1=nu d_1e_1, A e_2=nu d_2e_2, and A(e_1+e_2)=nu d_3(e_1+e_2). Linearity forces d_1=d_2=d_3=d, while det(A)=1 gives (nu d)^2=1. Thus nu d=±1, contradicting nu∉E. Both scalar-quotient actions are therefore 3-closed.

## 4. Synchronization of arbitrary constituents

Let Omega be any faithful finite S-set and let pi lie in its 3-closure. Constant triples show that pi preserves each transitive constituent setwise. Every nontrivial constituent is faithful because S is simple, and Sections 2--3 show that each is individually 3-closed. Hence the restriction of pi to each nontrivial constituent is induced by some element of S.

If one constituent has a two-point base (a,b), normalize pi to be the identity there. For any point x in another constituent, preservation of the mixed triple orbit containing (a,b,x) supplies an element of S fixing a and b and carrying x to pi(x). It is the identity, so all constituents synchronize.

It remains to consider an S-set all of whose nontrivial stabilizers are in {B,P:C_2,P:C_3}. Each constituent has its canonical S-equivariant projection to P^1(F_13). For two such constituents, the relation that two points have the same projective image is an S-invariant union of ordered-pair orbitals and is therefore preserved by pi. If the two restrictions of pi are induced by g_1,g_2∈S, preservation of this relation gives g_1(x)=g_2(x) for every projective point x. The projective action is faithful, so g_1=g_2. Repeating this comparison synchronizes all nontrivial constituents. Each fixed point is fixed individually because its constant triple is a singleton S-orbit. Thus pi is induced by one element of S on all of Omega.

Therefore every faithful finite action of PSL_2(13) is 3-closed.

## Short proof spine and root assembly

1. Source-certified Dickson specialization (M).
2. (M) plus conjugate-intersection estimates imply a two-point base for every stabilizer except B, P:C_2, and P:C_3.
3. Paley-graph and determinant-coset rigidity prove the three exceptional actions are 3-closed.
4. Mixed triples and the common projective quotient synchronize arbitrary repeated or nonisomorphic constituents.

The dependency chain 1→2→3→4 proves that PSL_2(13) is totally 3-closed. Combined with the integrated two-orbit reduction, this is a local verifier-ready proof candidate for claim_root_psl213_totally_3closed_rev94 and shows that the anticipated two-survivor list cannot be final if verification succeeds. The single remaining root-level theorem is now the residual-family classification with PSL_2(13) included in the survivor ledger: decide every other prime-field A_1 parameter, residual type A parameter, non-A classical family, exceptional or twisted family, and all exceptional isomorphisms.

## Self-check

The proof uses simplicity only to make every nontrivial constituent faithful. Every passage from a maximal subgroup to a subgroup preserves the exhibited two-point base. The D_14 count includes rotations and involutions; the A_4 estimate is uniform over all embedded A_4 subgroups. Both scalar quotients are treated separately, and the only surviving deck candidate is killed by an explicit ordered triple. Synchronization covers repeated constituents, nonisomorphic constituents, and fixed points. No verification or integration status is asserted here.
