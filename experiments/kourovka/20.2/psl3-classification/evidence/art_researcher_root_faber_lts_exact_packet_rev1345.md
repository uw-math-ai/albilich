# Exact source packet and proof of LTS(p)

## Local theorem

Let p≥5 be prime with p≡2 modulo 3, let L=GL_2(p), let M≤L not contain SL_2(p), and let D≤L be a split maximal torus. Then some g∈L satisfies

D∩M^g = D∩core_L(M).

Equivalently, the projective image A of M has an ordered pair of points of P^1(F_p) with trivial pointwise stabilizer. This supplies the exact Levi split-torus separator used in the relative-regular-anchor step of the current DNFK proof.

## Exact external theorem and source interface

Source: Xander Faber, “Finite p-Irregular Subgroups of PGL(2,k),” La Matematica 2 (2023), 479–522, DOI 10.1007/s44007-023-00051-4, paper_id Faber-PGL2-2023, arXiv:1112.1999v4. The relevant result is Theorem D on PDF pages 3–4; its proof is on PDF pages 28–30.

Complete statement of Theorem D in the notation needed here: if q=p^r and G=PGL_2(F_q), every conjugacy class of nontrivial subgroups of G occurs in one of ten cases. (1) For n≥2 with q≡1 mod n there is one class of split cyclic groups of order n. (2) For n≥2 with q≡−1 mod n there is one class of nonsplit cyclic groups of order n. (3) For n≥3 with q≡1 mod n there are split dihedral groups of order 2n, with two conjugacy classes when q≡1 mod 2n and one otherwise. (4) For n≥3 with q≡−1 mod n there are nonsplit dihedral groups of order 2n, with two classes when q≡−1 mod 2n and one otherwise. (5) If q is odd there are exactly two classes of Klein four-groups. (6) There is one class of A_4 when p is odd, or when p=2 and r is even. (7) There is one class of S_4 when p≠2. (8) There is one class of A_5 when q≡0,±1 mod 5. (9) For every s dividing r there is one class of each of PSL_2(F_{p^s}) and PGL_2(F_{p^s}). (10) If m,n are positive, m≤r, gcd(n,p)=1, and e=ord_n(p) divides gcd(r,m), then p-semi-elementary groups of order p^m n occur; their classes correspond to homothety classes of F_{p^e}-subspaces of F_q of dimension m/e. Faber defines p-semi-elementary to mean that the group has a unique Sylow p-subgroup of exponent p and cyclic quotient. In the finite-field case the proof shows that such a subgroup has a unique rational fixed point and is conjugate into the affine Borel.

Faber proves the exhaustion by combining the p-regular classification with Theorems A and B for p-irregular groups. The proof of Theorem D puts split and nonsplit dihedral groups into explicit torus-normalizer forms over F_q or F_{q^2}, treats A_4,S_4,A_5 using the preceding existence and conjugacy theorems, eliminates or identifies subfield groups through Theorems A and B, and derives the affine form of the p-semi-elementary groups from their unique fixed point. Thus the source theorem classifies projective subgroups; the base-pair deductions below are local arguments rather than an unstated consequence of the citation.

## 1. Passing from GL_2(p) to PGL_2(p)

Let Z=Z(L), let π:L→PGL_2(p), and put A=π(M). First A does not contain PSL_2(p). Indeed, if it did, then π([M,M]) contains [PSL_2(p),PSL_2(p)]=PSL_2(p), while [M,M]≤M∩SL_2(p). Hence M∩SL_2(p) maps onto PSL_2(p). It is therefore either SL_2(p), or an index-two subgroup of SL_2(p). The second alternative is impossible because SL_2(p) is perfect for p≥5. Thus M would contain SL_2(p), contrary to the hypothesis.

The projective core core_{PGL_2(p)}(A) is trivial. To see this without importing another classification theorem, intersect it with the simple normal subgroup PSL_2(p). A nontrivial intersection is all of PSL_2(p), which was excluded. A trivial intersection makes the core centralize PSL_2(p), whose centralizer in PGL_2(p) is trivial. Consequently

core_L(M)=M∩Z.                                                    (1)

A split maximal torus D is the full inverse image of the pointwise stabilizer in PGL_2(p) of an ordered pair of distinct projective points. Therefore it suffices to prove that A has an ordered pair (x,y) with A_{x,y}=1. Conjugating that pair to the two eigenlines of D gives g with π(D∩M^g)=1. Hence D∩M^g≤Z, and then

D∩M^g=Z∩M^g=Z∩M=core_L(M)=D∩core_L(M),

where all scalars lie in D. This also proves the round-trip implication from the projective base-pair formulation to the original linear intersection formula.

## 2. Exhaustive base-pair proof

Specialize Faber’s Theorem D to q=p, so r=1. Its subfield case contains only PSL_2(p) and PGL_2(p), both excluded. Its p-semi-elementary case has m=e=1 and is contained in an affine Borel. Thus it remains to handle affine, toral, dihedral, four-group, and exceptional subgroups.

### Affine case

After conjugacy A consists of maps z↦az+b fixing infinity. The ordered pair (0,1) is a base: fixing 0 forces b=0 and then fixing 1 forces a=1. This handles every p-semi-elementary subgroup and every subgroup contained in a Borel.

### Split torus-normalizer case

After conjugacy the split normalizer consists of z↦az and z↦a/z. Choose c∈F_p with c≠0,±1. The pair (1,c) is a base. A map z↦az fixing 1 has a=1. A map z↦a/z fixing 1 has a=1, and it could then fix c only if c^2=1, which was excluded. This handles split cyclic and split dihedral groups and their subgroups.

### Nonsplit torus-normalizer case

A nonidentity element of a nonsplit torus has no F_p-rational fixed point. In its normalizer, only the p+1 elements outside the torus can fix rational points, and each projectivity fixes at most two points, hence at most two ordered pairs of distinct points. They cover at most 2(p+1) of the p(p+1) ordered distinct pairs. Since p>2, an uncovered pair exists and is a base. This handles nonsplit cyclic and nonsplit dihedral groups.

For a Klein four-group, choose a nonidentity involution. Its centralizer in PGL_2(p) is the normalizer of its split or nonsplit torus, so the four-group is covered by one of the preceding two arguments.

### Exceptional groups except S_4 at p=5

Every nonidentity projectivity fixes at most two ordered distinct pairs. Thus a subgroup E has a base pair whenever

2(|E|−1)<p(p+1).                                             (2)

For E=A_4 this is 22<30 for all p≥5. For E=S_4 it is 46<p(p+1) for p≥7. For E=A_5 it is 118<p(p+1) for p≥11. Under p≡2 mod 3, either p=5 or p≥11. At p=5 the unique A_5 from Faber’s Theorem D is PSL_2(5), excluded because A does not contain PSL_2(p). Hence only S_4≤PGL_2(5) needs a separate argument.

### Explicit S_4≤PGL_2(5)

On X=P^1(F_5), define

a(z)=2z,    b(z)=(z+2)/(z+3).

The matrix of b is [[1,2],[1,3]]. Direct multiplication gives b^3=1, a has order 4, and (ab)^2=1 projectively. The spherical presentation with orders (4,3,2) gives a quotient of S_4; because the image contains an element of order 4, it cannot be a proper quotient of S_4. Thus H=⟨a,b⟩≅S_4.

Moreover b sends infinity to 1, the powers of a send 1 through 1,2,4,3, and b sends 3 to 0. Hence H is transitive on all six projective points. Its infinity stabilizer has order 24/6=4 and contains ⟨a⟩, so H_infinity=⟨a⟩. No nonidentity power of a fixes 1. Therefore H_{infinity,1}=1. Faber’s uniqueness assertion for S_4 in Theorem D transfers this base pair to every S_4≤PGL_2(5).

This completes every case of Theorem D and proves LTS(p).

## 3. Conceptual invariant and neighboring-theorem comparison

The selected invariant is the projective two-anchor base. In linear language one seeks D∩M^g modulo scalars; in projective language one seeks an ordered pair whose pointwise A-stabilizer is trivial; in Möbius language one seeks a pair outside the fixed-pair cover of nonidentity elements. The projective representation is strictly simpler because it separates the unavoidable scalar core before any subgroup case analysis.

The neighboring source theorem classifies all finite projective subgroups, whereas DNFK studies a Levi image inside a parabolic fiber. The object dictionary is: M≤GL_2(p) corresponds to A=π(M); the linear scalar core corresponds to the kernel discarded by π; a split torus corresponds to the pointwise stabilizer of two projective points; conjugating M corresponds to moving the two anchors; and a base pair corresponds exactly to the LTS intersection equality. This invariant simultaneously yields the LTS lemma and the relative-regular Levi anchor required in the DNFK frame descent.

A concrete falsification test shows the hypothesis is sharp. If A contains PSL_2(p), then its pointwise stabilizer of any ordered pair has order at least (p−1)/2 and no two-anchor base exists. In the DNFK core dichotomy this is precisely the separate large-core branch, where P_x^0 acts trivially on the complete fiber. Thus the projective invariant does not silently assume away that branch.

## 4. Assembly into DNFK and the root route

In the small-core DNFK branch, let M be the Levi image of H_x and let D be the frame torus in the Levi factor. The theorem just proved supplies l with D∩M^l=D∩core(M). If H_x∩Q_x=Q_x, the corresponding coset is immediately a relative-regular anchor modulo the fiber kernel. If H_x∩Q_x<Q_x, the affine displacement argument in the current DNFK dossier removes the remaining nonidentity scalar elements because their action on Q_x is multiplication by c^(−3)≠1. Thus the anchors used by the corrected oriented frame descent now have an exact, verifier-visible subgroup-exhaustion proof.

Combining this packet with art_researcher_root_oriented_right_gauge_dnfk_repair_rev1341 supplies the previously missing LTS dependency of the arbitrary-H DNFK argument. The remaining root assembly is unchanged: parabolic descendants use DNFK; nonparabolic constituents use the integrated base-two host results and synchronization; pairs of parabolic descendants use the integrated quotient-incidence theorem; and the integrated two-orbit reduction, outer obstruction, and q=2,3 certificates yield the claimed classification. This dossier does not assert verification status; it supplies new evidence for strict checking of the existing root inference.

## 5. Counterexample probe and self-check

The two full-hypothesis conjectures tested were: (positive) every M≤GL_2(p) not containing SL_2(p) admits the required separator; (negative) the exceptional S_4≤PGL_2(5) has no projective base pair. The explicit generators above refute the negative conjecture under the exact p=5 hypotheses. Removing the exclusion of SL_2(p) produces a genuine failure, so that weakened example is diagnostic rather than a counterexample to LTS.

Self-check: the proof covers M≤Z, affine and p-containing groups, both torus types, both dihedral types, both four-group classes, A_4, S_4, A_5, p=5, all primes p≥5 with p≡2 mod 3, arbitrary split D, and the passage back through scalars. It uses Faber only for the exhaustive projective subgroup list and proves every base-pair assertion locally. It does not assume fiberwise normalizer containment, fingerprint injectivity, or the false two-quotient-anchor shortcut.
