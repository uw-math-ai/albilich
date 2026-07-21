# Reduction of unitary automorphism classification to one polar-space theorem

## Exact remaining bridge
Let V be a nondegenerate Hermitian space over k=F_{Q^2} of dimension n at least 5 and Witt rank at least 3. The only external or separately proved theorem still needed in Section 1 of the unitary dossier is:

(FH) Every incidence automorphism of the Hermitian polar space of V is induced by a semilinear unitary similitude Z; equivalently, after choosing a standard Gram matrix, Z=A sigma with A in GU(V) and sigma in Aut(k).

Everything else required to pass from an abstract automorphism of S=PSU(V) to [A]sigma follows locally as below.

## 1. From an abstract group automorphism to the polar building
Let ell be the characteristic of k, let U be a Sylow ell-subgroup of S, and put B=N_S(U). In the standard BN-pair of S, the conjugates of B are the chambers. The minimal proper overgroups of B are the rank-one parabolic subgroups. This description is group-theoretic: by the Bruhat decomposition, a minimal subgroup properly containing B is B union BsB for one simple reflection s. Therefore every alpha in Aut(S) sends Sylow ell-subgroups to Sylow ell-subgroups, their normalizers to their normalizers, and minimal proper overgroups to minimal proper overgroups. It consequently induces an automorphism of the chamber system, hence an incidence automorphism of the Hermitian polar space.

Assume (FH), and let Z be a semilinear unitary similitude inducing this building automorphism. Conjugation by Z induces an automorphism beta of S. Put gamma=beta^{-1}alpha. Then gamma fixes every chamber. For s in S and every chamber C,

gamma(s)C=gamma(s)gamma(C)=gamma(sC)=sC.

Thus s^{-1}gamma(s) fixes every chamber. The kernel of the S-action on chambers is the core of B in S. Since S is simple and B is proper, this core is trivial. Hence gamma(s)=s for every s and alpha=beta. This repairs the earlier imprecise sentence that an automorphism itself lies in the core: it is the element s^{-1}gamma(s) that lies in the core for every s.

## 2. Uniqueness and order of the field component
Suppose two semilinear unitary similitudes induce the same automorphism of S. Their quotient fixes every isotropic projective point. Choose mutually orthogonal isotropic vectors e_1,e_2 inside a Witt frame. The lines spanned by e_1+a e_2 are isotropic for every a in k. After normalizing the two fixed coordinate lines, preservation of all these lines forces sigma(a)=a for every a, so the quotient has trivial field component. It is then linear and fixes every isotropic line; the isotropic vectors span V in Witt rank at least 2, and the usual line-sum argument makes the quotient scalar. Thus the field component sigma is well-defined.

Composition multiplies field components, so alpha maps to sigma under a homomorphism Aut(S) to Aut(k). If alpha has order dividing a prime r, then sigma^r=1. Since Aut(k) is cyclic, sigma is either trivial or has order r. For odd r its fixed field is not fixed by bar, because the involution bar cannot belong to an odd-order subgroup. For r=2 the only nontrivial sigma is bar. This proves the exhaustiveness of the three cases used later: sigma=1, odd prime-order sigma, and sigma=bar.

## 3. Graph identification and fixed-form lemma
In a basis with Hermitian Gram matrix I, a unitary matrix g satisfies bar(g)^T g=I, hence bar(g)=(g^{-1})^T. Thus entrywise bar induces the inverse-transpose graph automorphism; it is not an additional independent component.

For completeness, let B be a unitary similitude with B bar(B)=I, multiplier epsilon, and T=B bar. The multiplier equation gives epsilon^2=1. Galois descent gives V=k tensor_{F_Q} V_0 with V_0=Fix(T), so dim_{F_Q}(V_0)=n. If v,w lie in V_0, then h(v,w)=epsilon bar(h(v,w)). For epsilon=1, the restriction takes values in F_Q and is symmetric. It is nondegenerate because an element orthogonal to V_0 is, after scalar extension, orthogonal to V. For epsilon=-1, the characteristic is odd; choosing theta with bar(theta)=-theta makes b=theta^{-1}h|_{V_0} an F_Q-valued alternating nondegenerate form. In characteristic two, -1=1 and only the first description is needed. This proves the graph fixed-form step independently of the finite experiment.

## 4. Assembly into the selected route
Assuming only (FH), Sections 1 and 2 give the exhaustive representation alpha=[A]sigma with the required order behavior. Section 3 supplies graph=bar and the exact fixed-form descent. The existing dossier then supplies bounded Hermitian self-dual blocks for sigma=1, odd-field Hilbert-90 descent, construction of the E-space, PSU correction, outer-coset realization, properness, and the wreath-product gauge. Hence (FH), together with the existing dossier, proves claim_unitary_outer_coset_decomposition_normalizer_rev47.

The integrated PSL and PSp theorems then join this unitary theorem in the root spine. The orthogonal family and bounded-rank terminal assembly remain downstream and are not asserted here.

## Self-check
The target has n at least 360, so simplicity, thickness, and Witt rank at least 3 exclude all low-rank exceptional isomorphisms. The core argument is pointwise and does not confuse group elements with automorphisms. The field component is proved unique before its order is used. The CAS calculation is treated only as finite falsification evidence; the general graph fixed-form lemma is proved algebraically. The sole remaining unitary classification input is the exact polar-space theorem (FH).
