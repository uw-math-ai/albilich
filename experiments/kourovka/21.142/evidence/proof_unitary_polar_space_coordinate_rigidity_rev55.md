# Coordinate proof of the Hermitian polar-space automorphism theorem in the target rank

## Local theorem (FH7)
Let k=F_{Q^2}, let bar be x↦x^Q, and let V be a finite-dimensional nondegenerate Hermitian k-space of Witt rank m>=7. Every point-line incidence automorphism of the Hermitian polar space P(V) is induced by a projective semilinear unitary similitude of V.

This is exactly the remaining input (FH) isolated in `proof_unitary_building_reduction_and_graph_descent_rev53`, in a range far weaker than the application: the unitary route has n>=360 and hence m>=180.

Throughout, h is linear in the first variable and bar-linear in the second.

## 1. Normalize two opposite maximal singular subspaces
An incidence automorphism preserves maximal singular subspaces and opposition. Choose opposite maximal singular subspaces E and F. By Witt extension, the unitary group is transitive on ordered opposite pairs, so after composing with a unitary isometry we may assume that phi(E)=E and phi(F)=F. The pairing

beta:E×F→k,  beta(e,f)=h(e,f),

is perfect.

The restrictions of phi to P(E) and P(F) preserve projective lines. We use the elementary fundamental theorem of projective geometry: a line-preserving bijection of P(W), for dim(W)>=3, is induced by a semilinear bijection of W. Its coordinate proof fixes a projective frame, reads addition from intersections in a projective plane, reads multiplication from the usual two-plane construction, and thereby obtains one field automorphism on all coordinates. Thus phi|P(E) and phi|P(F) are induced by maps A and B with companions sigma and tau.

Choose beta-dual bases e_i,f_i. Incidence gives h(Ae_i,Bf_j)=0 exactly when i≠j; write kappa_i=h(Ae_i,Bf_i)≠0. For a∈k* the points e_1+a e_2 and f_1+b f_2 are orthogonal exactly when 1+a bar(b)=0. Taking b=-bar(a)^{-1} and applying phi gives

kappa_1-sigma(a)tau(a)^{-1}kappa_2=0.

At a=1 this gives kappa_1=kappa_2, and then sigma(a)=tau(a) for every a. Repeating with every pair of coordinates shows that all kappa_i equal one kappa and that

h(Ae,Bf)=kappa sigma(h(e,f)).

Multiplying B by a scalar d with bar(d)kappa=1 does not change its projective action. We may therefore assume

h(Ae,Bf)=sigma(h(e,f)).

Consequently Z=A direct-sum B is a sigma-semilinear unitary isometry on H=E direct-sum F. If V has odd dimension, write V=H perpendicular kz with h(z,z)=1 and extend Z by Z(z)=z. After replacing phi by Z^{-1}phi, it is enough to treat an incidence automorphism psi fixing every point of E and F.

## 2. The polar closure of E and F
If V has odd dimension, the set P(H) is intrinsically the closure of P(E) union P(F) under polar lines, so psi preserves P(H).

Indeed, let x=e+f∈H be singular and put s=beta(e,f), so s+bar(s)=0. If s=0, x lies on the polar line through e and f. Suppose s≠0. The map t↦t-bar(t) maps k onto the trace-zero elements, so choose A_0 with A_0-bar(A_0)=s. Choose e_1 with beta(e_1,f)=A_0 such that e_1 and e_2=e-e_1 are independent. Put B_0=beta(e_2,f)=s-A_0=-bar(A_0). Choose f_1 satisfying

beta(e_1,f_1)=0,  beta(e_2,f_1)=B_0,

and put f_2=f-f_1. Then beta(e_2,f_2)=0 and beta(e_1,f_2)=A_0. Hence y=e_1+f_1 and w=e_2+f_2 each lie on a polar line joining a point of E to a point of F, while

h(y,w)=A_0+bar(B_0)=0.

Thus x=y+w lies on the polar line through y and w. This proves the closure assertion without using an ambient projective extension theorem.

## 3. Rigidity on the hyperbolic part
We now work in H=E direct-sum F. For a mixed singular point x=<e+f>, its perpendicular intersections with E and F are

ker beta(-,f) and ker beta(e,-).

Because psi fixes E and F pointwise, these two hyperplanes are unchanged. Perfectness of beta therefore gives a unique lambda_x∈k* such that

psi(<e+f>)=<e+lambda_x f>.

Call x generic when s=beta(e,f)≠0. Since both e+f and e+lambda_x f are singular and s+bar(s)=0,

bar(lambda_x)s+lambda_x bar(s)=0

forces lambda_x∈F_Q*.

We next prove that lambda_x is constant on generic points. Let x=e+f and y=e'+f' be generic with e,e' independent. Choose u∈E outside span(e,e') and outside the two hyperplanes beta(-,f)=0 and beta(-,f')=0. Such u exists: k has at least four elements, m>=7, and the sum of the cardinalities of those three proper subspaces is strictly smaller than |E|. The three functionals beta(e,-), beta(e',-), beta(u,-) on F are independent. Choose a nonzero trace-zero t∈k and solve

beta(e,v)=-bar(beta(u,f)),
beta(e',v)=-bar(beta(u,f')),
beta(u,v)=t.

Then z=u+v is generic, orthogonal to both x and y, and both cross terms in each orthogonality equation are nonzero. Applying psi to x perpendicular z gives

bar(lambda_z)beta(e,v)+lambda_x bar(beta(u,f))=0.

The original equation and lambda_x,lambda_z∈F_Q* imply lambda_x=lambda_z. Similarly lambda_y=lambda_z. If e and e' are dependent, insert a generic point whose E-component is independent of their common line. Hence all generic points have one common scalar c∈F_Q*.

If x=e+f is nongeneric with e,f≠0, choose u outside span(e) and with beta(u,f)≠0. Solve

beta(e,v)=-bar(beta(u,f)),  beta(u,v)=t

for a nonzero trace-zero t. Then z=u+v is generic and orthogonal to x with nonzero cross terms. Applying psi to this orthogonality equation gives lambda_x=c. Points in E or F were fixed from the outset. Therefore on every singular point of H,

psi(<e+f>)=<e+c f>.

The linear map T_c(e+f)=e+c f satisfies h(T_cx,T_cy)=c h(x,y), because c∈F_Q*. Thus psi|P(H) is induced by a unitary similitude. In even dimension this completes the theorem.

## 4. Rigidity of the odd-dimensional anisotropic coordinate
Assume V=H perpendicular kz. Extend T_c to a similitude of V by sending z to d z, where d bar(d)=c; such d exists by surjectivity of the norm k*→F_Q*. After composing with its inverse, assume psi fixes every singular point in H.

Every singular point outside H has the form x=<h+a z> with a≠0 and h nonsingular. If psi(x)=<h'+a'z>, then for every singular y∈H,

h+az perpendicular y if and only if h'+a'z perpendicular y.

The singular vectors in h-perpendicular inside H span that hyperplane. To see this, take a hyperbolic basis for its hyperbolic part; if an anisotropic line remains, its generator is a linear combination of two singular vectors and a hyperbolic pair, using surjectivity of the trace k→F_Q. Hence equality of the two singular hyperplane sections implies h' is proportional to h. Rescaling gives

psi(<h+a z>)=<h+a_x z>.

Singularity implies u_x=a_x/a has norm one.

The orthogonality graph on the singular points outside H is connected. For x=h+a z and y=k+b z with h,k independent, choose l_0∈H satisfying

h(h,l_0)=-a,  h(k,l_0)=-b.

Let W_0=span(h,k,l_0)-perpendicular. Removing three vectors lowers Witt index by at most three; since m>=7 and the radical of W_0 has dimension at most three, W_0 contains a hyperbolic plane. The Hermitian norm on that plane represents every element of F_Q. Choose v∈W_0 with h(v,v)=-1-h(l_0,l_0). Then

w=l_0+v+z

is singular, outside H, and orthogonal to both x and y. If h and k are dependent, insert an outside singular point whose H-component is independent of their line. Thus the graph is connected.

For adjacent outside points x=h+a z and y=k+b z, orthogonality before and after applying psi gives

h(h,k)+a bar(b)=0,
h(h,k)+u_x bar(u_y)a bar(b)=0.

Therefore u_x bar(u_y)=1. Since both u_x and u_y have norm one, u_x=u_y. Connectivity gives one constant u of norm one. The unitary isometry acting identically on H and sending z to u z induces psi on every polar point. This proves (FH7).

## 5. Assembly into the selected unitary route
The dossier `proof_unitary_building_reduction_and_graph_descent_rev53` proves that an abstract automorphism of S=PSU(V) induces a polar-space incidence automorphism and that, once such an automorphism is induced by a semilinear unitary similitude, the chamber-action kernel is trivial. It also proves uniqueness and order of the field component and identifies Q-Frobenius with the graph operation. The theorem above supplies its sole missing input in the whole target range.

Sections 2-6 of `proof_unitary_outer_normalizer_twisted_descent_rev47` then provide bounded Hermitian self-dual blocks, odd-field descent, graph fixed-form descent, the prescribed nondegenerate E-space, PSU correction, outer-coset realization, properness, and the wreath-product gauge. Consequently the combined evidence is a verifier-ready candidate for `claim_unitary_outer_coset_decomposition_normalizer_rev47`.

## Five-step proof spine
1. Abstract PSU automorphisms act on the Hermitian polar incidence geometry.
2. The coordinate theorem (FH7) reconstructs a semilinear unitary similitude.
3. Chamber faithfulness and field-component uniqueness give the exhaustive form [A]sigma.
4. The existing block and descent arguments put every prime-order automorphism into the fixed proper decomposition normalizer.
5. PSU coset correction and the wreath gauge give the product-power conclusion.

The sole next root-level theorem gap is the orthogonal-family outer-coset normalizer analogue; the bounded-rank CFSG assembly remains downstream of that family bridge.

## Self-check
The proof uses m>=7 only in the odd-dimensional common-neighbor argument; the application has m>=180. The projective-geometry step applies because dim(E)>=3. Trace and norm surjectivity hold for every finite quadratic extension, including characteristic two. The closure lemma prevents an unjustified assumption that the hyperbolic part is already an intrinsic ambient subspace. Generic and nongeneric scalar fibers are both handled. The odd anisotropic fiber is controlled by an explicitly connected orthogonality graph. No external classification theorem or finite computation is used in (FH7). The only dependencies are the already attached group-to-building reduction and the existing unitary normalizer dossier.
