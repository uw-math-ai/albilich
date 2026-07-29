# Prime-field A1 extension theorem away from p=19

## Theorem proved in this dossier

Let p be a prime. Then PSL_2(5) is not totally 3-closed. If p>=17 and p!=19, then PSL_2(p) is totally 3-closed.

For p=19, the proof reduces total 3-closure to one finite theorem: in the degree-57 action of PSL_2(19) on the cosets of an A_5 subgroup, the valency-six orbital graph has full automorphism group PSL_2(19). Thus the entire prime-field A1 branch, apart from the already integrated cases p=7,11,13, has one remaining finite obstruction.

## 1. A two-point base synchronizes every second constituent

Let S be a finite group acting faithfully and transitively on X, and suppose there are a,b in X with S_a intersect S_b equal to 1. Let Z be any other faithful S-set, including a repeated copy of X. The diagonal action of S on X disjoint union Z is 3-closed.

Indeed, let pi preserve every S-orbit on ordered triples. Constant triples show that pi preserves each named constituent. Since pi(a),pi(b) lie in the S-orbit of (a,b), multiplication by an element of S lets us assume pi(a)=a and pi(b)=b. For every y in X disjoint union Z, preservation of the orbit of (a,b,y) gives s_y in S with s_y(a,b,y)=(a,b,pi(y)). The first two coordinates force s_y in S_a intersect S_b=1, so pi(y)=y. This proves the assertion.

Consequently, for the two-constituent reduction, every pair containing a coset action with base size two is already settled.

## 2. Proper-subgroup dichotomy in PSL_2(p)

Put G=PSL_2(p), where p>=17, and m=(p-1)/2. Its order is p(p^2-1)/2.

### 2.1 Subgroups divisible by p

There are exactly p+1 Sylow p-subgroups of G, corresponding to the points of the projective line. If H<G and p divides |H|, then the number of Sylow p-subgroups of H is congruent to 1 modulo p and is at most p+1. It is therefore 1 or p+1. In the second case H contains every Sylow p-subgroup of G; in particular it contains the upper and lower unitriangular subgroups, which generate G. This contradicts H<G. Thus H has a unique Sylow p-subgroup and lies in its normalizer

B=U:C_m.

If H intersects U trivially, projection to B/U embeds H into the cyclic group C_m. In the affine model, a nontrivial p-prime cyclic subgroup has a second fixed point, so it lies in a split torus normalizer. Otherwise U<=H and

H=H_d:=U:C_d

for a divisor d of m.

### 2.2 Subgroups of order prime to p

We use the following source-free tame subgroup lemma.

Lemma. If L is a finite subgroup of PGL_2 over an algebraically closed field of characteristic not dividing |L|, then L is cyclic, dihedral, A_4, S_4, or A_5.

Proof. Every nonidentity element is semisimple and fixes exactly two projective points. A point stabilizer is cyclic: after moving the point to infinity, its translation kernel is a p-group and hence trivial in L. Let e_1,...,e_r be the orders of stabilizers of representatives of the L-orbits having nontrivial stabilizer. Counting pairs (x,l), where l!=1 fixes x, gives

sum_i |L|(1-1/e_i)=2(|L|-1).

Since every e_i>=2, this gives r<=3. If r=2, both stabilizers have order |L|, so L is cyclic. If r=3, ordering e_1<=e_2<=e_3 gives

1/e_1+1/e_2+1/e_3=1+2/|L|>1.

The possibilities are (2,2,n), (2,3,3), (2,3,4), and (2,3,5), giving orders 2n,12,24,60. The inertia groups at the three exceptional orbits generate L and have product one: deleting those orbits gives the connected free part of the quotient map, so a subgroup containing all inertia groups would define a disconnected intermediate quotient unless it were L. Hence L is a quotient of the corresponding spherical triangle group. The presentations

<x,y | x^2=y^2=(xy)^n=1>,
<x,y | x^2=y^3=(xy)^3=1>,
<x,y | x^2=y^3=(xy)^4=1>,
<x,y | x^2=y^3=(xy)^5=1>

have orders 2n,12,24,60 and are respectively dihedral, A_4, S_4, A_5. Equality of the orders makes the quotient maps isomorphisms. This proves the lemma.

Applying the lemma over the algebraic closure to a p-prime subgroup of G proves that every such subgroup has one of these five types. Cyclic and dihedral subgroups lie in a split or nonsplit torus normalizer.

Thus every proper H<G is either contained in a torus normalizer, is A_4, S_4, or A_5, or is one of the groups H_d.

## 3. Every subgroup outside the fiber family has a two-point base, except A_5 at p=19

### 3.1 Split torus normalizers

The split torus normalizer is the setwise stabilizer of an unordered pair of projective points. The stabilizers of {infinity,0} and {infinity,1} intersect trivially: a projectivity preserving both pairs fixes their common point and then fixes 0 and 1. These two normalizers are conjugate in G. Hence the split-normalizer action has a two-point base, and so does every subgroup contained in it.

### 3.2 Nonsplit torus normalizers

Let N be a nonsplit torus normalizer. It is dihedral of order p+1. The number of its conjugates is

N_0=p(p-1)/2.

Two distinct conjugates can share only involutions: every noninvolution in N lies in its cyclic torus, and its two eigenlines determine that torus uniquely.

Write p+1=2m'. If p is 1 modulo 4, N has m'=(p+1)/2 involutions. The total number of involutions of G is p(p+1)/2, so each involution belongs to (p-1)/2 conjugates of N. Hence the number of conjugates equal to N or sharing an involution with it is at most

1+(p+1)(p-3)/4 < p(p-1)/2.

If p is 3 modulo 4, N has (p+3)/2 involutions, the total number of involutions is p(p-1)/2, and each involution belongs to (p+3)/2 conjugates of N. The corresponding bound is

1+(p+3)(p+1)/4 < p(p-1)/2

for p>7. Thus some conjugate intersects N trivially. Every subgroup contained in a nonsplit torus normalizer consequently has a two-point base.

### 3.3 Exceptional subgroups

Let E be A_4, S_4, or A_5. If E intersect E^g is nontrivial, it contains a subgroup of prime order. For a G-conjugacy class C of prime-order subgroups, the probability over uniform g that a fixed P in C intersect E lies in E^g is |C intersect E|/|C|. Therefore the union bound for a nontrivial intersection is

sum_C |C intersect E|^2/|C|.

Every prime-order subgroup occurring here is semisimple, and its normalizer has order at most p+1. Hence every such class has at least

|G|/(p+1)=p(p-1)/2

members. The numbers of prime-order subgroups in A_4 are 3 of order two and 4 of order three; in S_4 they are 9 and 4; in A_5 they are 15,10,6 of orders two, three, five. Thus the respective union bounds have numerators

25, 97, 361.

For p>=17 the first two are strictly below p(p-1)/2. For A_5 the inequality holds for p>=29. Between 17 and 29, divisibility permits A_5 only at p=19. It follows that all exceptional subgroups have a two-point base for p>=17 except possibly A_5 in PSL_2(19).

The exception is genuine at the level of base size: |PSL_2(19):A_5|=57, whereas |A_5|=60, so the stabilizer A_5 cannot have a regular orbit on the other 56 points.

## 4. The fiber actions H_d are ternarily rigid in every pair

Let F=F_p, V=F^2, and for d|m let A_d be the unique subgroup of F^* of order 2d. Since -1 belongs to A_d, G acts faithfully on

X_d=(V minus {0})/A_d.

The stabilizer of [e_1] is exactly H_d=U:C_d, so this is the coset action G/H_d.

We prove that the diagonal action on X_d disjoint union X_e is 3-closed for every d,e|m.

First, dependence of two nonzero vectors is a union of exact G-orbits on ordered pairs, hence is preserved by every element pi of the 3-closure. Therefore pi induces a permutation f_d of the projective lines below X_d. Mixed dependent pairs show f_d=f_e; call the common permutation f.

The induced f preserves each G-orbit on ordered projective triples. The projective action of PSL_2(p) is 3-closed. Here is a proof. After fixing infinity, the two G-orbits on triples (infinity,x,y), x!=y, are distinguished by whether y-x is a square. Thus a permutation fixing infinity and preserving triple colors restricts to a permutation of F preserving the square/nonsquare color of every difference. The elementary prime-degree lemma says that a transitive permutation group of prime degree containing the translations is either 2-transitive or has the translation group normal and is contained in AGL_1(p). For completeness, the lemma follows by applying the permutation character to a Sylow p-cycle: if that Sylow subgroup is not normal, its nontrivial linear characters form one point-stabilizer orbit, which makes the nontrivial suborbit unique and the group 2-transitive; otherwise the regular Sylow subgroup is normal and conjugation embeds the stabilizer in F_p^*. The square-colored relation is not 2-transitive, so its color-preserving automorphisms are affine. Preservation of the color forces the multiplier to be a square. Such affine maps are exactly the stabilizer of infinity in PSL_2(p). Undoing the normalization gives f in PSL_2(p).

Multiply pi by the inverse of this common element of G. We may now suppose that pi fixes every projective line and acts only inside scalar fibers.

Fix a line L. For two points [a v],[b v] in the fiber over L, their exact G-orbit is determined by the ratio b/a modulo A_d. Hence pi acts on that fiber by multiplication by a constant c_{d,L} in F^*/A_d. For distinct lines L,M, the orbit of an independent pair is determined by det(v,w) modulo A_d. Preservation of this orbit gives

c_{d,L} c_{d,M}=1 in F^*/A_d.

Using three distinct lines shows that all c_{d,L} equal a common c_d and c_d^2=1. Finally take points over three distinct projective lines. If simultaneous multiplication by c_d preserved their exact G-orbit, an element of SL_2(p) would projectively fix all three lines and hence would be scalar. Its determinant is one, so the scalar is plus or minus one; because plus or minus one lies in A_d, this forces c_d to be trivial in F^*/A_d. Thus pi fixes X_d pointwise. The same argument fixes X_e.

Therefore every repeated or unrepeated pair X_d disjoint union X_e is 3-closed.

## 5. Assembly for p>=17, p!=19

Let H,K<G be proper. If either is not of fiber type H_d, Section 3 supplies a two-point base and Section 1 proves the pair G/H disjoint union G/K is 3-closed. If both are fiber groups, Section 4 proves the pair is 3-closed. The integrated two-orbit reduction now implies that every faithful finite permutation representation of G is 3-closed. This proves total 3-closure for every p>=17 with p!=19.

## 6. The small negative case p=5

PSL_2(5) is A_5. In its natural faithful action on five points, A_5 is sharply 3-transitive: its order is 5*4*3=60 and the pointwise stabilizer of three distinct points is trivial. Hence A_5 and S_5 have exactly the same orbits on ordered triples, namely the equality-pattern orbits. The 3-closure therefore contains S_5 and is strictly larger than A_5. Thus PSL_2(5) is not totally 3-closed.

## 7. Exact residual theorem at p=19

Let G=PSL_2(19), let Y=G/A_5, and let X_d be as above. Here m=9, so d=1,3,9.

All proper-subgroup pairs except those involving Y are already covered. The mixed pair Y disjoint union X_1 has a two-point base because A_5 has no element of order 19. For d=3 or 9, synchronization follows once Y itself is known to be 3-closed.

Indeed, an A_5 subgroup is transitive on the 20 projective points: its point stabilizers are cyclic of order 1,2,3, or 5, giving possible orbit lengths 60,30,20,12, and the only way to sum to 20 is one orbit of length 20 with stabilizer C_3. Every C_3 subgroup P of G lies in exactly three A_5 subgroups from a fixed degree-57 conjugacy class, because

57*10/(|G|/18)=57*10/190=3.

Any two distinct such A_5 subgroups intersect exactly in P. To see this, an overgroup of P inside A_5 larger than P is D_6 or A_4. The normalizer of a D_6 in G is D_6, so there are |G|/6=570 such subgroups, equal to the 57*10 incidences with the chosen A_5 class; hence each D_6 belongs to only one member of that class. Likewise N_G(A_4)=A_4, there are |G|/12=285 A_4 subgroups, and this equals 57*5, so each A_4 belongs to only one member of the class. Thus two distinct members containing P have intersection P.

Now suppose a 3-closure element fixes Y pointwise. Given y in X_3 or X_9, choose P=C_3 in its stabilizer and two Y-points whose stabilizers intersect in P. Preservation of the orbit of the mixed triple formed by these two Y-points and y forces the image of y into P y={y}. Hence it fixes X_d pointwise. Repeated copies of Y synchronize automatically: after fixing the first copy, the cross-copy triple based at corresponding points forces the second copy point to remain corresponding.

It remains only to prove that the degree-57 action Y is 3-closed. A sufficient, strictly stronger finite statement is this:

Perkel-graph lemma. In the degree-57 coset action of PSL_2(19) on an A_5 subgroup, the orbital graph of valency six has full automorphism group PSL_2(19).

The lemma implies that Y is already 2-closed, hence 3-closed, and the preceding argument then proves PSL_2(19) totally 3-closed.

## Proof spine

1. Two-point-base lemma -> every pair containing such a constituent is 3-closed.
2. Subgroup dichotomy -> every proper subgroup is toral, exceptional, or H_d.
3. Toral and exceptional counting -> a two-point base exists for p>=17 except A_5 at p=19.
4. Scalar-quotient rigidity -> all H_d-H_e pairs are 3-closed.
5. Steps 1-4 plus the integrated two-orbit reduction -> PSL_2(p) is totally 3-closed for p>=17, p!=19.

The single remaining theorem-level gap in the prime-field A1 branch is the Perkel-graph lemma for p=19.

## Near miss and self-check

The strongest failed route was the diagonal outer automorphism in PGL_2(p): a three-base splits a triple orbit, so this overgroup does not supply a negative witness. The present proof abandons that route and instead reconstructs the action from bases and scalar fibers.

The p-divisible subgroup argument uses all p+1 Sylow p-subgroups and the elementary generation of SL_2 by opposite root groups. The tame classification is proved inside the dossier. The exceptional union bound counts prime-order subgroups rather than elements and remains strict at p=17 for A_4 and S_4 and at p=29 for A_5. The scalar model checks faithfulness, repeated constituents, mixed constituents, and the projective-to-fiber round trip. No finite computation is used for the infinite theorem. No verification status is asserted.
