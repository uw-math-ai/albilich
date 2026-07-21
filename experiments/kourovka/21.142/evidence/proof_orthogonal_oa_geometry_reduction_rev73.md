# Orthogonal abstract-automorphism interface after the triality experiment

## Exact local target

Let \(S=P\Omega(V)\), where \(V\) is a nondegenerate finite quadratic space of type \(B_m\) in odd characteristic or \(D_m\) in arbitrary characteristic, with \(m\ge5\); characteristic-two odd-dimensional \(B\)-type groups are assigned to the already integrated symplectic branch. The verified artifact `proof_orthogonal_quadratic_witt_descent_rev69` proves the common product-type overgroup theorem for the subgroup of \(\operatorname{Aut}(S)\) induced by projective semilinear similarities. The missing implication is
\[
\text{abstract automorphism of }S\Longrightarrow\text{projective semilinear similarity of }(V,Q).
\tag{OA}
\]

## Immediate consequences and direct attack

The verified decomposition, Witt cancellation, semilinear descent, spinor/Dickson correction, outer-quotient surjectivity, and wreath gauge should not be reopened. If (OA) is established, the orthogonal high-dimensional family immediately joins the already integrated \(PSL\), \(PSp\), and \(PSU\) families.

A first attack through the quotient \(\operatorname{Aut}(S)/S\) is circular. One can compute the cosets supplied by \(PGO(V)\), field maps, and the nontriality graph involution, but equality with the full abstract automorphism group is exactly what (OA) asserts. Order comparisons would merely import the classification being proved. This attack is therefore abandoned.

## Geometry attack selected by the computation

Use the spherical building \(\Delta(V)\) of totally singular flags. The required implication factors as
\[
\operatorname{Aut}(S)\xrightarrow{\mathrm{BR}}\operatorname{Aut}(\Delta(V))\xrightarrow{\mathrm{PG}}P\Gamma GO(V)\longrightarrow\operatorname{Aut}(S).
\]
Here (BR) is intrinsic building recognition: maximal defining-characteristic parabolics and their incidence must be recoverable from the abstract group \(S\), and the action kernel must be trivial. The step (PG) is the coordinate theorem for orthogonal polar spaces.

The triality computation closes the type-permutation part of this factorization. For \(B_m\), \(m\ge3\), the colored diagram has no automorphism. For \(D_m\), \(m\ge5\), its only diagram automorphism exchanges the two terminal maximal-singular types. The verified orthogonal dossier constructs this exchange by an improper isometry. Thus, after composing a building automorphism with such an isometry when necessary, it is type preserving. The only extra permutation in \(D_4\) is triality; \(D_4\) is outside the high-dimensional range and belongs to the bounded-rank terminal assembly.

For clarity, the coordinate step has the following local structure. Choose opposite maximal totally singular spaces
\[
E=\langle e_1,\ldots,e_m\rangle,\qquad F=\langle f_1,\ldots,f_m\rangle
\]
in the split part, with \(b(e_i,f_j)=\delta_{ij}\). A type-preserving building automorphism restricts on \(E\) and \(F\) to projective collineations. The fundamental theorem of projective geometry supplies semilinear maps on both spaces. Cross-orthogonality forces the same field automorphism and makes the two maps contragredient up to one scalar. Singular points with coordinates \(e+a+cf\), where \(a\) lies in the anisotropic kernel of dimension at most two and \(c\) is fixed by \(Q(e+a+cf)=0\), then determine the action on the anisotropic kernel and force preservation of \(Q\) up to one multiplier. Hence the building action is induced by a projective semilinear quadratic similarity. A fully internal proof must spell out this last coordinate recovery in characteristic two as well as odd characteristic; the present pass does not promote it to a verified inference.

The decisive smaller theorem exposed by the experiment is:

**(BRK).** For the above \(S\) of rank \(m\ge5\), the stabilizers of nonzero proper totally singular subspaces, together with their incidence, admit an intrinsic group-theoretic characterization invariant under every abstract automorphism of \(S\); the resulting action on \(\Delta(V)\) is faithful.

Once (BRK) is proved, diagram rigidity reduces every induced building automorphism to a type-preserving one, the coordinate argument gives a semilinear similarity, and faithfulness identifies the original abstract automorphism with the induced one. This establishes (OA) and upgrades the verified semilinear normalizer theorem without modifying its construction.

## Representation switch

The subgroup-and-quotient representation encodes an automorphism by its putative image in \(PGO/S\), its field component, and its graph component. It is efficient only after completeness of those components is known, so it leaves (OA) unchanged. The building representation encodes the same data by the permutation of intrinsic parabolic classes and the induced incidence map. The dictionary is:
\[
\begin{array}{c|c}
\text{group data}&\text{building data}\\ \hline
\text{stabilizer of a totally singular }i\text{-space}&\text{type-}i\text{ maximal parabolic}\\
\text{parabolic containment/intersection}&\text{flag incidence}\\
D_m\text{ terminal graph coset}&\text{swap of the two maximal-singular families}\\
\text{semilinear quadratic similarity}&\text{type-preserving polar-space collineation}.
\end{array}
\]
The round trip is exact conditional on (BRK): an abstract automorphism gives a faithful building action; diagram correction and coordinates give a semilinear similarity with the same action; their quotient fixes every building object and hence is trivial.

## Root assembly and remaining obstruction

Assuming (BRK) and the explicit coordinate recovery, (OA) combines with the verified orthogonal semilinear inference. Together with the integrated linear, symplectic, and unitary claims, this proves the common-proper-overgroup statement for all sufficiently high-dimensional classical composition factors. The root theorem is not yet proved: the terminal bounded-rank and exceptional-family analysis and the characteristic-uniform faithful-projective-degree argument for a sufficiently large alternating counterexample remain separate obligations.

The new obstruction is precise. A finite diagram or polar-space computation cannot show that arbitrary abstract automorphisms preserve defining-characteristic parabolics. The next proof must characterize those parabolics internally, for example from normalizers of maximal unipotent subgroups and their rank-one residues, with explicit exclusion of small accidental isomorphisms. If that recognition fails, one must produce an exact exotic automorphism; another computation of semilinear cosets would not address the gap.

## Self-check

The experiment was used only to select and narrow the proof architecture, not to certify an infinite statement. The split \(D_m^+\) type-count formula was not extrapolated to twisted minus type; diagram rigidity, which is independent of the sign, is the theorem-level input. The improper-isometry realization is already contained in the verified semilinear dossier. \(D_4\) triality, characteristic-two odd \(B\)-type, and small nonsimple cases are explicitly outside this local theorem. No root conclusion and no verification transition is claimed.
