# Replacement section: scalar-quotient reduction and determinant-neutral parabolic rigidity

## Proposition

Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p)=PSL_3(p), let P be a point parabolic, and let H≤P. Then the action of G on Ω=H\G is 3-closed. The line-parabolic case follows by contragredient duality.

This section replaces only the parabolic-descendant paragraph of the canonical proof. It simultaneously resolves the named cyclic scalar-quotient closure obligation and the determinant-neutral fiber-kernel obligation.

## Step 1: the scalar quotient forces determinant neutrality

Write P^0=Q⋊SL_2(p), where Q is the unipotent radical. Then P/P^0 is cyclic of order p−1. Put J=HP^0. Since P^0 is normal in P, J is a subgroup between H and P. The action on J\G is one of the scalar-fiber actions (F_p^3 minus {0})/C, where C is the subgroup of F_p^* corresponding to J/P^0. Certified premise 5 of the root statement says that this action is faithful and 3-closed.

Let c belong to the 3-closure of G on H\G. Every G-invariant equivalence relation on Ω is preserved by c: it is a union of G-orbits on ordered pairs, and pair orbits are recovered from the triple orbits containing tuples of the form (α,β,β). In particular c preserves the system of J-blocks. Its induced permutation on J\G lies in the 3-closure of the quotient action. Indeed, lift any ordered triple of J-cosets to an ordered triple of H-cosets; the image under c is G-conjugate to the original lifted triple, and therefore the induced quotient triple is G-conjugate to the original quotient triple.

Scalar-fiber rigidity therefore supplies g∈G inducing the quotient action of c. Replace c by k=cg^(-1). Then k fixes every J-block. Consequently it fixes every P-block and, for every α in the fiber over a projective point x,

αk ∈ α^(P_x^0).

Thus the cyclic scalar quotient gives exactly the determinant-neutral hypothesis required by DNFK. No separate antiframe assumption is needed.

## Step 2: classification of complete-fiber kernels

For a projective point x, let H_x be the transported copy of H in P_x and put N_x=core_(P_x)(H_x), the kernel of P_x on the complete fiber X_x. Fix x and write

P_x=Q_x⋊L_x,  L_x≅GL_2(p),  P_x^0=Q_x⋊SL_2(p).

Relative to V=x⊕W, a Levi element A∈GL_2(p) acts on Q_x≅F_p^2 by

ρ(A)u=(det A)^(-1)uA^(-1).

Let N=N_x. Since N∩Q_x is L_x-invariant and Q_x is an irreducible L_x-module, N∩Q_x is either 1 or Q_x. If it is 1, then [N,Q_x]=1. Directly from the displayed action, C_(P_x)(Q_x)=Q_x: a Levi element centralizing Q_x must be scalar cI with c^3=1, hence c=1 because gcd(3,p−1)=1. Therefore N=1.

Suppose Q_x≤N. The image N/Q_x is normal in GL_2(p). If it does not contain SL_2(p), its projective image is a normal subgroup of PGL_2(p) disjoint from PSL_2(p), hence centralizes PSL_2(p). That centralizer is trivial: a Möbius transformation commuting with all translations is itself a translation, and commuting with one nontrivial square dilation forces its translation parameter to vanish. Thus N/Q_x lies in Z(GL_2(p)). We obtain the dichotomy

P_x^0≤N_x,

or

N_x=1 or N_x=Q_x⋊Z_x with Z_x≤Z(GL_2(p)).

In the second case, N_x∩N_y=1 for every distinct projective point y. To see this, take x=<e_1>, y=<e_2>. An element of N_x∩N_y has both forms

[[c^(-2),u,v],[0,c,0],[0,0,c]]

and

[[d,0,0],[u',d^(-2),v'],[0,0,d]].

Equality forces all off-diagonal entries to vanish and c=d=c^(-2), so c^3=1 and the element is the identity.

## Step 3: relative-regular anchors for every small-core fiber

Let F={x,y,z} be a projective frame and let T_F be its pointwise stabilizer, a split maximal torus. The kernel of T_F on X_x is K_x=T_F∩N_x. We prove that T_F has an orbit on X_x whose point stabilizer is exactly K_x.

Identify P_x with Q⋊L, put D=T_F≤L, let M be the image of H_x in L, and put W=H_x∩Q.

First suppose M contains S=SL_2(p). Irreducibility gives W=0 or Q. The latter would imply P_x^0≤N_x, so in the small-core case W=0. The inverse image of S in H_x is a complement to Q in Q⋊S. Every such complement is Q-conjugate to S. Indeed, for a cocycle a:S→Q and the central element z=−I, which acts as −1 on Q,

a(zs)=a(z)−a(s),  a(sz)=a(s)+s a(z).

Since zs=sz, this gives 2a(s)=a(z)−s a(z), so a is the coboundary of a(z)/2. After conjugation, H_x contains the standard S. It then lies in L, because an element of Q⋊L normalizing S has Q-component fixed by S, and Q^S=0.

For D=diag(b,c), its two eigencharacters on Q are

(b^(−2)c^(−1), b^(−1)c^(−2)).

The exponent matrix has determinant 3, so this character map D→(F_p^*)^2 is an isomorphism. Choose q∈Q with both root coordinates nonzero. Its D-stabilizer is trivial, and hence D∩H_x^q=1=K_x.

Now suppose M does not contain S. Apply the existing Levi split-torus separator claim claim_root_levi_split_torus_separator_rev1210: after conjugating by l∈L,

D∩M^l=D∩core_L(M)=R.

If W=Q, then H_x is the full inverse image of M, N_x is the full inverse image of core_L(M), and immediately D∩H_x^l=D∩N_x=K_x.

Assume W is proper. Then N_x∩Q=1 and hence N_x=1. Moreover R lies in Z(L). For each nonidentity d∈R, the lifts of d in H_x^l form an affine coset of W. Conjugating by q∈Q makes the pure torus element d belong to H_x^(lq) precisely when q lies in one affine coset of W, because ρ(d)−1 is a nonzero scalar: for d=cI, ρ(d)=c^(−3)I, and the cube map is injective. There are at most |R|−1≤p−2 forbidden cosets. If dim W=0, Q/W has p^2 elements; if dim W=1, it has p elements. Hence the forbidden cosets cannot cover Q/W. Choose q outside them. Then D∩H_x^(lq)=1=K_x.

Thus every coordinate action of every frame torus has a relative-regular anchor.

## Step 4: simultaneous realization on a frame

We use the following elementary orbit-tensor lemma. Let a group T act on Y_1,Y_2,Y_3 with kernels K_i. Suppose each action has a point η_i whose stabilizer is K_i and K_j∩K_k≤K_i cyclically. Then every triple of coordinate permutations preserving every diagonal T-orbit on Y_1×Y_2×Y_3 is induced on all three coordinates by one element of T.

For proof, use the orbit of (η_1,η_2,η_3) to normalize the three coordinate maps so that they fix all anchors. For arbitrary y∈Y_1, a witness for (y,η_2,η_3) lies in K_2∩K_3≤K_1 and hence fixes y. Thus the first normalized map is the identity; the other two follow cyclically.

Apply this with T=T_F and Y_i the three complete fibers over F. Because k fixes the P-blocks, every lifted triple and its image lie over the same ordered projective frame. A G-element witnessing equality of their triple colors therefore fixes the three quotient points and belongs to T_F. Thus the restrictions of k preserve every diagonal T_F-orbit. In the small-core case, K_y∩K_z≤N_y∩N_z=1 cyclically, and Step 3 supplies the anchors. Hence there is d_F∈T_F inducing k on all three complete fibers.

## Step 5: global gluing and conclusion

If P_x^0≤N_x, then P_x^0 acts trivially on X_x. Determinant neutrality from Step 1 gives αk=α for every α∈X_x, and conjugacy gives the same conclusion on every fiber.

Otherwise all fiber cores are small. If two projective frames F and F' share distinct points x and y, then d_F and d_F' induce the same permutation k on X_x and X_y. Therefore d_Fd_(F')^(-1) lies in N_x∩N_y=1, so d_F=d_F'. The basis graph of the rank-three projective matroid is connected by single basis exchanges, hence all d_F equal one element d∈G. Every projective point lies in a frame, so d fixes every projective point. It is scalar, and Z(SL_3(p))=1 because gcd(3,p−1)=1. Thus d=1 and k=1.

Returning to c, we have c=g∈G. Therefore G on H\G is 3-closed for every H in a point parabolic. Contragredient duality proves the line-parabolic case.

## Five-step proof spine

Scalar quotient neutrality → normal-core dichotomy → relative-regular anchors → frame orbit-tensor realization → overlap gluing and k=1.

Inserted into the existing root route, this proves every residual-prime parabolic constituent is individually 3-closed. A pair with a nonparabolic constituent is handled by the integrated base-two host and synchronization claims; a pair of parabolic descendants is handled by the integrated quotient-incidence synchronization claim. The integrated two-orbit reduction then gives total 3-closure for every residual prime. Together with the integrated q=2, q=3 results and the projective outer obstruction, the classification is exactly: q is prime and either q=3 or q≡2 modulo 3.

## Near-miss autopsy and self-check

The strongest earlier near miss tried to identify adjacent frame witnesses directly; that fails when their difference lies in a shared fiber kernel. The replacement first classifies normal fiber cores, proves that every small-core pair overlap is trivial, and handles the large-core case before gluing. The p=5 tensor audit was only diagnostic and is not used as proof.

The argument checks arbitrary H≤P, H=1, H=P^0, H=P, p=5, proper scalar quotients, Levi images containing SL_2(p), Levi images not containing SL_2(p), both possible dimensions of H∩Q, all complete fibers, and the dual line-parabolic case. It uses no normalizer-quotient assumption, fingerprint injectivity, tuple-witness uniqueness, or finite extrapolation. No verification status is asserted.
