# Conditional closure of orthogonal building recognition

## Exact conditional lemma
Let S be a finite simple orthogonal group in defining characteristic p, of type B_m(q) with q odd and m>=5, split D_m^+(q) with m>=5, or twisted D_m^-(q) with m>=5. Let Delta(S) be its actual spherical BN-pair building; in the twisted minus case this means the Frobenius-fixed, folded relative building rather than an incorrectly relabelled split D_m building. Assume:

(BT_p) Every subgroup H<=S with O_p(H) nontrivial is contained in a proper parabolic subgroup of S.

Then the maximal parabolics and their incidence are intrinsically recoverable from the abstract group S, every abstract automorphism of S induces an automorphism of Delta(S), and this action of Aut(S) on Delta(S) is faithful.

## Proof
Define M_p to be the set of maximal proper subgroups M<S satisfying O_p(M) != 1. If M belongs to M_p, hypothesis (BT_p) places M in a proper parabolic P. Maximality gives M=P, and because M is maximal proper, P is a maximal parabolic. Conversely, a maximal parabolic P is a maximal proper subgroup and its unipotent radical O_p(P) is nontrivial. Thus M_p is exactly the set of maximal parabolics. Maximality, the prime p, and O_p are invariant under group isomorphisms, so every abstract automorphism permutes M_p.

Incidence is also intrinsic. A finite set of maximal parabolics is declared incident precisely when its intersection contains a Sylow p-subgroup U of S. For the standard BN-pair this is equivalent to the usual condition that the parabolics contain a common Borel subgroup. One direction is immediate because a Borel contains a Sylow p-subgroup. Conversely, if a parabolic P contains U, choose a Borel B_0<=P and a Sylow p-subgroup U_0<=B_0. Both U and U_0 are Sylow in P, so some x in P sends U_0 to U; hence B_0^x<=P is a Borel containing U. Applying this simultaneously to incident standard parabolics, or equivalently using the residue through U, shows that parabolics containing the same U form a chamber face. Therefore the abstractly reconstructed incidence complex is Delta(S).

For faithfulness, let K be the kernel of the Aut(S)-action on this complex. An element of K fixes every maximal parabolic setwise and hence fixes the intersection B of the maximal parabolics in every chamber. It fixes O_p(B), which is the corresponding Sylow p-subgroup. Therefore K fixes every Sylow p-subgroup setwise. The subgroup K is normal in Aut(S). Its intersection with the inner automorphism group S is normal in the nonabelian simple group S. It cannot equal S, since conjugation by S acts nontrivially on its Sylow p-subgroups; hence K intersect S is trivial. For k in K and s in S, the commutator [k,s] lies both in K and in S, so it is trivial. Thus k centralizes every inner automorphism. Since S is centerless, c_{k(s)}=k c_s k^{-1}=c_s implies k(s)=s for every s, and k is the identity. Hence K=1.

Finally, an automorphism of the unlabelled chamber complex globally permutes vertex types: choose the permutation on one chamber and propagate it along adjacent chambers; connectedness makes it global, while rank-two residues force preservation of the Coxeter matrix. For B-type relative diagrams there is no nontrivial diagram permutation. For split D_m with m>=5 the only permutation exchanges the two terminal types and is realized by the improper-isometry coset already present in the verified semilinear dossier. The D_4 triality case remains outside the high-rank branch. In twisted D_m^-(q), the finite building is folded by Frobenius and must be treated using its relative diagram; no split-terminal count is assumed.

This proves BRK from (BT_p). It does not assume the missing polar-coordinate theorem and does not claim OA. Once a type-corrected building action is known, the remaining geometric interface is: every relevant orthogonal-building incidence automorphism is induced by a projective semilinear quadratic similarity. Combining that interface with this lemma proves OA, and OA then upgrades the already verified semilinear decomposition-normalizer theorem to all abstract automorphisms.

## Why the index attack fails
For split B_m, the node-i maximal-parabolic index is P_Bm(q)/(P_A(i-1)(q)P_B(m-i)(q)). Adjacent indices satisfy I_{i+1}/I_i=[2(m-i)]_q/[i+1]_q. Hence B_{3k+2} has equal indices at nodes 2k+1 and 2k+2 for every q. Thus even exact subgroup orders cannot reconstruct the types; this obstruction is structural and not a small-field accident.

## Self-check
The proof uses (BT_p) only as an explicit hypothesis. It does not infer the twisted-minus building from the split-D computation. Simplicity and centerlessness are used in the kernel argument. D_4 triality, small accidental isomorphisms, and characteristic-two odd-dimensional B-type are outside this claim, the last already belonging to the symplectic branch. No verification status is asserted.
