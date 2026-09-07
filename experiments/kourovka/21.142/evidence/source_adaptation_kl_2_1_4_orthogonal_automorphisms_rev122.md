Theorem-adaptation packet for Kleidman–Liebeck, Theorem 2.1.4.

Source location: The Subgroup Structure of the Finite Classical Groups, Chapter 2, Theorem 2.1.4, printed page 16; orthogonal notation is defined immediately before the theorem.

Exact source statement: For a finite classical geometry (V,F,kappa) of linear, unitary, symplectic, or orthogonal type, with respective dimension at least 2, 3, 4, or 7 and simple associated projective Ω-group, PA(V,F,kappa) is the full abstract automorphism group of PΩ(V,F,kappa), except that PA has index 2 for PSp_4(q) with q even and index 3 for PΩ_8^+(q).

Local statement translation: In orthogonal type A(V,F,Q)=Γ(V,Q), the invertible semilinear similarities of Q, and projectivization gives PA(V,F,Q)=PΓ(V,Q). Hence Aut(PΩ(V,Q))=PΓ(V,Q) whenever PΩ(V,Q) is simple, dim(V)>=7, and the group is not PΩ_8^+(q).

Definition dictionary: source PΩ(V,F,Q) is the local S=PΩ(V,Q); source A(V,F,Q) is the local Γ(V,Q); source PA is PΓ(V,Q), obtained by quotienting scalar transformations. Inner automorphisms come from S. Diagonal automorphisms are represented by projective similarity cosets outside S. Field automorphisms are the companion automorphisms of semilinear similarities. The ordinary D_m graph involution for m>=5 is included in PΓ(V,Q); D_4 triality is the exceptional PΩ_8^+ case.

Hypothesis dictionary and checks: The source orthogonal dimension bound dim(V)>=7 holds because B_m(q), q odd, m>=5 has dimension 2m+1>=11 and D_m^±(q), m>=5 has dimension 2m>=10. The local branch assumes S simple. The rank bound excludes D_4 and all small accidental low-rank cases. Both D-signs and all characteristics in even dimension are covered. Odd-dimensional B-type in characteristic two is deliberately handled by the integrated symplectic branch. Projectivization agrees on both sides and removes precisely the scalar kernel.

Missing hypotheses: none for the stated local orthogonal families.

Local deduction: The cited theorem identifies every abstract automorphism in the local high-rank orthogonal branch with an element of the projective semisimilarity group already handled by the semilinear decomposition-normalizer construction. Thus it closes debt_orthogonal_oa_source_certification_rev79. It does not independently prove the root theorem because the global bounded-rank, exceptional-family, projective-degree, and alternating-group assembly remains.

Reusable proof moves: replace intrinsic reconstruction of abstract automorphisms by the equality Aut(S)=PA=PΓ; translate the source A-group before applying the theorem; use the natural-dimension inequalities to discharge the source rank bound and triality exception; projectivize explicitly to account for the scalar kernel; route characteristic-two odd-dimensional B-type through its symplectic identification.

Failure boundary: The theorem says nothing about constructing the common proper product-type subgroup, the wreath-product gauge, bounded-rank classical and exceptional groups, or the final alternating-group counterexample. Those steps must come from existing local proof modules or later synthesis.

Representations considered: (1) intrinsic decomposition of abstract automorphisms into inner, diagonal, field, and graph factors; (2) geometric realization as the projective semisimilarity group PA=PΓ; (3) reconstruction through the orthogonal building. Translation dictionary: the four intrinsic automorphism types are precisely the automorphisms represented in PΓ outside the D_4 triality exception. Equivalence check: the source definition A=Γ and Theorem 2.1.4 give Aut(S)=PΓ, while every projective semisimilarity normalizes Ω and therefore induces an automorphism of S. Chosen representation: projective semisimilarities, because it directly matches the group quantified over by the integrated normalizer theorem. Next test in the chosen representation: ensure the integrated module uses the same scalar quotient PΓ and retains the m>=5 exclusion of triality; both checks are recorded in the manifest-listed rev89 and rev95 dossiers.
