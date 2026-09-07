# Proof repair: bounded orthogonal blocks for symplectic similitudes

## Repaired local theorem

Let F be a finite field, let r be prime, let V be a finite-dimensional symplectic F-space with alternating form B, and let A be a similitude of multiplier mu. If A^r=lambda I, then V is an orthogonal direct sum of nondegenerate A-invariant subspaces, each of dimension at most 2r.

## Proof

Because A is invertible, lambda is nonzero. Comparing multipliers in A^r=lambda I gives mu^r=lambda^2. Define

Lambda=F[T,T^{-1}]/(T^r-lambda)

and let T act on V as A. The formula iota(T)=mu T^{-1} defines an involution of Lambda: indeed

(mu T^{-1})^r-lambda=lambda^2 T^{-r}-lambda=-lambda T^{-r}(T^r-lambda).

For a finite Lambda-module M, let D(M)=Hom_F(M,F), with Lambda-action twisted by iota. The similitude identity implies

B(Av,w)=B(v,mu A^{-1}w),

so beta(v)(w)=B(v,w) is a Lambda-module isomorphism beta:V to D(V).

Every indecomposable finite Lambda-module is, as an F[T]-module, of the form C=F[T]/(f^e), where f is irreducible and f^e divides T^r-lambda. Consequently

dim_F C=e deg(f) <= r.                                                    (1)

We now prove the self-dual Krull-Schmidt splitting step which was missing from the earlier dossier. Write

V=direct_sum over tau and i of C_{tau,i},

where tau runs over the isomorphism types of indecomposable Lambda-modules. Each End_Lambda(C_tau) is local. In the quotient of the finite Krull-Schmidt category by its categorical radical, the copies of C_tau form a vector space over the division ring

Delta_tau=End_Lambda(C_tau)/rad End_Lambda(C_tau).

Maps between nonisomorphic indecomposables are radical, and an endomorphism of a finite direct sum is invertible precisely when its block matrices on this semisimple quotient are invertible. For completeness, the latter assertion follows by identifying the kernel of

End_Lambda(V) -> product over tau of M_{m_tau}(Delta_tau)

with the Jacobson radical: off-type maps are categorical-radical maps, same-type radical entries lie in the maximal ideals of the local endomorphism rings, and this finite-dimensional radical ideal is nilpotent. Thus invertibility modulo it lifts to actual invertibility.

Duality permutes the types; write tau* for the type of D(C_tau). Reduce beta modulo the categorical radical.

First suppose tau is not tau*. Since beta is an isomorphism, its residue matrix pairs the tau-multiplicity space perfectly with the tau*-multiplicity space. Hence some component between a copy C of type tau and a copy C' of type tau* is outside the radical and therefore is an isomorphism. Alternating symmetry makes the reverse component an isomorphism as well. On W=C direct_sum C', the residue matrix of the restricted form has invertible off-diagonal entries and zero diagonal entries. It is therefore invertible. Lifting across the radical shows that beta restricted to W is an isomorphism W to D(W), so W is nondegenerate.

Now suppose tau=tau*. The residue Gram matrix on the copies of C_tau is invertible over Delta_tau. If it has a nonzero diagonal entry, the restriction to the corresponding single copy C is an isomorphism C to D(C), and C is nondegenerate. If every diagonal entry is zero, invertibility supplies a nonzero off-diagonal entry. Choose the corresponding two copies C and C'. Alternating symmetry supplies the reverse nonzero entry, so the 2 by 2 residue Gram matrix on C direct_sum C' is invertible. Again the restricted form lifts to an isomorphism, making C direct_sum C' nondegenerate.

Thus every nonzero V contains a nondegenerate A-invariant submodule W which is either one indecomposable or the sum of two indecomposables. By (1), dim W<=2r. Its orthogonal complement is A-invariant: if y is orthogonal to W and w lies in W, then

B(Ay,w)=mu B(y,A^{-1}w)=0.

Hence V=W orthogonal_sum W^perp. Repeating the argument on W^perp terminates and proves the theorem.

This proof explicitly handles defining characteristic. If char(F)=r, then T^r-lambda has a single primary factor over the finite field and the indecomposables are the unequal Jordan modules C_k=F[t]/(t^k), k<=r. Pairings between unequal k can be nonzero, but they are maps between nonisomorphic indecomposables and therefore lie in the categorical radical. They need not vanish before reduction; this is exactly why the earlier unqualified multiplicity-space Gram argument was incomplete.

## Assembly into the selected route

Replace Lemma 1 of proof_psp_outer_normalizer_module_descent_rev19 by the repaired theorem above. Its blocks are nondegenerate, A-invariant, and have dimensions e<=2r. Since every such e is even and divides E=lcm(1,...,2R), the original pigeonhole argument produces an A-invariant nondegenerate E-space. The inner-diagonal conjugation follows. The field/diagonal-field Hilbert-90 descent, correction of the PGSp conjugator through the fixed decomposition subgroup, properness, and wreath-product gauge arguments in the original dossier do not use the old Gram assertion and remain unchanged. Therefore the two dossiers together give a complete candidate proof of claim_psp_outer_coset_decomposition_normalizer.

## Four-step proof spine

1. Encode A and its adjoint by the involutive Artinian algebra Lambda.
2. Every indecomposable Lambda-module has F-dimension at most r.
3. The self-dual Krull-Schmidt radical quotient splits a nondegenerate invariant block supported on one or two indecomposables.
4. Orthogonal induction proves bounded blocks; the original pigeonhole, descent, and wreath arguments then prove the target claim.

## Self-check and near miss

The proof uses A^r=lambda I and mu^r=lambda^2 to make iota well defined; it treats inseparable T^r-lambda without assuming semisimplicity; it does not assume unequal Jordan sizes are orthogonal; and it uses the radical quotient only to detect units, after which invertibility is lifted in the finite-dimensional endomorphism ring. Orthogonal complements remain A-invariant for similitudes, not merely isometries. The strongest failed route was the earlier direct multiplicity-space Gram elimination, which silently discarded cross-pairings between unequal Jordan sizes. The categorical-radical step removes exactly that obstruction.
