# Canonical source-certified proof that PSL_2(11) is totally 3-closed

## Theorem

Let G=PSL_2(11). Every faithful finite G-set has 3-closure equal to G.

## Certified external interfaces

Jones, “Counting conjugacy classes of subgroups of PSL_2(p),” arXiv:2411.02219v1, Section 2, Lemmas 2.1–2.3 and Table 1, proves, after specialization to p=11, that the fourteen nonidentity proper-subgroup G-conjugacy classes are

C_2, C_3, C_6, V_4, S_3^+, S_3^-, D_12, C_5, D_10, C_11, C_11:C_5, A_4, A_5^+, A_5^-.

Here Jones writes D_d for the dihedral group of order 2d. Thus, including the identity subgroup, the stabilizer orders are

1,2,3,4,5,6,6,6,10,11,12,12,55,60,60.

Jones's Lemma 2.2 gives two classes precisely for D_3=S_3 and A_5 in this specialization, while Lemma 2.3 makes the A_5 subgroups self-normalizing.

Martín–Singerman, “The geometry behind Galois' final theorem,” European J. Combin. 33 (2012), Section 10, Theorem 3(a), identifies the two eleven-member A_5 conjugacy classes as the point and block sides of an order-3 biplane. Their Section 9 contains the preceding combinatorial construction; the theorem itself is in Section 10. Alavi–Daneshkhah–Praeger, “Symmetries of biplanes,” arXiv:2004.04535, Section 3, Line 2, states that the unique 2-(11,5,2) biplane is the Hadamard design and that its full automorphism group is PSL_2(11). Self-normalization identifies these conjugation actions with the two degree-11 coset actions.

## Lemma 1: element classes needed for the base calculation

The order of G is 660. Matrix centralizers in SL_2(11), modulo {±I}, give the following G-class sizes:

- order 2: one class of size 55;
- order 3: one class of size 110;
- order 5: two classes, each of size 132;
- order 6: one class of size 110;
- order 11: two classes, each of size 60.

Indeed, the split and nonsplit maximal tori have orders 5 and 6. A noninvolutory semisimple element has its torus as centralizer. A projective involution has the full nonsplit-torus normalizer, of order 12, as centralizer. A nonidentity unipotent element has centralizer its Sylow 11-subgroup. The complement C_5 in N_G(C_11)=C_11:C_5 has two length-five orbits on C_11 minus {1}, producing the two order-11 classes. The displayed classes account for

1+55+110+132+132+110+60+60=660,

so the census is exhaustive. In particular, every C_11 contains five elements from each order-11 class.

## Lemma 2: bases imply closure

If a faithful permutation group L has a base of size b, then it is (b+1)-closed. Let y lie in its (b+1)-closure. Repeated coordinates show that y preserves L-orbits on b-tuples, so after multiplication by an element of L we may assume that y fixes a chosen base pointwise. For every point z, preservation of the orbit of the tuple consisting of the base followed by z supplies an element of L fixing the base and sending z to z^y. That element is the identity, so y fixes every z.

## Lemma 3: the twelve small-stabilizer actions are 3-closed

For H≤G and uniformly distributed g in G,

E(|H∩H^g|-1)=sum_C |H∩C|^2/|C|,

where C runs over the nonidentity G-classes. This follows by summing, for each x in H minus {1}, the probability that x belongs to H^g. If the expectation is below one, some conjugate of H intersects H trivially, giving a two-point base for H\G.

Using Lemma 1 and the elementary element distributions inside the subgroup types, the relevant upper bounds are

C_2: 1/55;
C_3: 4/110;
V_4: 9/55;
C_5: 16/132;
C_6: 1/55+4/110+4/110;
S_3: 9/55+4/110;
D_10: 25/55+16/132;
C_11: 25/60+25/60=5/6;
A_4: 9/55+64/110;
D_12: 49/55+4/110+4/110=53/55.

Every number is below one. The regular action has a one-point base. Lemma 2 therefore proves 3-closedness of the coset actions for the identity, C_2, C_3, V_4, C_5, C_6, both S_3 classes, D_10, C_11, A_4, and D_12.

## Lemma 4: the two degree-11 actions are 3-closed

Let D be the certified symmetric 2-(11,5,2) biplane. On its point set let R consist of ordered triples of distinct points contained in a block. This is a union of G-orbits, hence every element of the 3-closure preserves R.

Two distinct blocks of a symmetric 2-design meet in exactly two points, since its incidence matrix N satisfies NN^T=3I+2J. Thus a triple lies in at most one block. Suppose X is a five-subset every triple of which belongs to R, and let n_i count blocks meeting X in i points. Counting pairs, triples, incidences, and blocks gives

sum binom(i,2)n_i=20,  sum binom(i,3)n_i=10,  sum i n_i=25,  sum n_i=11.

If X were not a block, then i≤4. The first two equations yield n_3+4n_4=10 and n_2+3n_3+6n_4=20. Nonnegativity forces n_4=2, n_3=2, n_2=2, and then the incidence equation gives n_1=7. This would require at least thirteen blocks meeting X, a contradiction. Hence the blocks are exactly the five-cliques of R. Every element of the 3-closure therefore belongs to Aut(D)=G. Applying the same argument to the dual design proves the result for both A_5 classes.

## Lemma 5: the degree-12 action is 3-closed

The subgroup B=C_11:C_5 is the stabilizer of infinity in the projective-line action. On F_11 it consists of maps t↦ut+v with u a nonzero square. Orient the Paley tournament T by a→b when b-a is a square. A 3-closure element normalized to fix infinity preserves T because the two B-orbits on (infinity,a,b), with a≠b, are distinguished by the square class of b-a.

Translations and square multipliers give B≤Aut(T), of order 55. The out-neighborhood Q={1,3,4,5,9} of 0 induces a five-vertex tournament whose automorphism group is the regular C_5 of square multipliers. The restriction of Aut(T)_0 to Q is injective: the five in-neighbors 2,6,7,8,10 have distinct sets of in-arrows from Q, namely {1,4,9}, {1,3,5}, {3,4,9}, {3,4,5}, and {1,5,9}. Hence |Aut(T)_0|≤5 and |Aut(T)|≤55. Therefore Aut(T)=B, proving that the degree-12 action is 3-closed.

## Lemma 6: synchronization for nonfactorizing pairs

Let G be nonabelian simple and act faithfully and 3-closedly on transitive sets A and B. Restriction embeds the 3-closure C of the diagonal action on A disjoint union B into G×G. Its image D contains the diagonal subgroup. The kernels of both coordinate projections are normal under diagonal conjugation, so simplicity shows that D is either the diagonal subgroup or all of G×G. If both kernels are trivial, D is the graph of an automorphism containing every (g,g), hence is diagonal.

If D=G×G, then every (1,d) preserves all triple orbits. For a in A and b,b' in B, choose d with b^d=b'. Preservation of (a,b,b) supplies an element of G_a sending b to b'. Thus G_a is transitive on B; symmetrically G_b is transitive on A. For A=H\G and B=K\G this is equivalent to G=HK. Consequently every nonfactorizing pair synchronizes diagonally.

## Lemma 7: all arithmetically possible factorizing pairs synchronize

If G=HK, then |H∩K|=|H||K|/660 is an integer. Applying this to the certified order ledger leaves only the unordered order pairs

(11,60), (12,55), (55,60).

Accounting for the two order-12 and two order-60 classes gives six class pairs:

(C_11,A_5^+), (C_11,A_5^-), (A_4,C_11:C_5), (D_12,C_11:C_5), (C_11:C_5,A_5^+), (C_11:C_5,A_5^-).

For the first four pairs, normalize a closure element to be the identity on the constituent with stabilizer C_11, A_4, or D_12. That constituent has a two-point base a_1,a_2 by Lemma 3. Preservation of every mixed triple (a_1,a_2,b) forces the relative element on the other constituent to fix every b, so it is the identity.

For either remaining pair, normalize on the projective-line constituent. A Sylow 5-subgroup T of the stabilizer A_5 of an arbitrary point b fixes two projective points a_1,a_2: its eigenvalue ratio has order five and is fixed by the eleventh-power Frobenius. Their pointwise stabilizer in PSL_2(11) is the split torus of order five, hence T. Preservation of (a_1,a_2,b) supplies s∈T taking b to its relative image; since T≤G_b, that image equals b. Thus the relative element fixes every b. All six pairs synchronize.

## Assembly

Let Ω be any faithful finite G-set and let x lie in its 3-closure. Triples (ω,ω,ω) show that x preserves every G-orbit and fixes each global fixed point. Every nonfixed orbit is H\G with H proper, and its action is faithful because the core of H is a proper normal subgroup of the simple group G.

Lemmas 3–5 show that x restricts on each nonfixed constituent as a unique element of G. Lemma 6 synchronizes every nonfactorizing pair, and Lemma 7 synchronizes every remaining possible pair, including repetitions. Hence all constituent restrictions are induced by one common g∈G. Both x and g fix every fixed point, so x=g on Ω. Therefore Ω is 3-closed. Since Ω was arbitrary, PSL_2(11) is totally 3-closed.

## Relation to the former computation debt

The exhaustive 15-action/120-pair/36-mixed-triple certificate is not a premise of this proof. The certified subgroup ledger, the base argument, the biplane and Paley relations, and the synchronization lemmas replace every finite assertion demanded by that route. The old raw-transcript obligation is therefore bypassed mathematically rather than asserted to have been fulfilled by an unavailable computation.

## Root proof spine and single unsupported sentence

The shortest present classification spine is:

1. the integrated two-orbit theorem reduces total 3-closure of a simple group to its two-constituent coset actions;
2. the integrated PSL_2(7) certificate proves the first survivor;
3. the proof above supplies the verifier-ready second survivor PSL_2(11);
4. the integrated projective outer-witness theorem excludes PSL_n(p^f) whenever f>1, and for n≥3 also whenever gcd(n,p^f-1)>1;
5. the following sentence is unsupported and is the sole remaining theorem-level classification gap: “Every finite nonabelian simple Lie-type group other than PSL_2(7) and PSL_2(11) which is not covered by the projective outer-witness theorem has a faithful permutation action whose 3-closure properly contains the group; this includes prime-field PSL_2(p) for p≥13, residual prime-field type A with gcd(n,p-1)=1, every non-A classical, exceptional, twisted, Suzuki and Ree family, and all exceptional-isomorphism bookkeeping.”

Once Step 5 is proved and the present PSL_2(11) inference passes strict verification, the two positive results and all negative certificates assemble directly into the root if-and-only-if classification.

## Self-check

The argument includes the identity subgroup, both S_3 and both A_5 classes, repeated constituents, fixed points, and all stabilizer-order pairs. The expectation uses G-conjugacy classes rather than abstract subgroup types. The biplane is reconstructed from a ternary relation. The Paley argument preserves orientation. The subdirect-product argument uses faithful constituent actions and simplicity. The order calculation is used only to over-list possible factorizations, so it does not assume that any listed factorization exists. No CAS output is used as a theorem premise, and no verification status is claimed.
