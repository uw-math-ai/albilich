# Source-certified orthogonal automorphism interface

## Local theorem
Let F be a finite field and let (V,Q) be a nondegenerate quadratic space. Suppose S=PΩ(V,Q) is simple and is either B_m(F) with m>=5 and char(F) odd, or D_m^+(F) or D_m^-(F) with m>=5 in arbitrary characteristic. Then every abstract automorphism of S is induced by a projective semilinear similarity of Q:

Aut(S)=PΓ(V,Q).

Here Γ(V,Q) consists of the invertible sigma-semilinear maps T for which Q(Tv)=lambda Q(v)^sigma for some lambda in F* and every v in V; PΓ is its image after quotienting scalar transformations.

## Exact source interface
Kleidman and Liebeck, The Subgroup Structure of the Finite Classical Groups, LMS Lecture Note Series 129, Cambridge University Press, 1990, Chapter 2, Section 2.1, Theorem 2.1.4, printed page 16, DOI 10.1017/CBO9780511629235.004, no arXiv id, state: for a classical geometry (V,F,kappa), in orthogonal dimension at least 7 and with PΩ(V,F,kappa) simple, the projective group PA(V,F,kappa) is the full abstract automorphism group of PΩ(V,F,kappa), except that PA has index 3 for PΩ_8^+(q). The theorem also lists an even-characteristic PSp_4 exception, irrelevant here. The definitions immediately preceding the theorem identify A(V,F,Q) in orthogonal type with the semisimilarity group Γ(V,Q), and projectivization quotients scalar maps. Thus, away from PΩ_8^+, the orthogonal specialization is exactly Aut(PΩ(V,Q))=PΓ(V,Q), not merely an inclusion of standard automorphisms.

Steinberg, Automorphisms of Finite Linear Groups, Canadian Journal of Mathematics 12 (1960), Theorem 3.2 and Sections 5-7, DOI 10.4153/CJM-1960-054-6, no arXiv id, supplies proof-level corroboration: for the finite groups of types B_m, D_m, and twisted 2D_m, every abstract automorphism factors into inner, diagonal, field, and graph factors. His proof normalizes opposite defining-characteristic root subgroups, extracts the diagram and field actions from root-group commutator relations, and proves the remaining normalized automorphism trivial.

## Hypothesis dictionary and check
For B_m(q) in odd characteristic, dim(V)=2m+1>=11. For D_m^+(q) and D_m^-(q), dim(V)=2m>=10. Hence the source dimension bound is satisfied and PΩ_8^+(q), which is D_4 triality, cannot occur. Simplicity is part of the local hypothesis. The minus family is the twisted 2D_m family and is included in the source's orthogonal geometry. Both signs and both field characteristics in even dimension are covered. Odd-dimensional B type in characteristic two is outside this local orthogonal claim and is already represented by the integrated symplectic family.

The diagram audit gives an independent boundary check. In B_m the unique Coxeter edge labeled 4 pins its endpoint and then the entire path. In D_m for m>=5, the trivalent vertex has arms of lengths 1, 1, and m-3, so the only nontrivial diagram automorphism exchanges the two terminal spin nodes and fixes the long arm, including point and line types. At m=4 all three arms have length 1, producing the triality excluded by the source theorem.

## Deduction to the common-overgroup theorem
Let G_sem be the subgroup of Aut(S) induced by projective semilinear similarities. The verified claim claim_orthogonal_semilinear_decomposition_normalizer_rev69 constructs, for fixed distinct primes p and q, a fixed proper nondegenerate-decomposition normalizer D such that every order-p or order-q element of G_sem has an S-conjugate in D; D realizes the required outer cosets; and the factor-cycle gauge works in G_sem wr Sym(t).

The source theorem gives G_sem=Aut(S) in every local family. Therefore the same conjugacy statement holds for every order-p or order-q abstract automorphism. For every t>=1 and every X with S^t<=X<=Aut(S) wr Sym(t), independently conjugating the chosen p-element and q-element by elements of S^t puts both in X intersect (D wr Sym(t)). This subgroup is proper because D is proper and cannot contain the full socle S^t. Thus the two elements cannot invariably generate X. This is exactly the orthogonal premise used by the integrated terminal simple-factor exclusion.

## Representation comparison
The intrinsic-building representation would require abstract recognition of parabolics, recovery of incidence, a point-line polar-space coordinate theorem, and a trivial chamber-action kernel. The source-classification representation replaces that chain by the single exact equality Aut(PΩ)=PΓ, whose right side is precisely the group already handled by the semilinear construction. The Coxeter-diagram representation independently checks the only exceptional graph phenomenon but cannot classify all abstract automorphisms. The source-classification representation is therefore strictly simpler and is selected.

## Root assembly
The orthogonal conclusion joins the integrated PSL, PSp, PSU, and alternating common-overgroup conclusions in claim_terminal_simple_factor_exclusion_rev128. If a p,q-invariably generated finite host contained the alternating group A_m selected there, the integrated minimal-host reduction would place a copy of A_m in a simple factor S and place the host in S^t<=X<=Aut(S) wr Sym(t). The terminal claim then supplies independent socle conjugates of the two generators in a common proper subgroup, contradicting invariable generation. Hence A_m is a counterexample to the root question.

## Self-check
The source is a full abstract-automorphism theorem. Its orthogonal notation, projectivization, simplicity and dimension assumptions, signs, characteristics, twisted D-minus family, scalar kernel, ordinary D_m graph involution, D_4 exception, and characteristic-two B-family delegation were checked. The CAS audit is not used to certify the infinite equality. No verification status is asserted in this dossier.
