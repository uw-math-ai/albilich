# Replacement section: source-certified closure of the orthogonal abstract-automorphism interface

## Exact local theorem
Let F be a finite field, let (V,Q) be a nondegenerate quadratic space, and let S=PΩ(V,Q) be simple. If dim(V)≥7 and S is not PΩ_8^+(F), then every abstract automorphism of S is induced by a projective semilinear similarity of Q. Equivalently,

Aut(S)=PΓ(V,Q),

where Γ(V,Q) consists of invertible semilinear maps T with companion field automorphism σ and a scalar λ∈F* satisfying Q(Tv)=λ·σ(Q(v)) for all v∈V.

## Exact cited theorem and notation translation
Kleidman and Liebeck, The Subgroup Structure of the Finite Classical Groups, London Mathematical Society Lecture Note Series 129, Cambridge University Press, 1990, Theorem 2.1.4, printed page 16 (Chapter 2 preview PDF page 27), DOI 10.1017/CBO9780511629235.004, ISBN 9780521359498, state the following complete result. For a classical geometry (V,F,κ) of linear, unitary, symplectic, or orthogonal type, assume respectively that dim(V) is at least 2, 3, 4, or 7 and that the associated projective Ω-group is simple. Then the projective group PA(V,F,κ) is the full abstract automorphism group of PΩ(V,F,κ), except for PSp_4(q) with q even and PΩ_8^+(q). In the two exceptional cases PA has index 2 and 3, respectively, in the full automorphism group. There is no arXiv id.

The definitions immediately preceding that theorem identify, in orthogonal type, A(V,F,Q) with Γ(V,Q), the semisimilarity group. A semisimilarity is an invertible σ-semilinear map T satisfying Q(Tv)=λ(T)Q(v)^σ. Projectivization means quotienting by scalar transformations. Thus the orthogonal specialization of Theorem 2.1.4 is precisely Aut(PΩ(V,Q))=PΓ(V,Q), with only the 8-dimensional plus-type triality exception.

This interpretation is independently corroborated by Peter J. Cameron, Notes on Classical Groups, Section 8.3, page 92, https://webspace.maths.qmul.ac.uk/p.j.cameron/class_gps/cg.pdf. Cameron defines A(q) as the normalizer of the classical group X(q) in the invertible semilinear group and states that its projective image is the full automorphism group of the projective Ω-group except for GL(n,q), where duality is additional; O_8^+(q), where triality is additional; and Sp_4(q) in even characteristic, where exceptional polar-space duality is additional. For orthogonal groups outside O_8^+, this again gives the projective semisimilarity group and no extra abstract automorphisms.

A proof-level audit is supplied by Robert Steinberg, Automorphisms of Finite Linear Groups, Canadian Journal of Mathematics 12 (1960), 606–615, DOI 10.4153/CJM-1960-054-6, Theorem 3.2 and Sections 5–7, https://www.cambridge.org/core/services/aop-cambridge-core/content/view/16023F257E0F21D57873B1450E9F15E4/S0008414X00010245a.pdf/automorphisms-of-finite-linear-groups.pdf. Steinberg's complete theorem says that every automorphism of each finite group of Lie type listed in his Section 2 is a product of inner, diagonal, field, and graph automorphisms, with the field and graph factors uniquely determined. Section 2 identifies B_m and D_m, and the twisted group of type ²D_m, with the corresponding projective orthogonal groups. The proof first conjugates Sylow defining-characteristic subgroups and opposite subgroups into standard position, then recovers the root-group permutation, removes it by a graph automorphism, recovers the common field automorphism from root-group commutator relations, and finally proves that the normalized automorphism is trivial. This proof confirms that the cited classification is an abstract-automorphism theorem rather than merely a list of known geometric automorphisms.

## Hypothesis check in the local families
For B_m(q) with q odd and m≥5, dim(V)=2m+1≥11. For D_m^+(q) and D_m^-(q) with m≥5, dim(V)=2m≥10. Hence every family in the local orthogonal branch satisfies the orthogonal dimension hypothesis and avoids PΩ_8^+(q). The branch already assumes the relevant PΩ-group is simple. Odd-dimensional B-type groups in characteristic two are deliberately assigned to the verified symplectic branch, exactly as in the existing dossier. Both signs in even dimension and all field characteristics are covered by the orthogonal case of the theorem.

Consequently the group G defined in proof_orthogonal_quadratic_witt_descent_rev69 as the subgroup induced by projective semilinear similarities is not a proper subgroup in the present range: G=Aut(S). No separate building-recognition or polar-coordinate theorem is required.

## Deduction to the existing orthogonal normalizer theorem
The verified semilinear dossier fixes E=4·lcm(1,2,…,2R), chooses a hyperbolic E-space U, and lets D be the normalizer of its decomposition stabilizer. It proves for every α∈G of order dividing p or q that α has an S-conjugate in D; that D is proper and maps onto G/S; and that the factor-cycle gauge moves every order-p or order-q element of G wr Sym(t) into D wr Sym(t) by S^t-conjugacy.

Since the source-certified equality gives G=Aut(S), the same statements now quantify over every abstract automorphism of S. Therefore, for every t≥1 and every X with S^t≤X≤Aut(S) wr Sym(t), arbitrary elements of X of orders p and q have independent S^t-conjugates in the common proper subgroup X∩(D wr Sym(t)). Thus no such X is invariably generated by those two elements. This closes the high-dimensional orthogonal component without changing the Witt-descent, spinor/Dickson-correction, outer-coset-surjectivity, or wreath-gauge arguments.

## Five-step proof spine
1. Kleidman–Liebeck Theorem 2.1.4 identifies the full abstract automorphism group of a simple high-dimensional orthogonal group with its projective A-group, except in dimension eight of plus type.
2. In orthogonal type the defining equality A(V,Q)=Γ(V,Q) translates the theorem to Aut(PΩ(V,Q))=PΓ(V,Q).
3. The dimensions 2m+1 and 2m with m≥5 exclude triality and satisfy every rank hypothesis; characteristic-two odd B-type is already delegated to the symplectic branch.
4. Hence the verified semilinear decomposition-normalizer construction applies to every abstract automorphism and its verified wreath-product gauge proves the full high-dimensional orthogonal common-overgroup theorem.
5. Together with the integrated PSL, PSp, and PSU branches, this leaves exactly the global residual theorem debt_residual_classical_common_overgroup: assemble the high-dimensional classical result with the bounded-rank, exceptional-family, and characteristic-uniform projective-degree arguments needed for the alternating-group counterexample.

## Strongest near miss and representation comparison
The strongest failed route tried to recognize parabolic types numerically inside the abstract group; equal adjacent parabolic indices in B_{3k+2} show that this cannot recover the labeled building. The finite Borel–Tits route repairs recognition only conditionally and still leaves a polar-coordinate theorem. The source-classification representation bypasses both gaps by identifying the entire abstract automorphism group directly with the already handled semisimilarity group.

## Self-check
The complete source theorem, its notation, its exceptional cases, and a proof source were checked. The local deduction uses only simplicity, the stated dimension bounds, the identification A=Γ in orthogonal type, and the already verified semilinear inference. Both D-signs, field automorphisms, the ordinary D_m graph involution, odd and even characteristic, projectivization, and the scalar kernel are included by the cited PA=PΓ formulation. D_4 triality is genuinely exceptional but lies outside m≥5. No verification status is changed here, and no claim is made that the remaining global CFSG assembly is complete.
