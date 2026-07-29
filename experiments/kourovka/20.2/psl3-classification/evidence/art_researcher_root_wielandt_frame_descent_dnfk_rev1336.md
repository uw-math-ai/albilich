# Wielandt stabilizer descent and the two-layer frame invariant for DNFK(p)

## Local theorem

Let p≥5 be prime with p≡2 mod 3, let G=SL_3(p)=PSL_3(p), let P be a point parabolic, and let H≤P. Then the right-coset action of G on Ω=H\G is 3-closed. The analogous assertion for a line parabolic follows by contragredient duality.

The proof below replaces tuple-by-tuple witness comparison by point-stabilizer descent inside the closure group. Its conceptual invariant has two layers: local two-anchor stabilizer orbits on each projective frame, and transition kernels on overlaps of adjacent frames.

## 1. Determinant-neutral reduction

Put P^0=Q⋊SL_2(p), where Q is the two-dimensional unipotent radical, and put J=HP^0. The equivalence relation on Ω whose classes are the J-blocks is G-invariant, hence is a union of G-orbits on Ω². Every element c of C=G^(3) preserves it, because every ordered-pair orbit is recovered from ordered triples by repeating a coordinate.

The permutation induced by c on J\G lies in the 3-closure of the quotient action: lift a quotient triple to Ω, apply c, choose a G-witness for the resulting triple, and project. The quotient action is the certified scalar-fiber action of G on (F_p^3\{0})/A for the subgroup A≤F_p^× corresponding to J/P^0. Certified premise 5 of the root statement makes this quotient action 3-closed. Hence some g∈G induces the same quotient permutation as c. Replacing c by k=cg^(-1), we may assume that k fixes every J-block.

For a projective point x, let X_x be the complete fiber above x, let P_x be its stabilizer, and let P_x^0 be the conjugate of P^0. Then k fixes every projective block and

α^k∈α^(P_x^0) for every α∈X_x.                                              (1)

It remains to prove k=1.

## 2. Source-checked stabilizer descent

We use the following general result.

External result — complete statement. Let m≥2, let A,B≤Sym(Λ) have the same orbits on Λ^m, and let λ∈Λ. Then A_λ and B_λ have the same orbits on Λ^(m−1).

Source: E. A. O'Brien, I. Ponomarenko, A. V. Vasil'ev and E. Vdovin, The 3-closure of a solvable permutation group is solvable, Journal of Algebra 607 (2022), 618–637; paper_id OBrien-Ponomarenko-Vasilev-Vdovin-JA607; theorem_id Theorem 2.3(ii); arXiv id 2012.14166; DOI 10.1016/j.jalgebra.2021.07.002; source URL https://arxiv.org/abs/2012.14166.

Terminology translation. The paper calls A and B m-equivalent when they have the same orbits on Λ^m. This is exactly the relation between G and G^(3) for m=3. The theorem is part of the paper's general Wielandt-theory section and does not assume solvability.

For completeness, the special case used here has a one-line proof. If b∈B_λ and u∈Λ^(m−1), then (λ,u) and (λ,u^b) are in the same B-orbit and hence the same A-orbit. An element a∈A carrying the first tuple to the second fixes λ, so a∈A_λ. Interchanging A and B gives equality of the stabilizer orbits. Iterating the result for m=3 shows that, for any two points η,θ∈Λ, the two-point stabilizers A_{η,θ} and B_{η,θ} have the same orbits on Λ.

Applied with A=G and B=C, this says

G_{η,θ} and C_{η,θ} are 1-equivalent.                                      (2)

This is the exact source-to-local implication; no solvability or transitivity hypothesis is imported.

## 3. Complete-fiber core profile

Let H_x be the transported copy of H in P_x and let N_x=core_{P_x}(H_x), the kernel of P_x on X_x. Write P_x=Q_x⋊L_x with L_x≅GL_2(p). On Q_x≅F_p², written as row vectors, the Levi action is

ρ(A)u=(det A)^(-1)uA^(-1).                                                  (3)

Since N_x is normal in P_x, N_x∩Q_x is L_x-invariant. The natural two-dimensional module is irreducible, so N_x∩Q_x is either 1 or Q_x.

If N_x∩Q_x=1, then [N_x,Q_x]≤N_x∩Q_x=1. The action (3) is faithful: if A acts trivially, then A=cI and c^3=1, whence c=1 because gcd(3,p−1)=1. Thus C_{P_x}(Q_x)=Q_x, so N_x≤Q_x and N_x=1.

Suppose Q_x≤N_x and put R_x=N_x/Q_x◁GL_2(p). If the projective image of R_x contains PSL_2(p), then R_x∩SL_2(p) projects onto PSL_2(p). A proper such intersection would have index two in SL_2(p), impossible because SL_2(p) is perfect for p≥5. Hence SL_2(p)≤R_x and P_x^0≤N_x. If the projective image does not contain PSL_2(p), its intersection with the simple normal subgroup PSL_2(p) is trivial; normality then makes it centralize PSL_2(p). The centralizer of PSL_2(p) in PGL_2(p) is trivial, so R_x is scalar. Therefore exactly one of the following holds:

(a) P_x^0≤N_x;
(b) N_x=1;
(c) N_x=Q_x⋊Z_x with Z_x scalar.                                             (4)

In either small-core case (b) or (c), N_x∩N_y=1 for distinct projective points x,y. By conjugacy take x=<e_1> and y=<e_2>. A common element has both forms

[[c^(-2),u,v],[0,c,0],[0,0,c]] and [[d,0,0],[u',d^(-2),v'],[0,0,d]].

Equality kills u,v,u',v' and gives c=d=c^(-2), hence c^3=1 and c=1. Thus

N_x∩N_y=1 whenever x≠y in the small-core branch.                            (5)

The core type is uniform over all fibers because the pairs (P_x,H_x) are G-conjugate. There are therefore no mixed large-core/small-core frames.

## 4. Relative-regular anchors

Let F=(x,y,z) be an ordered projective frame and let D=T_F=P_x∩P_y∩P_z, the split pointwise frame torus. For a coordinate x put K_x=D∩N_x, the kernel of D on X_x. We prove that, in the small-core branch, D/K_x has a regular orbit on X_x.

Identify P_x=Q⋊L, let M be the Levi image of H_x, and put W=H_x∩Q.

First suppose M contains S=SL_2(p). Since W is S-invariant, irreducibility gives W=0 or Q. The alternative W=Q would give P_x^0≤H_x and hence P_x^0≤N_x, contrary to the small-core assumption. Thus W=0. The inverse image of S in H_x is a complement to Q in Q⋊S. If a:S→Q is its cocycle and z=−I, then z is central and acts as −1 on Q, so comparing a(zs) and a(sz) gives

2a(s)=a(z)−s a(z).

Thus a is a coboundary and the complement is Q-conjugate to the standard S. After this conjugacy, H_x≤L: the standard S is normal in H_x, while N_Q(S)=C_Q(S)=0.

Write an element of D by its Levi coordinate diag(b,c). Its two characters on Q are b^(−2)c^(−1) and b^(−1)c^(−2). Their exponent matrix has determinant 3, invertible modulo p−1, so the character map D→(F_p^×)² is bijective. Choose q∈Q with both root coordinates nonzero. If d∈D stabilizes the coset H_xq, then qdq^(−1)∈H_x≤L, so ρ(d)q=q. Both characters of d are therefore one, and d=1. Here N_x=1, so this stabilizer is K_x.

Now suppose M does not contain SL_2(p). Apply the integrated Levi split-torus separator claim claim_root_levi_split_torus_separator_rev1210. After conjugating H_x by l∈L,

D∩M^l=D∩core_L(M)=R.                                                       (6)

If W=Q, then H_x is the full inverse image of M, and H_xl has D-stabilizer R=D∩N_x=K_x.

If W<Q, then (4) gives N_x=1. The group core_L(M), and hence R, is scalar. For d=cI∈R with d≠1, equation (3) gives ρ(d)=c^(−3)I≠I. The lifts of d lying in H_x^l form at most one affine W-coset, and conjugation by q∈Q moves this coset by (ρ(d)−1)q. Hence each nonidentity d excludes at most one coset of W in Q. There are at most |R|−1≤p−2 excluded cosets, whereas |Q/W| is p or p². Choose q outside their union. Then D∩H_x^(lq)=1=K_x.

Thus every coordinate of every small-core frame has an anchor η_x∈X_x satisfying

D_{η_x}=K_x.                                                               (7)

## 5. Local frame descent

Choose anchors η_x,η_y,η_z as in (7). Since k∈C preserves the G-orbit of the anchor triple, there is t_F∈G carrying that triple to its k-image. Both triples lie over the same ordered frame, so t_F fixes x,y,z and t_F∈D. Put h=t_F^(−1)k. Then h∈C, h fixes all quotient blocks, and h fixes η_x,η_y,η_z.

Take u∈X_x. Since h∈C_{η_y,η_z}, equation (2) gives a∈G_{η_y,η_z} with u^h=u^a. Both u and u^h lie in X_x, so a also fixes the quotient point x. The anchors force a to fix y and z, hence a∈D. By (7),

a∈D_{η_y}∩D_{η_z}=K_y∩K_z.

In the small-core branch, (5) gives K_y∩K_z≤N_y∩N_z=1, and in particular K_y∩K_z≤K_x. Therefore a fixes every point of X_x and u^h=u. As u was arbitrary, h fixes X_x pointwise. The cyclic argument fixes X_y and X_z. Consequently

k and t_F induce the same permutation on all three complete fibers of F.    (8)

This is the local vanishing part of the invariant. It is also an independent proof of the orbit-tensor lemma: instead of choosing a new witness for every product tuple, it uses the group-level equality of two-anchor stabilizer orbits.

## 6. Transition-kernel descent

If adjacent frames F and F' share x and y, then by (8) both t_F and t_F' induce k on X_x and X_y. Hence t_Ft_F'^(−1) fixes those fibers pointwise and lies in N_x∩N_y. Equation (5) makes it trivial. Thus t_F=t_F' on every edge of the frame graph.

The graph of ordered projective frames under basis exchange is connected, and every projective point belongs to a frame. Therefore all t_F equal a single t∈G inducing k on every complete fiber. Since every t_F fixes its frame coordinates, t fixes every projective point. The kernel of the projective action of SL_3(p) is its center, of order gcd(3,p−1)=1. Thus t=1, and (8) gives k=1.

In the large-core branch of (4), P_x^0≤N_x on every fiber. Equation (1) then immediately fixes every α∈X_x because P_x^0 acts trivially on X_x. Hence k=1 there as well.

It follows that the original c equals g∈G. Thus G on H\G is 3-closed for every H≤P. Contragredient duality proves the line-parabolic case.

## 7. Conceptual invariant and falsification tests

The selected invariant is the two-layer stabilizer-descent complex. On a frame F its degree-zero datum is the triangle of coordinate kernels (K_x,K_y,K_z); on an overlap (F,F') its degree-one datum is the transition element t_Ft_F'^(−1) in N_x∩N_y. Relative-regular anchors and the cyclic containments K_y∩K_z≤K_x annihilate the local defect, while (5) annihilates every transition. It simultaneously subsumes relative-regular anchors, the orbit-tensor realization lemma, and frame-holonomy gluing.

The kernel-containment condition is genuinely necessary. Let T=C_2, let Y_1 be two disjoint regular T-orbits, and let Y_2,Y_3 be singletons. Each coordinate has a relative-regular anchor, but K_1=1 and K_2=K_3=T. Translating only one regular orbit in Y_1 preserves all diagonal T-orbits on Y_1×Y_2×Y_3 and is not induced by one element of T. This weakened example does not satisfy DNFK; it falsifies any proof omitting the kernel triangle.

Likewise, local frame realization alone does not kill global holonomy when N_x∩N_y is nontrivial. The transition-kernel calculation is a separate necessary layer. Under the full DNFK hypotheses the exhaustive core dichotomy removes this obstruction: the large-core case is pointwise trivial, and every small-core overlap is trivial by (5). Thus the positive full-hypothesis conjecture is proved and the competing compatible-nontrivial-holonomy conjecture is refuted.

## 8. Root assembly and self-check

The integrated projective obstruction excludes nonprime q and primes q≡1 mod 3. The integrated q=2 and q=3 certificates settle those survivors. For p≥5 prime with p≡2 mod 3, the theorem above makes every parabolic descendant individually 3-closed. The integrated nonparabolic maximal-host claim claim_root_nonparabolic_maximal_host_base2_rev1278 gives a two-point base for every subgroup with a nonparabolic maximal overgroup. A pair with a nonparabolic constituent is therefore closed by the integrated base-two synchronization claim. A pair of parabolic descendants is closed by claim_root_mixed_parabolic_quotient_incidence_rev1290. The integrated two-orbit reduction proves that PSL_3(q) is totally 3-closed exactly when q is prime and either q=3 or q≡2 mod 3.

Self-check: the local proof covers H=1, H=P^0, H=P, arbitrary intermediate H, p=5, both core branches, all dimensions of H∩Q, complete fibers rather than chosen representatives, repeated constituents, and point/line duality. It never assumes fiberwise normalizer containment, fingerprint injectivity, or uniqueness of arbitrary tuple witnesses. The only external result newly used is stated completely, translated, and reproved in the required special case. The scalar-fiber rigidity and LTS inputs are explicitly identified as certified or integrated premises rather than being silently treated as part of DNFK.
