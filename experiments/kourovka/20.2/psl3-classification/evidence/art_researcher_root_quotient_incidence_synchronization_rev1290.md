# Quotient-incidence synchronization and final root assembly

## Uniform mixed-parabolic synchronization theorem

Let p≥5 be prime with p≡2 modulo 3, let G=SL_3(p)=PSL_3(p), and let H and K be proper subgroups contained in point or line parabolics P_X and P_Y. Put A=G/H and B=G/K. Assume the two constituent actions G on A and B are 3-closed. Then the diagonal action of G on A disjoint union B is 3-closed.

## Proof

We use left cosets. The containments H≤P_X and K≤P_Y give surjective G-equivariant quotient maps

ρ_A:G/H→G/P_X,  gH↦gP_X,

ρ_B:G/K→G/P_Y,  gK↦gP_Y.

The target G/P_X is the set X of projective points or projective lines according to the type of P_X; similarly G/P_Y is a set Y of points or lines.

Let C be the 3-closure of the diagonal action on A disjoint union B and take π∈C. The G-orbit of a constant triple (ω,ω,ω) lies in one tagged constituent, so equality of the G- and C-orbits on triples forces π to preserve A and B setwise, even when the two G-sets are isomorphic or are repeated copies. Triples wholly contained in A show that π restricted to A lies in the 3-closure of the constituent action; similarly for B. By the assumed constituent 3-closedness there are a,b∈G inducing these restrictions. Properness of H and K and simplicity of G make both coset actions faithful, although only existence is needed below.

Compose π with the diagonal action of a^{-1}. The normalized permutation fixes A pointwise and acts on B as δ=a^{-1}b∈G. We prove δ=1.

Define a G-invariant relation R⊆X×Y as follows. If X and Y have the same projective type, let R(x,y) mean x=y. If their types are dual, let R(x,y) mean that the point and line are incident. For every x∈X and y∈Y choose α∈A and β∈B with ρ_A(α)=x and ρ_B(β)=y. The normalized π sends the mixed repeated-coordinate triple

(α,α,β) to (α,α,δβ).

These triples belong to the same G-orbit. Hence some t∈G satisfies tα=α and tβ=δβ. Equivariance of the quotient maps gives tx=x and ty=δy. Since R is G-invariant,

R(x,y) if and only if R(tx,ty) if and only if R(x,δy).

This holds for every x∈X. Thus y and δy have the same relation profile

Σ(y)={x∈X:R(x,y)}.

The map y↦Σ(y) is injective. For equal projective types this is immediate because Σ(y) is the singleton {y}. For dual types, two distinct lines are separated by a point lying on one but not the other, while two distinct points are separated by a line through one but not the other. Consequently δy=y for every y∈Y.

If Y is the point set, δ fixes every one-dimensional subspace of F_p^3. A linear representative of δ is therefore scalar: the coordinate lines make each basis vector an eigenvector, and the lines spanned by e_i+e_j force the three eigenvalues to be equal. If Y is the line set, intersections of pairs of lines show first that every point is fixed, and the same conclusion follows. Thus δ=λI with λ^3=1. Since p≡2 modulo 3, gcd(3,p−1)=1, so λ=1. Hence δ=1 and the normalized π is the identity. Undoing the normalization gives π∈G.

Therefore C=G. Notice that the AAB triples alone suffice after normalization; ABB triples provide the symmetric redundant check. The proof covers point-point, point-line, line-point, line-line, arbitrary descendants, repeated constituents, H=P_X, K=P_Y, and both dual orientations.

## Conceptual invariant and falsification test

The invariant is the complete equality-or-incidence profile Σ(y) of a quotient object against the opposite constituent's quotient objects. Mixed repeated-coordinate triple colors force preservation of this profile. Projective-plane quotient objects have no relational twins, so the profile determines y.

The no-twins hypothesis is essential for the abstract mechanism. Let X={x}, Y={y_0,y_1}, and declare both pairs (x,y_i) incident. The transposition of y_0 and y_1 preserves every relation profile while being nontrivial. This refutes the broader assertion that an arbitrary quotient relation suffices. It does not satisfy the projective-plane hypotheses, because projective equality and incidence have injective profiles.

## Comparison with the verified PSL_3(3) argument

The verified artifact art_verification_root_psl33_M3_bilateral_route_rev43 uses exactly the same relational mechanism for the six exceptional parabolic classes at p=3. Its exceptional-subgroup quotient maps correspond here to the maps G/H→G/P_X and G/K→G/P_Y; its E3 constituent theorem corresponds here to the integrated residual-prime individual parabolic 3-closedness theorem; and its quotient equality/incidence separator is field-independent. The only residual-prime kernel check after projective pointwise fixation is λ^3=1, which is killed by gcd(3,p−1)=1. Thus the present proof is the uniform arbitrary-descendant version of that verified bilateral argument, not a new unproved analogy.

## Complete classification assembly

We now assemble the root theorem from the manifest-integrated premises and the bridge just proved.

If q=r^f with f>1, or if gcd(3,q−1)>1, claim_import_psln_projective_nonclosure supplies a faithful projective action with a proper semilinear or diagonal 3-closure overgroup. Hence such PSL_3(q) is not totally 3-closed.

The survivor q=2 is claim_import_psl27_totally_3closed through PSL_3(2)≅PSL_2(7), and q=3 is claim_root_psl33_totally_3closed_A3_rev37.

It remains to take a prime p≥5 with p≡2 modulo 3. By the integrated determinant-neutral parabolic theorem represented in art_researcher_root_relative_regularity_holonomy_invariant_rev1274, every point- or line-parabolic descendant action is individually 3-closed. By art_researcher_root_nonparabolic_host_dichotomy_rev1278 together with the integrated claims claim_root_c2c3_uniform_base2_descendants_rev966 and claim_root_c8_s_base2_hosts_rev1216, every subgroup having a nonparabolic maximal overgroup has base size at most two and its coset action is 3-closed.

Consider any two proper subgroups H,K<G, as required by claim_import_two_orbit_reduction. Choose maximal overgroups of H and K. If at least one is nonparabolic, one constituent has base at most two, both constituents are 3-closed, and claim_root_base2_constituent_synchronization_rev369 closes the diagonal pair. If both chosen maximal overgroups are point or line parabolics, the uniform mixed-parabolic theorem proved above closes the pair. Thus every two-constituent diagonal action is 3-closed, and the two-orbit reduction proves that PSL_3(p) is totally 3-closed.

Therefore, among the nonabelian simple groups PSL_3(q), total 3-closure holds if and only if q is prime and either q=3 or q≡2 modulo 3. This includes q=2 via the exceptional isomorphism. The exclusions and all p≥5 survivor arguments are uniform; the q=2 and q=3 survivors use their already integrated finite certificates.

## Self-check

The proof recovers tagged constituents from constant triples before restricting π; invokes constituent 3-closedness only after that recovery; uses the actual mixed triple orbit to obtain t rather than assuming δ normalizes a stabilizer; uses only the containment G_α≤G_x, so arbitrary descendants are covered; explicitly proves surjectivity and profile injectivity; treats all four point/line orientations and repeated copies; and kills the projective kernel using exactly gcd(3,p−1)=1. It does not reopen DNFK, use fingerprint injectivity, assume a parabolic base of size two, invoke CAS, or use an external unlisted result.
