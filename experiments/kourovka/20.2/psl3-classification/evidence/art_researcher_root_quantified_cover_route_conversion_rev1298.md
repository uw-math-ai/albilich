# Verifier-ready quantified cover and root classification assembly

## Target theorem

Among the nonabelian simple groups PSL_3(q), total 3-closure holds exactly when q is prime and either q=3 or q≡2 modulo 3.

## Lemma 1: arithmetic exhaustion

Write q=r^f. The integrated projective outer-obstruction claim excludes f>1 and also excludes gcd(3,q−1)>1. Thus every surviving parameter is prime and is either 3 or congruent to 2 modulo 3. Conversely, the only prime-field parameters not covered by that obstruction are q=3 and q≡2 modulo 3. The standard simplicity exceptions for projective special linear groups are confined to dimension two, so no further simplicity exception occurs in the PSL_3 family. The case q=2 is included through PSL_3(2)≅PSL_2(7).

## Lemma 2: residual-prime constituent cover

Let p≥5 be prime with p≡2 modulo 3 and put G=SL_3(p)=PSL_3(p). For every proper H<G, the action on G/H is 3-closed, and one of the following more precise alternatives holds:

1. H is contained in a point or line parabolic, and its constituent action is 3-closed by determinant-neutral parabolic kernel rigidity;
2. H is contained in a nonparabolic maximal subgroup, and b(G,G/H)≤2.

For the first alternative, the complete local proof is recorded in art_researcher_root_relative_regularity_holonomy_invariant_rev1274. Its exact argument is as follows. After the induced action on the projective quotient has been normalized, an element of the block kernel restricts on the three complete fibers over every ordered projective frame as a coordinatewise automorphism of the split-torus orbit tensor. Relative-regular anchors and the cyclic kernel containments force these three restrictions to come from one frame-torus element. In the small-core case, the verified core-overlap assertion makes transition elements on adjacent frames trivial. In the large-core case, the restrictions are phases φ(x) in a quotient of F_p^× satisfying φ(x)φ(y)φ(z)=1 for every projective frame. Given projective points u,v, choose distinct r,s on a line avoiding u and v; comparison of the frames (r,s,u) and (r,s,v) gives φ(u)=φ(v). Hence φ is constant, and its value c satisfies c^3=1. Since gcd(3,p−1)=1, c=1. Connectedness of the frame graph then kills the entire block kernel, so the constituent 3-closure is G. The dual line-parabolic case is identical by contragredient duality.

For the second alternative, choose a nonparabolic maximal overgroup M of H. The host argument in art_researcher_root_nonparabolic_host_dichotomy_rev1278 gives an exhaustive elementary dichotomy. If M is reducible, maximality makes it parabolic, contrary to the choice. If M is irreducible imprimitive, its three one-dimensional imprimitivity blocks place it in the determinant-one monomial host N_2. Suppose M is primitive and F(M)≠1. A nontrivial characteristic abelian subgroup A of F(M) has order prime to p, and E=F_p[A] is commutative semisimple. Its primitive idempotents would give an imprimitivity decomposition unless E is a field. The degree [E:F_p] divides 3; degree one would make A scalar and hence trivial because Z(G)=1. Thus E≅F_{p^3}, and M lies in the extension-field host N_3=ΓL_1(p^3)∩G.

It remains that F(M)=1. A minimal normal subgroup N is a direct product T_1×⋯×T_k of isomorphic nonabelian simple groups. If B is the image of F_p[N] on V=F_p^3, its Jacobson radical J is M-invariant. Irreducibility gives JV=0 or V, and nilpotence excludes JV=V; hence J=0. Thus V is semisimple for N. Primitivity leaves one isotypic component, so V is a direct sum of copies of one faithful irreducible N-module W. Since dim V=3 and dim W≥2, necessarily dim W=3 and the multiplicity is one. After scalar extension, every factor T_i contributes a nontrivial tensor factor of dimension at least two, so 2^k≤3 and k=1. Hence N=T is simple and acts irreducibly. The commuting field End_{F_pT}(V) has degree dividing three. Degree three would make V one-dimensional over that field and embed T in an abelian multiplicative group, so the degree is one and the module is absolutely irreducible. Also C_M(T)=1, since a minimal normal subgroup inside that centralizer would be abelian, contradicting F(M)=1, or would supply a second commuting nonabelian factor, contradicting the dimension bound. Therefore T≤M≤Aut(T).

If this absolutely irreducible module is self-dual, its invariant form is symmetric because p is odd and dim V=3. Uniqueness up to scalar shows that each m∈M acts as a similitude with multiplier λ_m satisfying λ_m^3=det(m)^2=1. The condition gcd(3,p−1)=1 gives λ_m=1, placing M in an orthogonal C8 host. If the module is not self-dual, M is an almost-simple S host. The integrated claims claim_root_c2c3_uniform_base2_descendants_rev966 and claim_root_c8_s_base2_hosts_rev1216 give b(G,G/H)≤2 in the four host cases N_2, N_3, C8, and S.

Finally, a faithful action with a base (α,β) of size at most two is 3-closed: normalize any element of its 3-closure so that it fixes α and β; preservation of the orbit of (α,β,γ) forces every γ to be fixed. Thus both alternatives give individual constituent 3-closedness.

## Lemma 3: synchronization of two parabolic descendants

Let H≤P_X and K≤P_Y, where P_X and P_Y are point or line parabolics, and assume the actions on A=G/H and B=G/K are individually 3-closed. Then the diagonal action on A⊔B is 3-closed.

There are surjective equivariant maps ρ_A:G/H→G/P_X and ρ_B:G/K→G/P_Y. Let π belong to the 3-closure on A⊔B. Constant triples show that π preserves the two tagged constituents separately, including when they are isomorphic or repeated copies. Triples internal to each constituent and individual 3-closedness give a,b∈G inducing π on A and B. Normalize by a^{-1}; the resulting permutation fixes A pointwise and acts on B as δ=a^{-1}b.

For x in the point-or-line quotient X and y in the quotient Y, choose α∈A and β∈B above x and y. The mixed triple (α,α,β) is sent to (α,α,δβ) in the same G-orbit. Hence some t∈G fixes α and sends β to δβ. Equivariance gives tx=x and ty=δy.

If X and Y have the same type, let R(x,y) mean equality; if they have opposite types, let R(x,y) mean incidence. Since R is G-invariant, R(x,y) is equivalent to R(x,δy) for every x. Equality profiles are singletons. Incidence profiles are also injective: distinct points are separated by a line through exactly one of them, and distinct lines are separated by a point on exactly one of them. Therefore δy=y for every quotient object y.

An element of SL_3(p) fixing every projective point is scalar; the same follows from fixing every projective line by taking intersections. Thus δ=λI with λ^3=1. Since p≡2 modulo 3, λ=1. Hence a=b and π is induced diagonally by an element of G. This proves the lemma in all point-point, point-line, line-point, and line-line orientations and for arbitrary descendants and repeated constituents.

The no-relational-twins condition is essential: for a general quotient relation, two distinct quotient objects with identical profiles could be interchanged. Projective equality and incidence have no such twins, so this obstruction is absent here.

## Root assembly

The integrated claims settle q=2 through PSL_3(2)≅PSL_2(7) and settle q=3 directly. Let p≥5 be prime with p≡2 modulo 3, and take arbitrary proper H,K<G as required by the integrated two-orbit reduction. Choose maximal overgroups M_H and M_K.

If at least one chosen maximal overgroup is nonparabolic, Lemma 2 gives a two-point base for that constituent and gives 3-closedness of both constituents. The integrated base-two synchronization claim then makes the action on G/H⊔G/K 3-closed. If both chosen maximal overgroups are parabolic, Lemma 2 gives individual 3-closedness and Lemma 3 synchronizes the two constituents. These cases exhaust all H and K. The two-orbit reduction therefore proves that PSL_3(p) is totally 3-closed.

Combining this positive result with Lemma 1 and the integrated projective outer obstruction proves the stated if-and-only-if classification.

## Self-check

The argument quantifies over every proper H and K rather than only maximal stabilizers; descendant base size follows from H∩H^g≤M∩M^g; both constituents are shown individually 3-closed before synchronization; the parabolic-parabolic case does not assume a base-two property; tagged constituents are recovered from constant triples; the mixed witness comes from the actual orbit of (α,α,β); equality and incidence profiles are proved injective; point and line duality and repeated copies are covered; the scalar kernel is killed using exactly gcd(3,p−1)=1; and q=2, q=3, all extension fields, all prime congruence classes, and the simplicity scope are explicitly accounted for. No verification status is asserted in this artifact.
