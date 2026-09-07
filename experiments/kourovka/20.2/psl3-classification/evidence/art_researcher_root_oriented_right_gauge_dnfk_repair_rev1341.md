# Oriented right-gauge repair of the DNFK frame descent

## Local theorem

Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p)=PSL_3(p), let P be a point parabolic, and let H≤P. Put Ω=H\G and C=G^(3). After the certified determinant-neutral quotient reduction, suppose k∈C fixes every projective block and satisfies α^k∈α^(P_x^0) on every complete fiber X_x. Then k=1. The line-parabolic case follows by contragredient duality.

This is a replacement for the normalization paragraph in Section 5 of art_researcher_root_wielandt_frame_descent_dnfk_rev1336. It repairs the noncommutative right-action order identified by the revision-1338 adversarial check.

## 1. Exact right-action normalization lemma

Use the right-action convention (ω^a)^b=ω^(ab). If permutations k and t agree on a tuple η, so η^k=η^t, then

h=kt^(-1)

fixes η, because η^h=(η^k)^(t^(-1))=(η^t)^(t^(-1))=η. The reversed product t^(-1)k need not fix η. Thus normalization of a right action is by postcomposition with the inverse witness.

The same orientation determines transition elements. If t and s induce the same permutation on a subset Y, then ts^(-1) fixes Y pointwise: for y∈Y,
y^(ts^(-1))=(y^t)^(s^(-1))=(y^s)^(s^(-1))=y.

## 2. Imported local interface

The earlier DNFK dossiers establish the following facts for every arbitrary H≤P.

1. For every projective point x, let N_x=core_(P_x)(H_x), the kernel of P_x on the complete fiber X_x. Uniformly in x, either P_x^0≤N_x, or the small-core branch holds and N_x∩N_y=1 for distinct projective points x,y.
2. For every ordered projective frame F=(x,y,z), put D_F=P_x∩P_y∩P_z and K_x=D_F∩N_x, cyclically. In the small-core branch there are anchors η_x∈X_x, η_y∈X_y, η_z∈X_z with (D_F)_(η_i)=K_i.
3. The kernel triangle satisfies K_y∩K_z≤K_x cyclically; in fact each left side is trivial in the small-core branch.
4. Since G and C have the same orbits on Ω^3, their two-point stabilizers have the same orbits on Ω: G_(η,θ) and C_(η,θ) are 1-equivalent.

The core profile and anchor construction use the integrated Levi split-torus separator claim and the residual-prime cube condition. No fiberwise normalizer containment or fingerprint injectivity is used.

## 3. Corrected local frame descent

Fix a frame F=(x,y,z) and the three anchors above. Because k preserves the G-orbit of the anchor triple, there is t_F∈G such that

(η_x,η_y,η_z)^k=(η_x,η_y,η_z)^(t_F).

Both triples project to the same ordered frame, so t_F fixes x,y,z and belongs to D_F. Define

h_F=kt_F^(-1).

Then h_F∈C and fixes all three anchors. It also preserves each of the three frame fibers X_x,X_y,X_z. One must not assert that h_F fixes every projective block: t_F generally moves projective points outside F, and the proof does not need that stronger false assertion.

Take u∈X_x. Since h_F∈C_(η_y,η_z), stabilizer descent supplies a∈G_(η_y,η_z) with u^(h_F)=u^a. The points u and u^(h_F) lie in X_x, so a fixes the quotient point x. Since a fixes η_y and η_z, it also fixes y and z. Hence a∈D_F. Moreover

a∈(D_F)_(η_y)∩(D_F)_(η_z)=K_y∩K_z≤K_x.

Elements of K_x fix X_x pointwise, so u^(h_F)=u. Since u was arbitrary, h_F fixes X_x pointwise. The cyclic argument fixes X_y and X_z pointwise. Therefore k and t_F induce the same permutation on all three complete fibers of F.

This argument uses simultaneous triple colors through the equality of the two-anchor stabilizer orbits; it does not compare independently chosen tuple witnesses.

## 4. Corrected transition and global descent

Let adjacent frames F and F' share x and y. For every α∈X_x∪X_y,

α^(t_F)=α^k=α^(t_F').

By the oriented transition lemma, t_F t_(F')^(-1) fixes X_x and X_y pointwise. It therefore belongs to N_x∩N_y, which is trivial in the small-core branch. Thus t_F=t_F' on every edge of the connected projective frame graph.

All local witnesses consequently equal one t∈G. Every projective point occurs in a frame, and the corresponding t_F fixes that frame, so t fixes every projective point. The projective kernel of SL_3(p) has order gcd(3,p−1)=1; hence t=1. Since k agrees with t on every complete fiber, k=1.

In the large-core branch P_x^0≤N_x on every fiber. Determinant neutrality gives α^k∈α^(P_x^0), while P_x^0 acts trivially on X_x, so k fixes every α directly. Thus k=1 in both branches.

## 5. Full-hypothesis adversarial probe

The competing full DNFK conjectures were:

- positive: every determinant-neutral block-kernel element is trivial;
- negative: some residual prime and H≤P admit a compatible nontrivial frame holonomy.

After correcting the orientation, the negative conjecture would require either a nontrivial normalized action on one frame fiber or a nontrivial transition on a shared pair of fibers. The first is excluded by the two-anchor stabilizer argument and the kernel triangle; the second is excluded by N_x∩N_y=1. These deductions hold for arbitrary H. The bounded p=5 calculation in the companion CAS report separately checks representative subgroups from every core/anchor branch and finds no missing relative-regular anchor.

The old left-normalization step is genuinely false, rather than merely unjustified: in the right action of S_4, exhaustive enumeration gives 72 failures among 144 pairs k,t agreeing on a chosen anchor, whereas kt^(-1) has zero failures. This counterexample attacks only the old proof step, not DNFK.

## 6. Representation switch and conceptual invariant

Three representations are compared.

1. Geometric fibers: k is a coordinatewise permutation of complete fibers preserving every triple color.
2. Right permutation torsors: a witness t_F is a local gauge, and the normalized defect is kt_F^(-1).
3. Oriented frame atlas: local defects live on frames and transition elements t_F t_(F')^(-1) live on overlaps.

The dictionary is exact: agreement of k and t_F on the anchor triple is equivalent to fixing that triple after right normalization; pointwise vanishing of the normalized defect is equivalent to agreement on the three complete fibers; agreement of two witnesses on shared fibers is equivalent to their oriented transition fixing those fibers. Connectedness then returns a single global G-element inducing k. The right-torsor/atlas representation is selected because it makes composition order explicit and removes the only newly exposed gap.

The neighboring Čech-descent analogy must be oriented: k is the object being trivialized, t_F is a right local section, kt_F^(-1) is the local defect, and t_F t_(F')^(-1) is the overlap cocycle. Reversing either product changes the assertion in a noncommutative permutation group.

## 7. Root assembly and self-check

With DNFK repaired, every parabolic descendant for residual primes p≥5 is individually 3-closed. The integrated nonparabolic maximal-host theorem and base-two synchronization handle every pair having a nonparabolic constituent; the integrated mixed-parabolic quotient-incidence theorem handles pairs of parabolic descendants. Together with the integrated two-orbit reduction, the projective outer obstruction, and the q=2 and q=3 certificates, the existing route yields the classification: PSL_3(q) is totally 3-closed exactly when q is prime and either q=3 or q≡2 modulo 3.

Self-check: the corrected proof treats arbitrary H, both core branches, p=5, point and line parabolics, complete fibers, repeated constituents, and the noncommutative order of every product. It uses only preservation of the three fibers belonging to the current frame. It does not claim verification status and should now be submitted, together with the companion CAS report, as new evidence for inference_root_classification_after_quotient_incidence_rev1290.
