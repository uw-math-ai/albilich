# Source-certified orthogonal route conversion

## Local theorem
Fix distinct primes p and q, put R=max(p,q), E=4·lcm(1,2,…,2R), and n0=4RE. Let S=PΩ(V,Q) be a finite simple orthogonal group of natural dimension n≥n0, of type B_m over an odd-order field or D_m^± over an arbitrary finite field, with m≥5. Then there is a proper nondegenerate-decomposition normalizer D≤Aut(S) such that DS=Aut(S), and for every t≥1, every X satisfying S^t≤X≤Aut(S) wr Sym(t), and every element x∈X of order p or q, some S^t-conjugate of x lies in D wr Sym(t). Consequently, any elements x,y∈X of respective orders p and q have independent S^t-conjugates in the same proper subgroup X∩(D wr Sym(t)); hence they do not invariably generate X.

## Source interface
Kleidman and Liebeck, The Subgroup Structure of the Finite Classical Groups, London Mathematical Society Lecture Note Series 129, Cambridge University Press, 1990, Theorem 2.1.4, printed page 16, DOI 10.1017/CBO9780511629235.004, state the following theorem. For a classical geometry (V,F,κ) of linear, unitary, symplectic, or orthogonal type, in respective dimensions at least 2, 3, 4, or 7, and with simple associated projective Ω-group, the full abstract automorphism group of PΩ(V,F,κ) is the projective image PA(V,F,κ), except that PA has index two for PSp_4(q) with q even and index three for PΩ_8^+(q). There is no arXiv id.

In orthogonal type their group A(V,F,Q) is the group Γ(V,Q) of invertible semilinear similarities: T has a companion field automorphism σ and a scalar λ with Q(Tv)=λσ(Q(v)). Projectivizing gives PA(V,F,Q)=PΓ(V,Q). Thus their theorem yields Aut(PΩ(V,Q))=PΓ(V,Q) whenever dim(V)≥7, PΩ(V,Q) is simple, and the group is not PΩ_8^+(F).

For B_m(q) with q odd and m≥5, dim(V)=2m+1≥11. For D_m^±(q) with m≥5, dim(V)=2m≥10. These families satisfy the dimension and simplicity hypotheses and exclude D_4 triality. Odd-dimensional characteristic-two B-type groups are assigned to the already integrated symplectic branch. Both D-signs, arbitrary field automorphisms, and the ordinary D_m graph automorphism are included in the projective semisimilarity group specified by the cited theorem.

## Composition with the integrated semilinear theorem
Let G=PΓ(V,Q). The integrated claim claim_orthogonal_semilinear_decomposition_normalizer_rev69 supplies the subgroup D and proves three facts for G: D is proper, DS=G, and every order-p or order-q element of G wr Sym(t) is S^t-conjugate into D wr Sym(t). The source theorem gives G=Aut(S), so these three conclusions hold with the full abstract automorphism group in place of G.

Now take x,y∈X of orders p and q. Applying the preceding conjugacy statement independently gives a,b∈S^t with x^a,y^b∈D wr Sym(t). Since S^t≤X, both conjugates remain in X, hence lie in M=X∩(D wr Sym(t)). The subgroup M is proper in X: otherwise S^t≤D wr Sym(t), which would force a coordinate copy of S into D∩S, contradicting the proper decomposition stabilized by D. Therefore the two chosen conjugates generate a subgroup contained in M<X. This is exactly the failure of invariable generation by x and y.

## Five-step proof spine
1. Kleidman–Liebeck Theorem 2.1.4 gives Aut(S)=PΓ(V,Q) in the stated orthogonal families.
2. The rank bounds m≥5 imply dimensions at least ten and exclude the sole orthogonal exception PΩ_8^+.
3. claim_orthogonal_semilinear_decomposition_normalizer_rev69 supplies a proper decomposition normalizer D, outer-coset surjectivity, and the wreath-product conjugacy gauge for PΓ(V,Q).
4. Substituting Aut(S)=PΓ(V,Q) proves the full high-dimensional orthogonal common-overgroup theorem.
5. Together with the integrated PSL, PSp, and PSU modules, this leaves exactly one theorem-level root gap: the residual bounded-rank and exceptional-family assembly, including characteristic-uniform projective-degree bounds needed to turn a sufficiently large alternating group into a counterexample to the original embedding assertion.

## Representation comparison
The intrinsic-building representation attempts to reconstruct parabolics, chamber incidence, the action kernel, and polar coordinates. Its numerical shortcut fails because adjacent parabolic indices can coincide in type B, while the repaired finite-Borel–Tits version remains conditional on further coordinate reconstruction. The source-classification representation identifies the entire abstract automorphism group directly with the semisimilarity group already handled by the integrated module. The dictionary is S=PΩ(V,Q), source PA=PΓ(V,Q), source A=Γ(V,Q), and the source triality exception=PΩ_8^+, excluded by m≥5. The equality Aut(S)=PΓ(V,Q) converts back to the original obligation by extending the verified semilinear theorem's quantifier from induced semisimilarities to all abstract automorphisms.

## Self-check
The source statement, theorem number, notation translation, projectivization, dimension hypotheses, simplicity hypothesis, both D-signs, field and graph automorphisms, the D_4 exception, and the characteristic-two B-type transfer were checked. The common-overgroup deduction uses the integrated semilinear claim as an explicit premise. No verification status is asserted. The argument does not claim the remaining global bounded-rank/alternating-group assembly.
